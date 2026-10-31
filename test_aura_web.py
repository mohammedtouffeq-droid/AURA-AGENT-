"""Comprehensive integration tests for AURA web server and API endpoints."""
from __future__ import annotations

import json
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from aura_web import AuraWebHandler, make_server


class AuraWebIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 5052
        cls.server = make_server("127.0.0.1", cls.port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.4)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_get_root_page(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode("utf-8")
            self.assertIn("AURA Core", body)
            self.assertIn("permissionPrompt", body)
            self.assertIn("Allow once", body)

    def test_get_safety_status(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/system/safety_status")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertFalse(data.get("sandbox_active"))
            self.assertTrue(data.get("command_filter_active"))
            self.assertIn("not process isolation", data.get("sandbox_note", ""))

    def test_permission_requests_require_authentication(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/permission/pending")
        with self.assertRaises(urllib.error.HTTPError) as response:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(response.exception.code, 401)

    def test_permission_decisions_require_authentication(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/permission/respond",
            data=json.dumps({"id": "missing", "decision": "ALLOW_ONCE"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as response:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(response.exception.code, 401)

    def test_get_projects_list(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/projects")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertTrue(data.get("success"))
            self.assertIsInstance(data.get("projects"), list)

    def test_chat_api_post_authenticated(self):
        payload = json.dumps({
            "prompt": "What is the weather in Hyderabad?",
            "thread_id": "test_thread",
            "mode": "auto_pilot"
        }).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": "Bearer test-token"},
            method="POST"
        )
        with (
            patch("aura_db.authenticate_token", return_value={"id": "test-user"}),
            patch("aura_db.save_message"),
            patch("aura_db.get_thread_messages", return_value=[]),
            patch("aura_web.AuraBrain") as brain_type
        ):
            brain_type.return_value.think_and_act.return_value = "Stubbed test response"
            brain_type.return_value.last_tools = []
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode())
                self.assertEqual(data.get("status"), "completed")
                self.assertIn("reply", data)


if __name__ == "__main__":
    unittest.main()
