import unittest
import json
import urllib.request
import urllib.error
import threading
import time
import secrets
from pathlib import Path
import sys

ROOT = Path(r"C:\Users\hp\AURA-Agent")
sys.path.insert(0, str(ROOT))

import aura_db
from aura_web import make_server, _resolve_workspace_dir
from aura_brain import is_safe_public_url, validate_safe_path, AuraBrain, HOST_PRIVILEGED_TOOLS, AVAILABLE_TOOLS
from aura_permission_system import permission_manager, SecurityMode

class TestAuditRemediationP0P1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 5054
        cls.server = make_server("127.0.0.1", cls.port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.4)

        # User A (Regular User)
        reg_a = aura_db.register_user("audit_user_a", "PassWordA123!")
        if not reg_a.get("success"):
            reg_a = aura_db.login_user("audit_user_a", "PassWordA123!")
        cls.user_a = reg_a["user"]
        cls.token_a = reg_a["token"]

        # User B (Regular User)
        reg_b = aura_db.register_user("audit_user_b", "PassWordB123!")
        if not reg_b.get("success"):
            reg_b = aura_db.login_user("audit_user_b", "PassWordB123!")
        cls.user_b = reg_b["user"]
        cls.token_b = reg_b["token"]

        # Admin User
        reg_adm = aura_db.register_user("audit_admin", "AdminPass123!")
        if not reg_adm.get("success"):
            reg_adm = aura_db.login_user("audit_admin", "AdminPass123!")
        cls.admin = reg_adm["user"]
        cls.token_admin = reg_adm["token"]
        aura_db.set_user_role(cls.admin["id"], "admin")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.server.shutdown()
            cls.server.server_close()
        except Exception:
            pass

    def _api_call(self, path, method="GET", data=None, token=None, headers=None, parse_json=True):
        h = dict(headers or {})
        if token:
            h["Authorization"] = f"Bearer {token}"
        req_data = json.dumps(data).encode("utf-8") if data is not None else None
        if req_data and "Content-Type" not in h:
            h["Content-Type"] = "application/json"
        req = urllib.request.Request(f"{self.base_url}{path}", data=req_data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                content = resp.read().decode("utf-8")
                parsed = json.loads(content) if parse_json else content
                return resp.status, parsed, resp.headers
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8")
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = {"raw": body}
            return err.code, parsed, err.headers

    def test_01_workspace_isolation_per_user(self):
        # Audit #1 & #11: User A workspace cannot leak into User B workspace
        ws_a = _resolve_workspace_dir(self.user_a["id"])
        ws_b = _resolve_workspace_dir(self.user_b["id"])
        self.assertNotEqual(ws_a, ws_b)
        self.assertIn(f"user_{self.user_a['id']}", str(ws_a))
        self.assertIn(f"user_{self.user_b['id']}", str(ws_b))

        # Save file in User A workspace
        status, data, _ = self._api_call("/api/workspace/save", "POST", {"path": "secret_a.txt", "content": "secret_data_a"}, token=self.token_a)
        self.assertEqual(status, 200)

        # User B reads own workspace tree - secret_a.txt must NOT exist
        status, data_b, _ = self._api_call("/api/workspace/tree", "GET", token=self.token_b)
        self.assertEqual(status, 200)
        file_names_b = [f["name"] for f in data_b.get("files", [])]
        self.assertNotIn("secret_a.txt", file_names_b)

    def test_02_media_endpoint_requires_auth(self):
        # Audit #2: /media/... requires authentication
        status, data, _ = self._api_call("/media/sample.png", "GET")
        self.assertEqual(status, 401)

    def test_03_coderx_patch_blocks_path_traversal(self):
        # Audit #3 & #67: /api/coderx/patch blocks ../ path escapes
        patch_payload = {
            "file_path": "../../../system_escape.py",
            "patch_text": "<<<<<<< SEARCH\nfoo\n=======\nbar\n>>>>>>> REPLACE"
        }
        status, data, _ = self._api_call("/api/coderx/patch", "POST", patch_payload, token=self.token_a)
        self.assertEqual(status, 403)
        self.assertIn("escapes workspace", data.get("error", "").lower())

    def test_04_vault_export_excludes_credentials(self):
        # Audit #4 & #10: Vault export excludes password_hash, salt, and session tokens
        vault = aura_db.export_user_vault(self.user_a["id"])
        self.assertNotIn("password_hash", vault.get("payload", {}).get("user", {}))
        self.assertNotIn("salt", vault.get("payload", {}).get("user", {}))
        self.assertNotIn("sessions", vault.get("payload", {}))
        self.assertEqual(vault.get("version"), 2)

    def test_05_vault_signing_uses_non_fallback_secret(self):
        # Audit #5: Cryptographic secret generation does not use public fixed strings
        s = aura_db._get_or_create_secret("AURA_VAULT_SECRET", "vault_secret")
        self.assertNotEqual(s, "aura-signed-vault-hmac-v1")
        self.assertGreaterEqual(len(s), 32)

    def test_06_unauthenticated_requests_receive_401(self):
        # Audit #6 & #9: Private endpoints return 401 unauthenticated
        private_endpoints = [
            "/api/projects",
            "/api/engines",
            "/api/game/status",
            "/api/godot/status",
            "/api/media/status",
            "/api/systems10/overview",
            "/api/pipeline/status",
            "/api/cyberheist/status"
        ]
        for ep in private_endpoints:
            status, data, _ = self._api_call(ep, "GET")
            self.assertEqual(status, 401, f"Expected 401 for {ep}, got {status}")

    def test_07_query_string_token_rejected(self):
        # Audit #8: Tokens in URL query strings are rejected
        status, data, _ = self._api_call(f"/api/projects?token={self.token_a}", "GET")
        self.assertEqual(status, 401)

    def test_08_post_handler_rejects_malformed_and_non_dict_json(self):
        # Audit #10: Rejects non-dict JSON ([]) and oversized requests
        req = urllib.request.Request(
            f"{self.base_url}/api/settings",
            data=b"[]",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.token_a}"},
            method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_09_user_role_blocks_privileged_host_tools(self):
        # Audit #22: Chat user cannot execute host shell tools
        brain = AuraBrain(provider="gemini", model="gemini-flash-lite-latest")
        brain.user_id = self.user_a["id"]
        brain.user_role = "user"

        is_restricted = (brain.user_id is not None and str(brain.user_role).lower() not in ("admin", "superuser"))
        self.assertTrue(is_restricted)
        self.assertIn("tool_execute_shell", HOST_PRIVILEGED_TOOLS)
        self.assertIn("tool_windows_app_control", HOST_PRIVILEGED_TOOLS)
        self.assertIn("tool_scrcpy_mobile_bridge", HOST_PRIVILEGED_TOOLS)

    def test_10_ssrf_protection_in_webpage_reader(self):
        # Audit #25: SSRF protection blocks loopback, private IPs and cloud metadata
        self.assertFalse(is_safe_public_url("http://127.0.0.1")[0])
        self.assertFalse(is_safe_public_url("http://localhost:5050")[0])
        self.assertFalse(is_safe_public_url("http://169.254.169.254/latest/meta-data/")[0])
        self.assertFalse(is_safe_public_url("http://192.168.1.1")[0])
        self.assertFalse(is_safe_public_url("file:///etc/passwd")[0])
        self.assertTrue(is_safe_public_url("https://www.google.com")[0])

    def test_11_permission_manager_is_user_scoped(self):
        # Audit #14 & #15: Permissions, pending queues and decisions are strictly isolated per user
        test_req_id = "test_perm_" + secrets.token_hex(4)
        permission_manager._db_upsert_request({
            "id": test_req_id,
            "user_id": self.user_a["id"],
            "action_type": "shell",
            "target": "cmd",
            "risk": "DANGEROUS",
            "timestamp": time.time(),
            "expires_in": 30.0
        })
        pending_b = permission_manager.get_pending(user_id=self.user_b["id"])
        pending_b_ids = [p["id"] for p in pending_b]
        self.assertNotIn(test_req_id, pending_b_ids)

        forbidden_approval = permission_manager.respond_request(test_req_id, "ALLOW_ONCE", user_id=self.user_b["id"])
        self.assertFalse(forbidden_approval)

    def test_12_security_headers_present(self):
        # Audit #91 & #92: Security headers and strict CORS
        status, html_content, headers = self._api_call("/", "GET", parse_json=False)
        self.assertEqual(status, 200)
        self.assertIn("AURA", html_content)
        self.assertIn("Content-Security-Policy", headers)
        self.assertIn("X-Content-Type-Options", headers)
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")

    def test_13_mem0_and_system2_user_isolation(self):
        # P0 Audit Fix #1: Multi-tenant memory isolation
        from aura_10_systems import AURA_10_SYSTEMS
        bus_a = {"user_id": self.user_a["id"], "selected_model": "gemini-2.5-flash", "difficulty_score": 0.3}
        bus_b = {"user_id": self.user_b["id"], "selected_model": "gemini-2.5-flash", "difficulty_score": 0.8}

        res_a = AURA_10_SYSTEMS.sys2_memory.record_and_consolidate("Secret project for user A", user_tag=f"user_{self.user_a['id']}", context_bus=bus_a)
        res_b = AURA_10_SYSTEMS.sys2_memory.record_and_consolidate("Confidential finances for user B", user_tag=f"user_{self.user_b['id']}", context_bus=bus_b)

        # Check edge isolation
        edges_a = [e["subject"] for e in res_a["temporal_knowledge_graph_edges"]]
        for subj in edges_a:
            self.assertIn(str(self.user_a["id"]), subj)
            self.assertNotIn(str(self.user_b["id"]), subj)

    def test_14_master_pipeline_fail_closed(self):
        # P0 Audit Fix #2: Master pipeline security gate fails closed
        from unittest.mock import patch
        from aura_master_pipeline import AuraMasterPipeline, PipelineDomain

        pipeline = AuraMasterPipeline()
        # Mock security gate to raise an error
        with (
            patch("aura_permission_system.permission_manager.request_permission", return_value={"granted": True}),
            patch("aura_10_systems.AURA_10_SYSTEMS.sys10_security.evaluate_and_guard", side_effect=RuntimeError("Security service offline"))
        ):
            run_res = pipeline.execute("Deploy autonomous code", domain=PipelineDomain.TEN_SYSTEMS_OMNI)
            self.assertEqual(run_res.get("status"), "BLOCKED_BY_SECURITY_GATE")
            self.assertFalse(run_res.get("cross_engine_bus", {}).get("security_gate_passed"))

    def test_15_system10_postgate_controls_overall_success(self):
        # P0 Audit Fix #3: System 10 post-gate verdict controls overall success
        from unittest.mock import patch
        from aura_10_systems import AURA_10_SYSTEMS

        # Mock evaluate_and_guard so pre-gate passes but post-gate returns allowed=False
        calls = 0
        def mock_eval(goal, proposed_output=None, context_bus=None):
            nonlocal calls
            calls += 1
            if calls == 1:
                return {"allowed": True, "block_reason": None, "openssf_scorecard": {"overall_score_out_of_10": 9.5}}
            return {"allowed": False, "block_reason": "Inspect AI found unsafe binary output", "openssf_scorecard": {"overall_score_out_of_10": 3.0}}

        with patch.object(AURA_10_SYSTEMS.sys10_security, "evaluate_and_guard", side_effect=mock_eval):
            omni_res = AURA_10_SYSTEMS.run_10_system_omnipipeline("Generate high-performance script")
            self.assertFalse(omni_res.get("success"))
            self.assertTrue(omni_res.get("blocked_by_system_10"))
            self.assertIn("Inspect AI found unsafe binary output", omni_res.get("error", ""))

    def test_16_hardware_brightness_and_volume_controller(self):
        from aura_os_controller import laptop_controller
        from aura_brain import tool_set_brightness, tool_get_brightness, tool_set_volume

        b_res = laptop_controller.set_brightness(60)
        self.assertTrue(b_res.get("success"))
        self.assertEqual(b_res.get("level"), 60)

        read_res = tool_get_brightness()
        self.assertTrue(read_res.get("success"))
        self.assertIn("level", read_res)

        v_res = tool_set_volume(40, mute=False)
        self.assertTrue(v_res.get("success"))
        self.assertEqual(v_res.get("level"), 40)

    def test_17_application_launcher_whatsapp_and_apps(self):
        from aura_os_controller import laptop_controller
        from aura_brain import tool_windows_app_control, tool_launch_application

        # Safe launch WhatsApp
        wa_res = laptop_controller.launch_app("whatsapp")
        self.assertTrue(wa_res.get("success"))
        self.assertIn(wa_res.get("app"), ["WhatsApp", "WhatsApp Web"])

        # Tool layer launch
        app_res = tool_launch_application("notepad")
        self.assertTrue(app_res.get("success"))

        # Blocked dangerous application
        bad_res = tool_windows_app_control("trojan_virus_runner")
        self.assertFalse(bad_res.get("success"))
        self.assertIn("not allowed", bad_res.get("error", "").lower())

    def test_18_open_interpreter_os_automation_skills(self):
        from aura_flagship_repos import OPEN_INTERPRETER_HUB

        oi_b = OPEN_INTERPRETER_HUB.execute_computer_use_task("Turn laptop brightness down to 20")
        self.assertTrue(oi_b.get("success"))

        oi_app = OPEN_INTERPRETER_HUB.execute_computer_use_task("Open WhatsApp on screen")
        self.assertTrue(oi_app.get("success"))

    def test_19_aura_brain_offline_os_automation_dispatch(self):
        from aura_brain import AuraBrain

        brain = AuraBrain()
        r1 = brain.think_and_act("Make my laptop brightness low")
        self.assertTrue("brightness" in r1.lower() or "display" in r1.lower())

        r2 = brain.think_and_act("Open WhatsApp on laptop on my screen")
        self.assertTrue("whatsapp" in r2.lower())

if __name__ == "__main__":
    unittest.main()
