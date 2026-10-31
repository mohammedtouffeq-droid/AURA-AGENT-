"""Focused tests for AURA's coding/game pipeline routing and approval gates."""
from __future__ import annotations

import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from aura_master_pipeline import AuraMasterPipeline, PipelineDomain


class PipelineRoutingTests(unittest.TestCase):
    def test_domain_routing_defaults_to_coding_and_limits_fanout(self) -> None:
        pipeline = AuraMasterPipeline()
        self.assertEqual(pipeline._determine_domain("help me build a project"), PipelineDomain.CODERX)
        self.assertEqual(pipeline._determine_domain("make a Godot racing game"), PipelineDomain.GAME_DEV)
        self.assertEqual(pipeline._determine_domain("write code for a game"), PipelineDomain.FULL_STACK)
        self.assertEqual(pipeline._determine_domain("generate concept art"), PipelineDomain.MEDIA_STUDIO)
        self.assertEqual(pipeline._determine_domain("run everything"), PipelineDomain.FULL_STACK)
        self.assertEqual(pipeline._determine_domain("run the full pipeline"), PipelineDomain.FULL_STACK)
        self.assertFalse(pipeline._include_media(PipelineDomain.GAME_DEV, {}, "make a video game"))
        self.assertTrue(pipeline._include_media(PipelineDomain.GAME_DEV, {}, "make a game and render concept art"))

    def test_denial_stops_pipeline_before_engine_dispatch(self) -> None:
        pipeline = AuraMasterPipeline()
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_dir = Path(temp_dir) / "runs"
            runs_dir.mkdir()
            with patch("aura_master_pipeline.PIPELINE_RUNS_DIR", runs_dir), patch(
                "aura_permission_system.permission_manager.request_permission",
                return_value={"granted": False, "decision": "DENY"}
            ), patch("coderx_engine.CODERX.run") as code_run:
                result = pipeline.execute("write a simple script")

        self.assertFalse(result["success"])
        self.assertEqual(result["stage"], "failed")
        self.assertEqual(result["domain"], "coderx")
        self.assertEqual(result["results"], {})
        code_run.assert_not_called()

    def test_code_run_does_not_read_telemetry_or_start_optional_media(self) -> None:
        pipeline = AuraMasterPipeline()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            runs_dir = root / "runs"
            runs_dir.mkdir()

            def write_code(goal: str, target_filename: str, max_iterations: int) -> dict:
                target = workspace / target_filename
                target.write_text("print('ok')\n", encoding="utf-8")
                return {"success": True, "target_file": str(target)}

            media_module = types.ModuleType("aura_media_engine")
            media_module.AURA_CINEMA = types.SimpleNamespace(
                create_cinematic_image=lambda *args, **kwargs: self.fail("media should be opt-in"),
                create_cinematic_video=lambda *args, **kwargs: self.fail("media should be opt-in")
            )
            with (
                patch("aura_master_pipeline.WORKSPACE_DIR", workspace),
                patch("aura_master_pipeline.PIPELINE_RUNS_DIR", runs_dir),
                patch("aura_permission_system.permission_manager.request_permission", return_value={"granted": True}),
                patch("coderx_engine.CODERX.run", side_effect=write_code),
                patch.dict("sys.modules", {"aura_media_engine": media_module}),
                patch("aura_os_controller.laptop_controller.get_system_telemetry") as telemetry
            ):
                result = pipeline.execute("create a useful helper script")

        self.assertTrue(result["success"])
        self.assertEqual(result["domain"], "coderx")
        self.assertEqual(set(result["results"]), {"coderx_engine"})
        self.assertEqual(result["system_snapshot"]["status"], "NOT_REQUESTED")
        telemetry.assert_not_called()

    def test_game_run_dispatches_only_game_engine_without_media(self) -> None:
        pipeline = AuraMasterPipeline()
        with tempfile.TemporaryDirectory() as temp_dir:
            game_path = Path(temp_dir) / "playable.html"
            game_path.write_text("game", encoding="utf-8")
            runs_dir = Path(temp_dir) / "runs"
            runs_dir.mkdir()

            godot_module = types.ModuleType("godot_engine_manager")
            godot_module.GodotCarCraftingProjectBuilder = types.SimpleNamespace(
                build_project=lambda name: {"success": True, "playable_3d_web": str(game_path)}
            )
            godot_module.AURA_GODOT_TRAINER = types.SimpleNamespace(
                train_and_verify=lambda name: {"success": True}
            )
            with (
                patch("aura_master_pipeline.PIPELINE_RUNS_DIR", runs_dir),
                patch("aura_permission_system.permission_manager.request_permission", return_value={"granted": True}),
                patch.dict("sys.modules", {"godot_engine_manager": godot_module})
            ):
                result = pipeline.execute("make a Godot racing game")

        self.assertTrue(result["success"])
        self.assertEqual(result["domain"], "game_dev")
        self.assertEqual(set(result["results"]), {"game_engine"})
        self.assertNotIn("media_engine", result["results"])

    def test_invalid_domain_fails_without_requesting_permission(self) -> None:
        pipeline = AuraMasterPipeline()
        with patch("aura_permission_system.permission_manager.request_permission") as request_permission:
            result = pipeline.execute("write a script", domain="unrecognized")
        self.assertFalse(result["success"])
        self.assertIn("Unsupported pipeline domain", result["error"])
        request_permission.assert_not_called()


class ExplicitPermissionTests(unittest.TestCase):
    def test_required_approval_is_not_bypassed_by_full_autonomous_mode(self) -> None:
        from aura_permission_system import SecurityMode, permission_manager

        original_mode = permission_manager.security_mode
        signature = "pipeline_execute:approval-test"
        permission_manager.session_allowlist.discard(signature)
        permission_manager.security_mode = SecurityMode.FULL_AUTONOMOUS
        result = {}

        def request() -> None:
            result.update(permission_manager.request_permission(
                "pipeline_execute",
                "approval-test",
                timeout=3.0,
                require_approval=True
            ))

        worker = threading.Thread(target=request)
        try:
            worker.start()
            deadline = time.time() + 1.0
            pending = []
            while time.time() < deadline and not pending:
                pending = permission_manager.get_pending()
                time.sleep(0.01)
            self.assertTrue(pending, "explicit approval should create a pending request")
            self.assertTrue(permission_manager.respond_request(pending[0]["id"], "ALLOW_ONCE"))
            worker.join(timeout=1.0)
            self.assertFalse(worker.is_alive())
            self.assertTrue(result["granted"])
            self.assertEqual(result["decision"], "ALLOW_ONCE")
        finally:
            if worker.is_alive():
                worker.join(timeout=3.5)
            permission_manager.security_mode = original_mode

    def test_required_approval_ignores_cached_allowlist_and_does_not_cache_allow_always(self) -> None:
        from aura_permission_system import permission_manager

        action_type = "pipeline_execute"
        target = "cached-approval-test"
        signature = f"{action_type}:{target}"
        permission_manager.session_allowlist.add(signature)
        result = {}

        def request() -> None:
            result.update(permission_manager.request_permission(
                action_type,
                target,
                timeout=3.0,
                require_approval=True
            ))

        worker = threading.Thread(target=request)
        try:
            worker.start()
            deadline = time.time() + 1.0
            pending = []
            while time.time() < deadline and not pending:
                pending = [
                    item for item in permission_manager.get_pending()
                    if item["action_type"] == action_type and item["target"] == target
                ]
                time.sleep(0.01)
            self.assertTrue(pending, "cached permission must not suppress a required approval")
            permission_manager.session_allowlist.discard(signature)
            self.assertTrue(permission_manager.respond_request(pending[0]["id"], "ALLOW_ALWAYS"))
            worker.join(timeout=1.0)
            self.assertFalse(worker.is_alive())
            self.assertTrue(result["granted"])
            self.assertEqual(result["decision"], "ALLOW_ALWAYS")
            self.assertNotIn(signature, permission_manager.session_allowlist)
        finally:
            if worker.is_alive():
                worker.join(timeout=3.5)
            permission_manager.session_allowlist.discard(signature)


class OsControllerConsentTests(unittest.TestCase):
    def test_denial_prevents_laptop_file_and_process_side_effects(self) -> None:
        from aura_os_controller import LaptopController

        controller = LaptopController()
        denied = {"granted": False, "decision": "DENY"}
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "must_not_be_written.txt"
            with (
                patch.object(controller.pm, "request_permission", return_value=denied) as request,
                patch("aura_os_controller.subprocess.run") as run
            ):
                write_result = controller.write_file(str(target), "no")
                ps_result = controller.execute_powershell("echo should-not-run")
                controller.kill_process("1234")

        self.assertFalse(write_result["success"])
        self.assertFalse(target.exists())
        self.assertFalse(ps_result["success"])
        run.assert_not_called()
        self.assertEqual(request.call_count, 3)
        self.assertTrue(all(call.kwargs["require_approval"] for call in request.call_args_list))


class WorkspaceBoundaryTests(unittest.TestCase):
    def test_coderx_rejects_targets_outside_its_workspace(self) -> None:
        from coderx_engine import CoderXStateGraph

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            result = CoderXStateGraph(workspace=workspace).run("do not run", "../outside.py")
            self.assertFalse(result["success"])
            self.assertEqual(result["status"], "INVALID_TARGET_PATH")
            self.assertFalse((Path(temp_dir) / "outside.py").exists())

    def test_godot_builder_rejects_projects_outside_game_workspace(self) -> None:
        from godot_engine_manager import GodotCarCraftingProjectBuilder

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "games"
            with patch("godot_engine_manager.GAMES_WORKSPACE", workspace):
                result = GodotCarCraftingProjectBuilder.build_project("../outside")
            self.assertFalse(result["success"])
            self.assertIn("inside AURA's game workspace", result["error"])
            self.assertFalse((Path(temp_dir) / "outside").exists())


if __name__ == "__main__":
    unittest.main()
