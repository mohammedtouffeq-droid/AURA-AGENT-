"""Comprehensive tests for AURA Sovereign v5: JARVIS Hub, Kill Switch, Reasoning Modes, and Luxury UI."""
from __future__ import annotations

import json
import re
import secrets
import shutil
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import aura_db
import aura_web
from aura_jarvis_hub import JARVIS_HUB
from aura_web import _resolve_workspace_dir, make_server


class TestAuraJarvisCoordinatorUnit(unittest.TestCase):
    def setUp(self):
        self.user_a = f"unit_a_{secrets.token_hex(4)}"
        self.user_b = f"unit_b_{secrets.token_hex(4)}"

    def test_all_four_routines_execute_and_audit(self):
        health = JARVIS_HUB.run_routine(self.user_a, "repo_health_audit")
        self.assertTrue(health["success"])
        tel = health["telemetry"]
        self.assertTrue(tel["syntax_clean"], tel.get("syntax_errors"))
        self.assertTrue(tel["secret_hygiene_clean"], tel.get("hardcoded_secret_hits"))
        self.assertGreaterEqual(tel["python_modules_checked"], 10)

        scan = JARVIS_HUB.run_routine(self.user_a, "security_threat_scan", "upi://pay?pa=fraud@ybl&am=5000")
        self.assertTrue(scan["success"])
        self.assertIn("cyber_forensics", scan)
        self.assertIn("upi_guard", scan)

        ast_rev = JARVIS_HUB.run_routine(self.user_a, "code_ast_review", "aura_jarvis_hub.py")
        self.assertTrue(ast_rev["success"])
        self.assertGreaterEqual(ast_rev["functions"], 5)

        brief = JARVIS_HUB.run_routine(self.user_a, "executive_briefing", "Hyderabad")
        self.assertTrue(brief["success"])
        self.assertEqual(brief["location"], "Hyderabad")
        self.assertIn("workspace_health", brief)

        status = JARVIS_HUB.get_status(self.user_a)
        self.assertEqual(status["runs_completed"], 4)
        self.assertGreaterEqual(len(status["audit_log"]), 4)

    def test_ast_review_blocks_path_escape(self):
        res = JARVIS_HUB.run_routine(self.user_a, "code_ast_review", "../../etc/passwd")
        self.assertFalse(res["success"])
        self.assertIn("escapes", res["error"].lower())

    def test_kill_switch_blocks_execution_and_is_tenant_isolated(self):
        halted_state = JARVIS_HUB.set_kill_switch(self.user_a, halted=True, reason="Emergency Unit Lock")
        self.assertTrue(halted_state["halted"])
        self.assertEqual(halted_state["system_state"], "HALTED_BY_KILL_SWITCH")

        blocked = JARVIS_HUB.run_routine(self.user_a, "repo_health_audit")
        self.assertFalse(blocked["success"])
        self.assertTrue(blocked["halted"])

        # Tenant B remains unaffected and ARMED
        status_b = JARVIS_HUB.get_status(self.user_b)
        self.assertFalse(status_b["halted"])
        res_b = JARVIS_HUB.run_routine(self.user_b, "repo_health_audit")
        self.assertTrue(res_b["success"])

        # Re-arming user A restores execution cleanly
        rearmed = JARVIS_HUB.set_kill_switch(self.user_a, halted=False, reason="All clear")
        self.assertFalse(rearmed["halted"])
        res_a = JARVIS_HUB.run_routine(self.user_a, "repo_health_audit")
        self.assertTrue(res_a["success"])


class TestAuraSovereignHttpAndUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.2)

        cls.user_a = aura_db.register_user(f"sov_a_{secrets.token_hex(4)}", "SovPass123!")
        cls.token_a = cls.user_a["token"]
        cls.uid_a = cls.user_a["user"]["id"]

        cls.user_b = aura_db.register_user(f"sov_b_{secrets.token_hex(4)}", "SovPass123!")
        cls.token_b = cls.user_b["token"]
        cls.uid_b = cls.user_b["user"]["id"]

    @classmethod
    def tearDownClass(cls):
        try:
            cls.server.shutdown()
            cls.server.server_close()
        except Exception:
            pass
        shutil.rmtree(_resolve_workspace_dir(cls.uid_a), ignore_errors=True)
        shutil.rmtree(_resolve_workspace_dir(cls.uid_b), ignore_errors=True)

    def _req(self, path: str, method: str = "GET", token: str = "", body: dict | None = None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(f"{self.base}{path}", data=data, headers=headers, method=method)
        return urllib.request.urlopen(req, timeout=8)

    def test_jarvis_routes_require_auth(self):
        for method, path, body in (
            ("GET", "/api/jarvis/status", None),
            ("POST", "/api/jarvis/run", {"routine": "repo_health_audit"}),
            ("POST", "/api/jarvis/kill_switch", {"halted": True}),
        ):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self._req(path, method=method, body=body)
            self.assertEqual(ctx.exception.code, 401)

    def test_jarvis_http_lifecycle_and_chat_guardrails(self):
        with self._req("/api/jarvis/status", token=self.token_a) as resp:
            st = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(st["success"])
            self.assertFalse(st["halted"])
            self.assertEqual(len(st["routines"]), 4)

        with self._req(
            "/api/jarvis/run",
            method="POST",
            token=self.token_a,
            body={"routine": "code_ast_review", "target": "coderx_engine.py"},
        ) as resp:
            ast_res = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(ast_res["success"])
            self.assertEqual(ast_res["file"], "coderx_engine.py")

        # Engage Kill Switch for User A
        with self._req(
            "/api/jarvis/kill_switch",
            method="POST",
            token=self.token_a,
            body={"halted": True, "reason": "HTTP Integration Halt"},
        ) as resp:
            halt_res = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(halt_res["halted"])

        # Routine execution must return HTTP 423 Locked when halted
        with self.assertRaises(urllib.error.HTTPError) as ctx_locked:
            self._req(
                "/api/jarvis/run",
                method="POST",
                token=self.token_a,
                body={"routine": "repo_health_audit"},
            )
        self.assertEqual(ctx_locked.exception.code, 423)

        # User B stays unaffected and armed
        with self._req("/api/jarvis/status", token=self.token_b) as resp:
            st_b = json.loads(resp.read().decode("utf-8"))
            self.assertFalse(st_b["halted"])

        # /api/chat enforces reasoning_mode framing and downgrades mode to ask_first when halted
        captured = {}

        def _fake_think(self_brain, prompt, **kwargs):
            captured["prompt"] = prompt
            captured["permission_mode"] = kwargs.get("permission_mode")
            captured["temperature"] = getattr(self_brain, "temperature", None)
            self_brain.last_tools = []
            return "## Plan\nVerified safely."

        with mock.patch.object(aura_web.AuraBrain, "think_and_act", _fake_think):
            with self._req(
                "/api/chat",
                method="POST",
                token=self.token_a,
                body={
                    "prompt": "Build an API endpoint",
                    "thread_id": "t_sov_v5",
                    "mode": "auto_pilot",
                    "reasoning_mode": "architect",
                },
            ) as resp:
                chat_res = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(chat_res["status"], "completed")
                self.assertIn("[REASONING MODE: ARCHITECT", captured["prompt"])
                self.assertEqual(captured["permission_mode"], "ask_first")

        # Re-arm cleanly so Verifier mode also works without Kill Switch override
        with self._req(
            "/api/jarvis/kill_switch",
            method="POST",
            token=self.token_a,
            body={"halted": False, "reason": "Re-arm after check"},
        ) as resp:
            rearm_res = json.loads(resp.read().decode("utf-8"))
            self.assertFalse(rearm_res["halted"])

        with mock.patch.object(aura_web.AuraBrain, "think_and_act", _fake_think):
            with self._req(
                "/api/chat",
                method="POST",
                token=self.token_a,
                body={
                    "prompt": "Audit edge cases",
                    "thread_id": "t_sov_v5",
                    "mode": "auto_pilot",
                    "reasoning_mode": "verifier",
                },
            ) as resp:
                self.assertEqual(resp.status, 200)
                self.assertIn("[REASONING MODE: STRICT VERIFIER", captured["prompt"])
                self.assertEqual(captured["permission_mode"], "auto_pilot")
                self.assertLessEqual(captured["temperature"], 0.2)

    def test_frontend_sovereign_v5_dom_and_privacy_cleanliness(self):
        root = Path(__file__).resolve().parent
        html = (root / "index.html").read_text(encoding="utf-8")

        for req_id in (
            'id="reasoningModeSelect"',
            'id="btnGlobalKillSwitch"',
            'id="btnComposerModelMenu"',
            'id="btnComposerJarvis"',
            'id="composerModelPopover"',
            'id="composerJarvisPopover"',
            'id="heroGreetingTitle"',
            'id="artifactSplitPane"',
            'id="artifactPreviewFrame"',
            'id="voiceCallOverlay"',
            'id="voiceCallOrb"',
            'id="jarvisOverlay"',
            'placeholder="Username"',
        ):
            self.assertIn(req_id, html, f"Missing required Sovereign v5 UI marker: {req_id}")

        self.assertIn('sandbox="allow-scripts"', html)
        self.assertNotIn("touffeq", html.lower())
        self.assertNotIn("ahmed_builder", html.lower())

        no_scripts = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S | re.I)
        no_styles = re.sub(r"<style\b[^>]*>.*?</style>", "", no_scripts, flags=re.S | re.I)
        visible_text = re.sub(r"<[^>]+>", " ", no_styles)
        self.assertEqual(len(re.findall(r"BharatCode|Build League", visible_text, flags=re.I)), 0)

    def test_account_dot_username_login_roundtrip_and_offline_datetime(self):
        uname = f"demo.user.{secrets.token_hex(3)}"
        pw = "UserPass99!"
        reg = aura_db.register_user(uname, pw)
        self.assertTrue(reg.get("success"), reg)

        log = aura_db.login_user(uname.upper(), pw)
        self.assertTrue(log.get("success"), log)
        self.assertEqual(log["user"]["username"], uname)

        brain = aura_web._create_user_brain({"id": reg["user"]["id"], "settings": {}})
        out = brain._offline_autonomous_dispatch(
            [{"role": "user", "parts": [{"text": "What is today's time and date?"}]}],
            [],
        )
        txt = out["candidates"][0]["content"]["parts"][0]["text"]
        self.assertNotIn("temporarily slow", txt.lower())
        self.assertIn(str(time.localtime().tm_year), txt)


if __name__ == "__main__":
    unittest.main()
