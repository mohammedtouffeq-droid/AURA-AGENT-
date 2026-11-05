"""
===================================================================================
                AURA PRODUCTION CERTIFICATION & AUDIT SUITE
===================================================================================
Comprehensive verification tests covering:
1. Fixed Server Port 5050 & Endpoint Availability
2. Production Security Sandbox (PathGuard & Destructive Command Interception)
3. Request-Review Mode vs Auto-Pilot Mode
4. Multimodal Generative Tools (Image & Video Generation)
5. Hardware Automation & Sub-second Live Weather Telemetry
6. Autonomous Offline Intelligence Resilience (Zero-Key Air-Gapped Test)
7. Multi-Tenant SQLite Database Project & Thread Management
===================================================================================
"""
import os
import sys
import unittest
import threading
import time
import json
import urllib.request
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import aura_db
import aura_agent
from aura_brain import (
    validate_safe_path,
    is_safe_command,
    tool_execute_shell,
    tool_write_file,
    tool_read_file,
    tool_get_weather,
    tool_generate_image,
    tool_generate_video,
    tool_open_browser,
    tool_gui_click_and_type,
    tool_windows_app_control,
    tool_parse_screen_ui,
    tool_browser_action,
    tool_screen_grounding_coordinates,
    tool_mem0_persistent_memory,
    tool_whatsapp_manager,
    tool_instagram_manager,
    tool_github_manager,
    tool_hyperbrowser_session,
    tool_markitdown_convert,
    tool_media_extract_ytdlp,
    tool_scrcpy_mobile_bridge,
    tool_autogpt_recursive_planner,
    tool_powertoys_ocr,
    tool_hermes_structured_agent,
    tool_autonomous_code_loop,
    AuraBrain,
    SAFE_WORKSPACE_ROOTS,
    STRICTLY_FORBIDDEN_PATHS
)
from aura_web import AuraWebHandler, make_server


class TestAuraProductionCertification(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Start a local test server instance
        cls.test_port = 5051
        cls.server = make_server("127.0.0.1", cls.test_port)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    # -----------------------------------------------------------------------------
    # 1. FIXED SERVER & ENDPOINTS
    # -----------------------------------------------------------------------------
    def test_01_server_serves_index_html(self):
        url = f"http://127.0.0.1:{self.test_port}/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("AURA Core", content)
            self.assertIn("sidebar-section-switcher", content)

    def test_02_safety_status_endpoint(self):
        url = f"http://127.0.0.1:{self.test_port}/api/system/safety_status"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertTrue(data.get("success"))
            self.assertTrue(data.get("command_filter_active"))
            self.assertIn("tool_generate_image", data.get("multimodal_tools", []))

    def test_03_projects_endpoint(self):
        url = f"http://127.0.0.1:{self.test_port}/api/projects"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertTrue(data.get("success"))
            self.assertIsInstance(data.get("projects"), list)

    # -----------------------------------------------------------------------------
    # 2. PRODUCTION SECURITY SANDBOX (PathGuard)
    # -----------------------------------------------------------------------------
    def test_04_sandbox_blocks_windows_system_access(self):
        with self.assertRaises(PermissionError):
            validate_safe_path("C:/Windows/System32/cmd.exe")

    def test_05_sandbox_blocks_program_files(self):
        with self.assertRaises(PermissionError):
            validate_safe_path("C:/Program Files/malicious_tool.exe")

    def test_06_sandbox_blocks_path_traversal(self):
        with self.assertRaises(PermissionError):
            validate_safe_path("../../../Windows/System32/drivers/etc/hosts")

    def test_07_safe_workspace_path_allowed(self):
        safe_path = Path(__file__).resolve().parent / "workspace" / "test_file.txt"
        validated = validate_safe_path(str(safe_path), allow_create=True)
        self.assertEqual(validated, safe_path)

    # -----------------------------------------------------------------------------
    # 3. POWERSHELL COMMAND GUARD & REQUEST-REVIEW MODE
    # -----------------------------------------------------------------------------
    def test_08_command_guard_blocks_format_disk(self):
        is_safe, reason = is_safe_command("format C: /fs:ntfs")
        self.assertFalse(is_safe)
        self.assertIn("Potentially destructive", reason)

    def test_09_command_guard_blocks_recursive_rmdir(self):
        is_safe, _ = is_safe_command("rmdir /s /q C:\\")
        self.assertFalse(is_safe)

    def test_10_command_guard_allows_safe_commands(self):
        is_safe, _ = is_safe_command("Get-Process | Select-Object -First 5")
        self.assertTrue(is_safe)

    def test_11_request_review_mode_pauses_unapproved_shell(self):
        res = tool_execute_shell("Get-Date", permission_mode="request_review", approved=False)
        self.assertFalse(res.get("success"))
        self.assertTrue(res.get("requires_approval"))

    def test_12_request_review_mode_allows_approved_shell(self):
        res = tool_execute_shell("echo 'Authorized by User'", permission_mode="request_review", approved=True)
        self.assertTrue(res.get("success"))
        self.assertIn("Authorized by User", res.get("stdout", ""))

    # -----------------------------------------------------------------------------
    # 4. MULTIMODAL GENERATIVE TOOLS (Image & Video)
    # -----------------------------------------------------------------------------
    def test_13_multimodal_image_generation(self):
        res = tool_generate_image("A futuristic holographic user interface with glowing nodes", aspect_ratio="1:1")
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("action"), "generated_image")
        self.assertTrue(Path(res.get("file_path")).exists())

    def test_14_multimodal_video_generation(self):
        res = tool_generate_video("Cybersecurity agent running neural packet inspection", duration_sec=3)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("action"), "generated_video")
        self.assertTrue(Path(res.get("video_player_path")).exists())
        self.assertTrue(Path(res.get("video_meta_path")).exists())

    # -----------------------------------------------------------------------------
    # 5. HARDWARE AUTOMATION & LIVE WEATHER TELEMETRY
    # -----------------------------------------------------------------------------
    def test_15_live_weather_telemetry(self):
        res = tool_get_weather("Hyderabad")
        self.assertTrue(res.get("success"))
        self.assertIn("°C", res.get("temperature", ""))

    def test_16_browser_launch_tool(self):
        res = tool_open_browser("google.com")
        self.assertTrue(res.get("success"))
        self.assertIn("https://google.com", res.get("url", ""))

    def test_20_live_news_lookup(self):
        from aura_brain import tool_get_news
        res = tool_get_news("technology")
        self.assertTrue(res.get("success"))
        self.assertGreater(res.get("total_articles", 0), 0)

    # -----------------------------------------------------------------------------
    # 6. AUTONOMOUS OFFLINE REAC LOOP RESILIENCE (Zero-Key Test)
    # -----------------------------------------------------------------------------
    def test_17_autonomous_brain_offline_weather_react(self):
        brain = AuraBrain()
        brain.api_key = "" # Simulate offline environment
        reply = brain.think_and_act("What is the current weather in Hyderabad?")
        self.assertIsNotNone(reply)
        tools_executed = [t["name"] for t in brain.last_tools]
        self.assertIn("tool_get_weather", tools_executed)

    def test_18_autonomous_brain_offline_image_react(self):
        brain = AuraBrain()
        brain.api_key = ""
        reply = brain.think_and_act("Generate image of a high tech futuristic server room")
        self.assertIsNotNone(reply)
        tools_executed = [t["name"] for t in brain.last_tools]
        self.assertIn("tool_generate_image", tools_executed)

    def test_21_autonomous_brain_offline_news_react(self):
        brain = AuraBrain()
        brain.api_key = ""
        reply = brain.think_and_act("Open chrome on my screen and type about todays news")
        self.assertIsNotNone(reply)
        tools_executed = [t["name"] for t in brain.last_tools]
        self.assertIn("tool_get_news", tools_executed)
        self.assertIn("Today's Real-Time Breaking News", reply)

    # -----------------------------------------------------------------------------
    # 7. MULTI-TENANT SQLITE PROJECTS & THREADS CRUD
    # -----------------------------------------------------------------------------
    def test_19_projects_db_lifecycle(self):
        user_id = 9999
        proj = aura_db.create_user_project(
            user_id,
            "Certification Core Project",
            "AURA Tech Inc",
            "Python",
            "c:/Users/hp/cyberheist",
            "Audit verification workspace"
        )
        self.assertIsNotNone(proj.get("id"))
        proj_id = proj["id"]

        projects = aura_db.get_user_projects(user_id)
        self.assertTrue(any(p["id"] == proj_id for p in projects))

        aura_db.pin_user_project(user_id, proj_id, True)
        projects = aura_db.get_user_projects(user_id)
        self.assertTrue(any(p["id"] == proj_id and p["is_pinned"] == 1 for p in projects))

        aura_db.rename_user_project(user_id, proj_id, "Renamed Core Project")
        projects = aura_db.get_user_projects(user_id)
        self.assertTrue(any(p["id"] == proj_id and p["name"] == "Renamed Core Project" for p in projects))

        aura_db.delete_user_project(user_id, proj_id)
        projects = aura_db.get_user_projects(user_id)
        self.assertFalse(any(p["id"] == proj_id for p in projects))

    # -----------------------------------------------------------------------------
    # 8. GUI & WINDOWS DESKTOP AUTOMATION TOOLS
    # -----------------------------------------------------------------------------
    def test_22_tool_gui_click_and_type(self):
        res = tool_gui_click_and_type("click", x=500, y=400)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("action"), "click")
        self.assertEqual(res.get("x"), 500)
        self.assertEqual(res.get("y"), 400)

    def test_23_tool_windows_app_control(self):
        # Test invalid app rejection
        res_invalid = tool_windows_app_control("dangerous_trojan", "open")
        self.assertFalse(res_invalid.get("success"))
        self.assertIn("not allowed", res_invalid.get("error", "").lower())

        # Test valid app registry
        res_calc = tool_windows_app_control("calc", "open")
        self.assertTrue(res_calc.get("success"))
        self.assertEqual(res_calc.get("app"), "calc")

    def test_24_tool_parse_screen_ui(self):
        res = tool_parse_screen_ui()
        self.assertTrue(res.get("success"))
        self.assertIn("resolution", res)
        self.assertGreater(res.get("screen_width", 0), 0)
        self.assertGreater(res.get("screen_height", 0), 0)

    def test_25_engine_mesh_catalog_63(self):
        engines = aura_agent.AURA_AGENT.get_engine_list()
        self.assertEqual(len(engines), 63)
        engine_keys = [e["key"] for e in engines]
        expected_all = [
            "hyperbrowser", "whatsapp-web.js", "instaloader", "PyGithub", "undetected-chromedriver",
            "ShowUI", "midscene", "owl", "OSWorld-G", "self-operating-computer",
            "pywinauto", "pyautogui", "mem0", "Qwen-Agent", "llama.cpp",
            "Agent-S", "UI-TARS-desktop", "OmniParser", "UFO", "terminator",
            "markitdown", "yt-dlp", "scrcpy", "AutoGPT", "hermes-agent", "PowerToys"
        ]
        for expected in expected_all:
            self.assertIn(expected, engine_keys)

    def test_26_tool_browser_action(self):
        res = tool_browser_action(action="verify", url="https://example.com", expected_text="Example")
        self.assertTrue(res.get("success"))
        self.assertIn("verified", res)

    def test_27_tool_screen_grounding_coordinates(self):
        res = tool_screen_grounding_coordinates("center")
        self.assertTrue(res.get("success"))
        self.assertIn("grounded_x", res)
        self.assertIn("grounded_y", res)
        self.assertGreater(res.get("grounded_x"), 0)
        self.assertGreater(res.get("grounded_y"), 0)

    def test_28_tool_mem0_persistent_memory(self):
        # Store memory
        res_store = tool_mem0_persistent_memory(action="store", key="test_code_pref", value="TypeScript + Python", category="coding")
        self.assertTrue(res_store.get("success"))
        self.assertEqual(res_store.get("action"), "stored")

        # Recall memory
        res_recall = tool_mem0_persistent_memory(action="recall", key="test_code_pref")
        self.assertTrue(res_recall.get("success"))
        self.assertGreater(res_recall.get("total_facts", 0), 0)

    # -----------------------------------------------------------------------------
    # 9. GROUP 1 SOCIAL & SECURITY JAIL GATEKEEPER TESTS
    # -----------------------------------------------------------------------------
    def test_29_security_jail_blocks_unauthorized_whatsapp(self):
        # Strict jail mode blocks unauthorized WhatsApp message sending
        res = tool_whatsapp_manager(
            action="send_message",
            contact="1234567890",
            message="Test unapproved message",
            permission_mode="request_review",
            approved=False
        )
        self.assertFalse(res.get("success"))
        self.assertTrue(res.get("requires_approval"))
        self.assertTrue(res.get("security_jail"))
        self.assertIn("SECURITY JAIL", res.get("message", ""))

    def test_30_security_jail_blocks_unauthorized_instagram(self):
        # Strict jail mode blocks unauthorized Instagram DM
        res = tool_instagram_manager(
            action="send_dm",
            username="test_user",
            reply_text="Test unapproved DM",
            permission_mode="request_review",
            approved=False
        )
        self.assertFalse(res.get("success"))
        self.assertTrue(res.get("requires_approval"))
        self.assertTrue(res.get("security_jail"))

    def test_31_security_jail_blocks_unauthorized_gui_click(self):
        # Strict jail mode blocks unauthorized mouse clicking
        res = tool_gui_click_and_type(
            action="click",
            x=500,
            y=400,
            permission_mode="request_review",
            approved=False
        )
        self.assertFalse(res.get("success"))
        self.assertTrue(res.get("requires_approval"))
        self.assertTrue(res.get("security_jail"))

    def test_32_auto_pilot_allows_execution(self):
        # In 0-permission auto-pilot mode, action executes without blocking
        res = tool_gui_click_and_type(
            action="click",
            x=500,
            y=400,
            permission_mode="auto_pilot",
            approved=False
        )
        self.assertTrue(res.get("success"))
        self.assertFalse(res.get("requires_approval", False))

    def test_33_github_manager_inspects_repos(self):
        res = tool_github_manager(
            action="inspect_my_repos",
            user_login="mohammedtouffeq-droid"
        )
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("user"), "mohammedtouffeq-droid")

    def test_34_tool_markitdown_convert(self):
        # Create a temporary workspace file and convert it
        sample_doc = ROOT / "workspace" / "audit_test.csv"
        sample_doc.parent.mkdir(exist_ok=True)
        sample_doc.write_text("Engine,Stars,Status\nMarkItDown,192000,Active\nyt-dlp,200000,Active\n", encoding="utf-8")
        res = tool_markitdown_convert("workspace/audit_test.csv")
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("engine"), "microsoft/markitdown")
        self.assertIn("MarkItDown", res.get("markdown_preview", ""))

    def test_35_tool_media_extract_ytdlp_security_and_execution(self):
        # In request_review mode without approval, blocked by security jail
        blocked = tool_media_extract_ytdlp(
            url="https://www.youtube.com/watch?v=sample",
            extract_audio=True,
            permission_mode="request_review",
            approved=False
        )
        self.assertFalse(blocked.get("success"))
        self.assertTrue(blocked.get("requires_approval"))
        self.assertTrue(blocked.get("security_jail"))

        # In auto_pilot mode, executes cleanly
        allowed = tool_media_extract_ytdlp(
            url="https://www.youtube.com/watch?v=sample",
            extract_audio=True,
            permission_mode="auto_pilot"
        )
        self.assertTrue(allowed.get("success"))
        self.assertEqual(allowed.get("engine"), "yt-dlp/yt-dlp")

    def test_36_tool_scrcpy_mobile_bridge(self):
        # Device status inspection
        status = tool_scrcpy_mobile_bridge(action="device_status")
        self.assertTrue(status.get("success"))
        self.assertEqual(status.get("engine"), "Genymobile/scrcpy")

        # Security jail blocks unauthorized tap in review mode
        blocked = tool_scrcpy_mobile_bridge(
            action="tap",
            command="tap 500 500",
            permission_mode="request_review",
            approved=False
        )
        self.assertFalse(blocked.get("success"))
        self.assertTrue(blocked.get("requires_approval"))

    def test_37_tool_autogpt_recursive_planner(self):
        res = tool_autogpt_recursive_planner(goal="Construct autonomous trading bot with risk limits")
        self.assertTrue(res.get("success"))
        plan = res.get("plan", {})
        self.assertEqual(plan.get("engine"), "Significant-Gravitas/AutoGPT")
        self.assertGreaterEqual(len(plan.get("milestones", [])), 4)

    def test_38_tool_powertoys_ocr(self):
        res = tool_powertoys_ocr(screen_crop=False)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("engine"), "microsoft/PowerToys")

    def test_39_tool_hermes_structured_agent(self):
        res = tool_hermes_structured_agent("Decide next step for web automation")
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("engine"), "NousResearch/hermes-agent")
        self.assertIn("function_call", res.get("structured_output", {}))

    def test_40_engine_mesh_reports_actual_mount_state(self):
        from aura_engine_mesh import AURA_ENGINE_MESH
        status = AURA_ENGINE_MESH.get_mesh_status()
        self.assertEqual(status["total_engines"], 63)
        self.assertLessEqual(status["awakened_engines"], status["total_engines"])
        self.assertIn(status["status"], {
            "NO_ENGINES_MOUNTED",
            "SOME_ENGINES_MOUNTED",
            "ALL_DECLARED_ENGINES_MOUNTED"
        })
        self.assertEqual(status["supervisor_alive"], status["awakened_engines"] > 0)
        res = AURA_ENGINE_MESH.invoke("aider", "map_repo")
        aider_status = next(engine for engine in status["engines"] if engine["key"] == "aider")
        self.assertEqual(res.get("success"), aider_status["mounted"])

    def test_41_tool_autonomous_code_loop(self):
        from unittest.mock import patch
        from coderx_engine import CODERX
        mock_code = "print('Certified autonomous test passed successfully')\n"
        with patch.object(CODERX.router, "generate", return_value=mock_code):
            res = tool_autonomous_code_loop(
                goal="Build certified autonomous testing script",
                target_filename="auto_cert_test.py",
                max_iterations=3
            )
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("status"), "COMPLETED_WITHOUT_ERRORS")
        self.assertGreaterEqual(res.get("iterations_taken", 0), 1)

    def test_42_api_workspace_tree(self):
        url = f"http://127.0.0.1:{self.test_port}/api/workspace/tree"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertIn("files", data)

    def test_43_api_terminal_exec(self):
        url = f"http://127.0.0.1:{self.test_port}/api/terminal/exec"
        payload = json.dumps({"command": "echo 'IDE Terminal Live'"}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("exit_code"), 0)
            self.assertIn("IDE Terminal Live", data.get("stdout", ""))

    def test_44_api_cyberheist_status(self):
        url = f"http://127.0.0.1:{self.test_port}/api/cyberheist/status"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertTrue(data.get("mounted"))



    def test_45_permission_system_classification(self):
        from aura_permission_system import permission_manager, RiskLevel
        risk_safe = permission_manager.classify_action("read_file", "test.py")
        self.assertEqual(risk_safe, RiskLevel.SAFE)
        risk_crit = permission_manager.classify_action("delete_file", "test.py")
        self.assertEqual(risk_crit, RiskLevel.CRITICAL)
        risk_cmd = permission_manager.classify_action("powershell_exec", "PowerShell", command="Remove-Item -Recurse C:\\temp")
        self.assertEqual(risk_cmd, RiskLevel.CRITICAL)

    def test_46_permission_system_request_safe(self):
        from aura_permission_system import permission_manager
        res = permission_manager.request_permission("read_file", "aura_permission_system.py")
        self.assertTrue(res["granted"])
        self.assertEqual(res["risk"], "SAFE")

    def test_47_permission_system_interactive_approval(self):
        from aura_permission_system import permission_manager
        import threading, time

        def simulate_allow():
            time.sleep(0.3)
            pending = permission_manager.get_pending()
            if pending:
                permission_manager.respond_request(pending[0]["id"], "ALLOW_ONCE")

        threading.Thread(target=simulate_allow, daemon=True).start()
        res = permission_manager.request_permission("delete_file", "c:\\temp\\cert_dummy.txt", timeout=4.0)
        self.assertTrue(res["granted"])
        self.assertEqual(res["decision"], "ALLOW_ONCE")

    def test_48_os_controller_telemetry(self):
        from aura_os_controller import laptop_controller
        telem = laptop_controller.get_system_telemetry()
        self.assertGreater(telem.get("ram_total_gb", 0), 0)
        self.assertEqual(telem.get("status"), "ONLINE")

    def test_49_os_controller_powershell(self):
        import sys
        from aura_os_controller import laptop_controller
        from aura_permission_system import permission_manager
        cmd = "Write-Output 'AURA_CERT_PASS'" if sys.platform == "win32" else "echo 'AURA_CERT_PASS'"

        def approve_request():
            deadline = time.time() + 3.0
            while time.time() < deadline:
                pending = [
                    request for request in permission_manager.get_pending()
                    if request["action_type"] == "powershell_exec" and request["command"] == cmd
                ]
                if pending:
                    permission_manager.respond_request(pending[0]["id"], "ALLOW_ONCE")
                    return
                time.sleep(0.01)

        approver = threading.Thread(target=approve_request, daemon=True)
        approver.start()
        res = laptop_controller.execute_powershell(cmd)
        approver.join(timeout=3.5)
        self.assertTrue(res.get("success"))
        self.assertIn("AURA_CERT_PASS", res.get("stdout", ""))

    def test_50_api_permission_endpoints(self):
        url = f"http://127.0.0.1:{self.test_port}/api/permission/pending"
        req = urllib.request.Request(url)
        with self.assertRaises(urllib.error.HTTPError) as response:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(response.exception.code, 401)

    def test_51_godot_engine_manager_installed(self):
        from godot_engine_manager import AURA_GODOT_MANAGER
        self.assertTrue(AURA_GODOT_MANAGER.is_installed())
        self.assertGreater(AURA_GODOT_MANAGER.get_binary_size_mb(), 100.0)
        self.assertIn("4.3", AURA_GODOT_MANAGER.get_version())

    def test_52_godot_autonomous_training_pipeline(self):
        from godot_engine_manager import AURA_GODOT_TRAINER
        report = AURA_GODOT_TRAINER.train_and_verify("CyberCraft3D")
        self.assertTrue(report.get("success"))
        metrics = report.get("training_metrics", {})
        self.assertGreaterEqual(metrics.get("overall_training_score", 0), 9.0)
        self.assertEqual(report.get("headless_verification", {}).get("error_count"), 0)

    def test_53_master_pipeline_topology(self):
        from aura_master_pipeline import AURA_PIPELINE
        topo = AURA_PIPELINE.get_pipeline_topology()
        self.assertEqual(topo.get("status"), "OPERATIONAL")
        connections = topo.get("connections", {})
        self.assertIn("coderx_engine", connections)
        self.assertIn("media_cinema_engine", connections)
        self.assertIn("game_studio_engine", connections)
        self.assertIn("os_telemetry", connections)
        self.assertTrue(connections["game_studio_engine"].get("godot_installed"))

    def test_54_master_pipeline_execution_game_dev(self):
        from aura_master_pipeline import AURA_PIPELINE
        from aura_permission_system import permission_manager
        from unittest.mock import patch
        with patch.object(permission_manager, "request_permission", return_value={"granted": True, "decision": "ALLOW_ONCE"}):
            res = AURA_PIPELINE.execute(
                goal="Test 3D game generation and validation",
                domain="game_dev",
                params={"project_name": "CyberCraft3D"}
            )
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("stage"), "completed")
        self.assertGreater(len(res.get("artifacts", [])), 0)


if __name__ == "__main__":
    unittest.main()
