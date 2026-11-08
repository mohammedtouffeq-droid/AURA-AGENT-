"""
===================================================================================
                AURA MASTER PIPELINE: UNIFIED MULTI-ENGINE BUS
===================================================================================
Central Nervous System connecting ALL AURA engines into one continuous pipeline:
1. CoderX Enterprise Coding Engine (AST, Code Synthesis, Self-Healing)
2. AURA Cinema Media Engine (FLUX.1, Camera Physics, Alpha Cutout, 24fps Video)
3. AURA Game Engine & Godot 4.3 Studio (VehicleBody3D, JoltPhysics, 3D WebGL Mirror)
4. OS Controller & System Telemetry (Memory, RAM, Execution Safety)

Every user prompt or job travels through:
[INTENT] -> [CONTEXT INGESTION] -> [MULTI-ENGINE EXECUTION] -> [VALIDATION] -> [ARTIFACT SYNTHESIS]
===================================================================================
"""

import os
import sys
import time
import json
import uuid
import tempfile
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT_DIR = Path(__file__).resolve().parent
if os.environ.get("VERCEL") or not os.access(ROOT_DIR, os.W_OK):
    WORKSPACE_DIR = Path(tempfile.gettempdir()) / "aura_workspace"
else:
    WORKSPACE_DIR = ROOT_DIR / "workspace"
PIPELINE_RUNS_DIR = WORKSPACE_DIR / "pipeline_runs"
PIPELINE_RUNS_DIR.mkdir(parents=True, exist_ok=True)


class PipelineDomain(str, Enum):
    FULL_STACK = "full_stack"               # Code + game, with media only when requested
    GAME_DEV = "game_dev"                   # Godot 4 + 3D Physics + Playable WebGL
    MEDIA_STUDIO = "media_studio"           # FLUX.1 + Video + Background Removal
    CODERX = "coderx"                       # AST + Code Generation + Testing
    SYSTEM = "system"                       # Explicit system telemetry request
    OPENHANDS = "openhands"                 # OpenHands Agent Canvas + SWE SDK + Workspaces + Automation
    OPEN_INTERPRETER = "open_interpreter"   # Open Interpreter Rust/Python Computer-Use + ACP/MCP + Skills
    AUTOGPT = "autogpt"                     # AutoGPT AutoPilot + Agents + Marketplace + Visual Builder
    FLAGSHIP_TRINITY = "flagship_trinity"   # Connected A-to-Z: AutoGPT -> OpenHands -> Open Interpreter
    TEN_SYSTEMS_OMNI = "ten_systems_omni"   # 1 AURA = 100 AI: All 10 Systems Connected A-to-Z


class PipelineStage(str, Enum):
    QUEUED = "queued"
    INTENT_ANALYSIS = "intent_analysis"
    AWAITING_APPROVAL = "awaiting_approval"
    CONTEXT_INGESTION = "context_ingestion"
    ENGINE_DISPATCH = "engine_dispatch"
    VALIDATION = "validation"
    SYNTHESIS = "synthesis"
    COMPLETED = "completed"
    FAILED = "failed"


class AuraMasterPipeline:
    """Master single-pipe orchestrator for all AURA subsystems."""

    def __init__(self):
        self.active_runs: Dict[str, Dict[str, Any]] = {}

    def get_pipeline_topology(self) -> Dict[str, Any]:
        """Returns the full connection map of all piped subsystems."""
        # Check CoderX
        try:
            from coderx_engine import ROUTER
            coderx_status = {
                "active": True,
                "gemini_active": bool(ROUTER.gemini_key),
                "ollama_active": ROUTER.is_ollama_available()
            }
        except Exception as e:
            coderx_status = {"active": False, "error": str(e)}

        # Check Media Cinema
        try:
            from aura_media_engine import AURA_CINEMA
            media_status = AURA_CINEMA.get_status()
        except Exception as e:
            media_status = {"active": False, "error": str(e)}

        # Check Game Studio & Godot
        try:
            from aura_game_engine import AURA_GAME_STUDIO
            from godot_engine_manager import AURA_GODOT_MANAGER
            game_status = {
                "game_studio": AURA_GAME_STUDIO.get_status(),
                "godot_installed": AURA_GODOT_MANAGER.is_installed(),
                "godot_version": AURA_GODOT_MANAGER.get_version(),
                "godot_size_mb": AURA_GODOT_MANAGER.get_binary_size_mb()
            }
        except Exception as e:
            game_status = {"active": False, "error": str(e)}

        # Check OS Telemetry
        try:
            from aura_os_controller import laptop_controller
            telemetry = laptop_controller.get_system_telemetry()
        except Exception as e:
            telemetry = {"status": "UNKNOWN", "error": str(e)}

        # Check Flagship Ecosystems (OpenHands, Open Interpreter, AutoGPT)
        try:
            from aura_flagship_repos import get_all_flagship_status
            flagship_status = get_all_flagship_status()
        except Exception as e:
            flagship_status = {"success": False, "error": str(e)}

        return {
            "pipeline_name": "AURA Master Unified Pipeline v3.0 (Flagship Trinity Connected)",
            "status": "OPERATIONAL",
            "bus_type": "Multi-Engine Synchronous & Event-Driven",
            "connections": {
                "coderx_engine": coderx_status,
                "media_cinema_engine": media_status,
                "game_studio_engine": game_status,
                "os_telemetry": telemetry,
                "flagship_trinity_hub": flagship_status,
                "ten_systems_omni_core": self._get_ten_systems_status()
            },
            "supported_domains": [d.value for d in PipelineDomain],
            "total_completed_runs": len(list(PIPELINE_RUNS_DIR.glob("*.json")))
        }

    @staticmethod
    def _get_ten_systems_status() -> Dict[str, Any]:
        try:
            from aura_10_systems import AURA_10_SYSTEMS
            return AURA_10_SYSTEMS.get_overview()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute(self, goal: str, domain: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a job through the unified 5-stage pipeline:
        Stage 1: Intent Routing
        Stage 2: Context Gathering (system telemetry only for the system domain)
        Stage 3: Engine Execution (CoderX, Game, and explicitly requested Media)
        Stage 4: Headless Validation & Quality Check
        Stage 5: Final Synthesis & Delivery
        """
        if not isinstance(goal, str) or not goal.strip():
            return {"success": False, "stage": PipelineStage.FAILED.value, "error": "A non-empty goal is required"}
        if domain is not None and not isinstance(domain, str):
            return {"success": False, "stage": PipelineStage.FAILED.value, "error": "Pipeline domain must be a string"}
        if params is not None and not isinstance(params, dict):
            return {"success": False, "stage": PipelineStage.FAILED.value, "error": "Pipeline params must be an object"}
        if domain:
            try:
                PipelineDomain(domain.lower())
            except ValueError:
                return {"success": False, "stage": PipelineStage.FAILED.value, "error": f"Unsupported pipeline domain: {domain}"}
        params = params or {}
        job_id = f"pipe_{uuid.uuid4().hex[:10]}"
        start_time = time.time()
        selected_domain = self._determine_domain(goal, domain)

        run_record = {
            "job_id": job_id,
            "goal": goal,
            "stage": PipelineStage.QUEUED,
            "timeline": [],
            "results": {},
            "artifacts": [],
            "success": False
        }
        self._log_stage(run_record, PipelineStage.INTENT_ANALYSIS, "Analyzing goal intent and mapping target domain")
        run_record["domain"] = selected_domain.value

        self._log_stage(
            run_record,
            PipelineStage.AWAITING_APPROVAL,
            "Waiting for explicit approval before running this pipeline"
        )
        try:
            from aura_permission_system import permission_manager
            approval = permission_manager.request_permission(
                action_type="pipeline_execute",
                target=f"{selected_domain.value}: {goal.strip()[:160]}",
                details=self._approval_details(selected_domain, params, goal),
                require_approval=True
            )
        except Exception as exc:
            run_record["error"] = f"Permission check failed; pipeline was not started: {exc}"
            return self._finish_run(run_record, start_time, success=False)

        run_record["permission"] = approval
        if not approval.get("granted"):
            run_record["error"] = "Pipeline execution was not approved"
            return self._finish_run(run_record, start_time, success=False)

        # -------------------------------------------------------------
        # STAGE 1: INTENT ROUTING
        # -------------------------------------------------------------
        self._log_stage(run_record, PipelineStage.CONTEXT_INGESTION, f"Routing job to domain: {selected_domain.value}")

        # -------------------------------------------------------------
        # STAGE 2: CONTEXT INGESTION
        # -------------------------------------------------------------
        system_snapshot = {"status": "NOT_REQUESTED", "telemetry_live": False}
        if selected_domain == PipelineDomain.SYSTEM:
            try:
                from aura_os_controller import laptop_controller
                system_snapshot = laptop_controller.get_system_telemetry()
            except Exception as telem_err:
                system_snapshot = {"status": "UNAVAILABLE", "telemetry_live": False, "ram_total_gb": 0.0, "error": str(telem_err)}

        run_record["system_snapshot"] = system_snapshot

        # Cross-System Context Bus: Pre-Execution RouteLLM + Bi-Temporal Memory + Security Gate
        cross_engine_bus = {
            "job_id": job_id,
            "domain": selected_domain.value,
            "handoffs": [],
            "security_gate_passed": False
        }
        try:
            from aura_10_systems import AURA_10_SYSTEMS
            sec_gate = AURA_10_SYSTEMS.sys10_security.evaluate_and_guard(goal)
            allowed = bool(sec_gate.get("allowed", False))
            cross_engine_bus["security_gate_passed"] = allowed
            cross_engine_bus["openssf_score"] = sec_gate.get("openssf_scorecard", {}).get("overall_score_out_of_10", 0.0)
            cross_engine_bus["security_decision"] = sec_gate.get("decision", "BLOCKED")
            if not allowed:
                run_record["status"] = "BLOCKED_BY_SECURITY_GATE"
                run_record["cross_engine_bus"] = cross_engine_bus
                self._log_stage(run_record, PipelineStage.FAILED, f"Master pipeline blocked by Security Core pre-dispatch gate: {sec_gate.get('decision')}")
                run_record["finished_at"] = time.time()
                run_record["duration_sec"] = run_record["finished_at"] - start_time
                return run_record

            route_info = AURA_10_SYSTEMS.sys1_neural.estimate_task_difficulty(goal)
            mem_info = AURA_10_SYSTEMS.sys2_memory.record_and_consolidate(goal, user_tag="master_pipeline")
            cross_engine_bus["routed_model"] = route_info.get("selected_model", {}).get("model_id", "gemini-2.5-flash")
            cross_engine_bus["temporal_edge_id"] = (mem_info.get("temporal_knowledge_graph_edges") or [{}])[0].get("edge_id")
            cross_engine_bus["handoffs"].append({
                "stage": "pre_dispatch_omni_bus",
                "routed_model": cross_engine_bus["routed_model"],
                "temporal_edge_id": cross_engine_bus["temporal_edge_id"]
            })
        except Exception as gate_err:
            # FAIL-CLOSED: Any exception in security gate halts execution
            cross_engine_bus["security_gate_passed"] = False
            cross_engine_bus["security_error"] = str(gate_err)
            run_record["status"] = "BLOCKED_BY_SECURITY_GATE"
            run_record["cross_engine_bus"] = cross_engine_bus
            self._log_stage(run_record, PipelineStage.FAILED, f"Master pipeline fail-closed: security check error: {gate_err}")
            run_record["finished_at"] = time.time()
            run_record["duration_sec"] = run_record["finished_at"] - start_time
            return run_record

        run_record["cross_engine_bus"] = cross_engine_bus

        self._log_stage(run_record, PipelineStage.ENGINE_DISPATCH, "Dispatching tasks across piped engines")

        # -------------------------------------------------------------
        # STAGE 3: MULTI-ENGINE EXECUTION
        # -------------------------------------------------------------
        engine_outputs = {}

        if selected_domain in [PipelineDomain.GAME_DEV, PipelineDomain.FULL_STACK]:
            # Trigger Godot 4.3 Studio & Game Engine
            try:
                from godot_engine_manager import GodotCarCraftingProjectBuilder, AURA_GODOT_TRAINER
                proj_name = params.get("project_name", "CyberCraft3D")
                
                # Build or load project
                build_res = GodotCarCraftingProjectBuilder.build_project(proj_name)
                train_res = AURA_GODOT_TRAINER.train_and_verify(proj_name)
                
                engine_outputs["game_engine"] = {
                    "success": build_res.get("success") is True and train_res.get("success") is True,
                    "project_name": proj_name,
                    "build": build_res,
                    "headless_training": train_res,
                    "playable_web_mirror": build_res.get("playable_3d_web"),
                    "play_store_manifest": build_res.get("play_store_manifest")
                }
                if build_res.get("playable_3d_web"):
                    run_record["artifacts"].append({
                        "type": "playable_game",
                        "path": build_res.get("playable_3d_web"),
                        "title": f"{proj_name} 3D Playable Web Simulator"
                    })
            except Exception as e:
                engine_outputs["game_engine"] = {"success": False, "error": str(e)}

        if self._include_media(selected_domain, params, goal):
            # Trigger AURA Cinema Media Engine
            try:
                from aura_media_engine import AURA_CINEMA
                media_prompt = params.get("media_prompt", f"High-tech realistic concept art for {goal}")
                camera_style = params.get("camera_style", "iphone_16_pro")
                
                # Render FLUX image
                img_res = AURA_CINEMA.create_cinematic_image(media_prompt, camera_style=camera_style)
                
                # Render 24fps promotional MP4 sequence
                video_prompt = params.get("video_prompt", f"Cinematic camera tracking shot of {goal}")
                vid_res = AURA_CINEMA.create_cinematic_video(video_prompt, duration_sec=3, fps=24)
                
                engine_outputs["media_engine"] = {
                    "success": img_res.get("success") is True and vid_res.get("success") is True,
                    "image": img_res,
                    "video": vid_res
                }
                if img_res.get("file_path"):
                    run_record["artifacts"].append({
                        "type": "image",
                        "path": img_res.get("file_path"),
                        "title": "FLUX Cinematic Render"
                    })
                video_path = vid_res.get("video_path") or vid_res.get("mp4_path")
                if video_path:
                    run_record["artifacts"].append({
                        "type": "video",
                        "path": video_path,
                        "title": "24fps MP4 Video Sequence"
                    })
            except Exception as e:
                engine_outputs["media_engine"] = {"success": False, "error": str(e)}

        if selected_domain in [PipelineDomain.CODERX, PipelineDomain.FULL_STACK]:
            # Trigger CoderX Unified Engine
            try:
                from coderx_engine import CODERX
                target_file = params.get("target_file", "pipeline_generated_script.py")
                workspace_root = WORKSPACE_DIR.resolve()
                target_path = (workspace_root / target_file).resolve()
                try:
                    target_file = target_path.relative_to(workspace_root).as_posix()
                except (OSError, ValueError, TypeError):
                    raise ValueError("Target file must stay inside AURA's workspace")
                if target_path == workspace_root:
                    raise ValueError("Target file must name a file inside AURA's workspace")
                coderx_res = CODERX.run(
                    goal=goal,
                    target_filename=target_file,
                    max_iterations=1
                )
                engine_outputs["coderx_engine"] = {
                    "code_output": coderx_res,
                    "success": coderx_res.get("success") is True,
                    "target_file": target_file
                }
                run_record["artifacts"].append({
                    "type": "code",
                    "path": str(WORKSPACE_DIR / target_file),
                    "title": "CoderX Logic Script"
                })
            except Exception as e:
                engine_outputs["coderx_engine"] = {"success": False, "error": str(e)}

        if selected_domain == PipelineDomain.OPENHANDS:
            try:
                from aura_flagship_repos import OPENHANDS_HUB
                oh_res = OPENHANDS_HUB.execute_swe_task(
                    task_prompt=goal,
                    project_name=params.get("project_name", "openhands_pipeline_proj"),
                    canvas_agent=params.get("canvas_agent", "openhands_codeact"),
                    target_file=params.get("target_file")
                )
                engine_outputs["openhands_engine"] = oh_res
            except Exception as e:
                engine_outputs["openhands_engine"] = {"success": False, "error": str(e)}

        if selected_domain == PipelineDomain.OPEN_INTERPRETER:
            try:
                from aura_flagship_repos import OPEN_INTERPRETER_HUB
                oi_res = OPEN_INTERPRETER_HUB.execute_computer_use_task(
                    prompt=goal,
                    skill=params.get("skill", "auto"),
                    harness=params.get("harness", "rust_codex_fast"),
                    model=params.get("model", "gemini-flash-lite-latest"),
                    target_dir=params.get("target_dir")
                )
                engine_outputs["open_interpreter_engine"] = oi_res
            except Exception as e:
                engine_outputs["open_interpreter_engine"] = {"success": False, "error": str(e)}

        if selected_domain == PipelineDomain.AUTOGPT:
            try:
                from aura_flagship_repos import AUTOGPT_HUB
                ag_res = AUTOGPT_HUB.build_and_run_workflow(
                    goal=goal,
                    surface=params.get("surface", "autopilot"),
                    template_id=params.get("template_id"),
                    trigger_type=params.get("trigger_type", "pipeline_bus")
                )
                engine_outputs["autogpt_engine"] = ag_res
            except Exception as e:
                engine_outputs["autogpt_engine"] = {"success": False, "error": str(e)}

        if selected_domain == PipelineDomain.FLAGSHIP_TRINITY:
            try:
                from aura_flagship_repos import run_flagship_trinity_pipeline
                trinity_res = run_flagship_trinity_pipeline(
                    goal=goal,
                    project_name=params.get("project_name", "aura_trinity_mission"),
                    canvas_agent=params.get("canvas_agent", "openhands_codeact"),
                    oi_harness=params.get("harness", "rust_codex_fast")
                )
                engine_outputs["flagship_trinity_engine"] = trinity_res
            except Exception as e:
                engine_outputs["flagship_trinity_engine"] = {"success": False, "error": str(e)}

        if selected_domain == PipelineDomain.TEN_SYSTEMS_OMNI:
            try:
                from aura_10_systems import AURA_10_SYSTEMS
                omni_res = AURA_10_SYSTEMS.run_10_system_omnipipeline(
                    goal=goal,
                    user_tag=params.get("user_tag", "aura_pipeline")
                )
                engine_outputs["ten_systems_omni_engine"] = omni_res
            except Exception as e:
                engine_outputs["ten_systems_omni_engine"] = {"success": False, "error": str(e)}

        run_record["results"] = engine_outputs

        # Record cross-engine handoff chain across executed engines
        executed_engines = list(engine_outputs.keys())
        if len(executed_engines) > 1:
            for idx in range(len(executed_engines) - 1):
                cross_engine_bus["handoffs"].append({
                    "from_engine": executed_engines[idx],
                    "to_engine": executed_engines[idx + 1],
                    "artifacts_shared": len(run_record.get("artifacts", []))
                })

        # -------------------------------------------------------------
        # STAGE 4: VALIDATION
        # -------------------------------------------------------------
        self._log_stage(run_record, PipelineStage.VALIDATION, "Validating cross-engine artifacts and execution integrity")
        has_errors = any(
            isinstance(v, dict) and (v.get("success") is False or "error" in v)
            for v in engine_outputs.values()
        )
        # Fail-closed artifact verification: confirm all declared artifacts exist on disk and are not 0 bytes
        for artifact in run_record.get("artifacts", []):
            art_path = artifact.get("path")
            if art_path:
                p = Path(art_path)
                if not p.exists() or p.stat().st_size == 0:
                    artifact["verified"] = False
                    artifact["error"] = "Artifact file missing or zero bytes on disk"
                    has_errors = True
                else:
                    artifact["verified"] = True
                    artifact["size_bytes"] = p.stat().st_size
        
        # -------------------------------------------------------------
        # STAGE 5: SYNTHESIS & PACKAGING
        # -------------------------------------------------------------
        self._log_stage(run_record, PipelineStage.SYNTHESIS, "Synthesizing master response and persisting run log")
        return self._finish_run(run_record, start_time, success=not has_errors)

    def _determine_domain(self, goal: str, domain_hint: Optional[str] = None) -> PipelineDomain:
        if domain_hint:
            try:
                return PipelineDomain(domain_hint.lower())
            except ValueError:
                pass

        g_lower = goal.lower()
        if any(w in g_lower for w in ["10 systems", "10-system", "100 ai", "omnipipeline", "omni-pipeline", "ten systems"]):
            return PipelineDomain.TEN_SYSTEMS_OMNI
        if any(w in g_lower for w in ["trinity", "flagship pipeline", "all 3 flagship"]):
            return PipelineDomain.FLAGSHIP_TRINITY
        if "openhands" in g_lower or "agent canvas" in g_lower:
            return PipelineDomain.OPENHANDS
        if "open interpreter" in g_lower or "open-interpreter" in g_lower or "open_interpreter" in g_lower:
            return PipelineDomain.OPEN_INTERPRETER
        if "autogpt" in g_lower or "autopilot workflow" in g_lower:
            return PipelineDomain.AUTOGPT
        if any(w in g_lower for w in ["everything", "all engines", "full stack", "full-stack", "full pipeline"]):
            return PipelineDomain.FULL_STACK
        game_requested = any(w in g_lower for w in ["game", "godot", "car", "racing", "craft", "3d", "physics"])
        code_requested = any(w in g_lower for w in ["code", "script", "ast", "python", "bug", "patch", "program"])
        if game_requested and code_requested:
            return PipelineDomain.FULL_STACK
        if game_requested:
            return PipelineDomain.GAME_DEV
        if self._goal_requests_media(goal):
            return PipelineDomain.MEDIA_STUDIO
        if code_requested:
            return PipelineDomain.CODERX
        return PipelineDomain.CODERX

    def _approval_details(self, domain: PipelineDomain, params: Dict[str, Any], goal: str) -> str:
        actions = []
        if domain in [PipelineDomain.CODERX, PipelineDomain.FULL_STACK]:
            target_file = params.get("target_file", "pipeline_generated_script.py")
            actions.append(
                f"generate or update {target_file} in AURA's workspace, then execute the generated file locally for validation (it is not isolated)"
            )
        if domain in [PipelineDomain.GAME_DEV, PipelineDomain.FULL_STACK]:
            project_name = params.get("project_name", "CyberCraft3D")
            actions.append(
                f"write the {project_name} Godot project in AURA's game workspace and run Godot headlessly; project scripts may execute"
            )
        if self._include_media(domain, params, goal):
            actions.append("create image/video files in AURA's workspace")
        if domain == PipelineDomain.SYSTEM:
            actions.append("read system telemetry")
        if not actions:
            actions.append("run the selected pipeline")
        return "AURA will " + "; ".join(actions) + "."

    @staticmethod
    def _include_media(domain: PipelineDomain, params: Dict[str, Any], goal: str) -> bool:
        return (
            domain == PipelineDomain.MEDIA_STUDIO
            or params.get("include_media") is True
            or (
                domain in [PipelineDomain.CODERX, PipelineDomain.GAME_DEV, PipelineDomain.FULL_STACK]
                and AuraMasterPipeline._goal_requests_media(goal)
            )
        )

    @staticmethod
    def _goal_requests_media(goal: str) -> bool:
        normalized = goal.lower()
        return (
            ("video" in normalized and "video game" not in normalized)
            or any(
                word in normalized
                for word in ["image", "photo", "art", "asset", "illustration", "render", "flux", "portrait", "camera"]
            )
        )

    def _finish_run(self, run_record: Dict[str, Any], start_time: float, success: bool) -> Dict[str, Any]:
        run_record["elapsed_seconds"] = round(time.time() - start_time, 3)
        run_record["success"] = success
        run_record["stage"] = PipelineStage.COMPLETED if success else PipelineStage.FAILED
        save_file = PIPELINE_RUNS_DIR / f"{run_record['job_id']}.json"
        try:
            save_file.write_text(json.dumps(run_record, indent=2, default=str), encoding="utf-8")
            run_record["persisted_log"] = str(save_file)
        except Exception as exc:
            run_record["persisted_log_error"] = str(exc)
        return run_record

    def _log_stage(self, record: Dict[str, Any], stage: PipelineStage, message: str) -> None:
        record["stage"] = stage.value
        record["timeline"].append({
            "stage": stage.value,
            "timestamp": round(time.time(), 3),
            "message": message
        })


# Master Singleton Pipeline
AURA_PIPELINE = AuraMasterPipeline()

if __name__ == "__main__":
    print("[*] Initializing AURA Master Pipeline...")
    topo = AURA_PIPELINE.get_pipeline_topology()
    print("[*] Pipeline Topology:", json.dumps(topo, indent=2))
    print("[*] Running Full-Stack E2E Test Pipeline...")
    res = AURA_PIPELINE.execute(
        goal="Autonomous 3D Cyber Racing with photorealistic promo assets and telemetry logic",
        domain="full_stack",
        params={"project_name": "CyberCraft3D"}
    )
    print(f"[*] Pipeline Run Finished: Success={res.get('success')}, Elapsed={res.get('elapsed_seconds')}s")
    print(f"[*] Artifacts Generated: {len(res.get('artifacts', []))}")
