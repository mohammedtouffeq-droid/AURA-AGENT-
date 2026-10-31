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

    def test_model_settings_require_authentication(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/settings")
        with self.assertRaises(urllib.error.HTTPError) as response:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(response.exception.code, 401)

    def test_model_settings_are_user_scoped_and_do_not_expose_secrets(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/settings",
            headers={"Authorization": "Bearer settings-test-token"}
        )
        user = {"id": 42, "settings": {"brain_settings": {
            "active_provider": "ollama",
            "active_model": "qwen2.5-coder:7b"
        }}}
        with (
            patch("aura_db.authenticate_token", return_value=user),
            patch("aura_web.BRAIN.api_key", "server-secret"),
            urllib.request.urlopen(req, timeout=5) as response
        ):
            data = json.loads(response.read().decode())
        self.assertTrue(data["success"])
        self.assertEqual(data["brain_settings"]["active_provider"], "ollama")
        self.assertEqual(data["brain_settings"]["active_model"], "qwen2.5-coder:7b")
        self.assertTrue(data["gemini_key_configured"])
        self.assertNotIn("server-secret", json.dumps(data))

    def test_model_settings_post_validates_and_saves_for_authenticated_user(self):
        payload = json.dumps({
            "active_provider": "ollama",
            "active_model": "qwen2.5-coder:7b"
        }).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/settings",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer settings-test-token"
            },
            method="POST"
        )
        user = {"id": 42, "settings": {"other_preference": "preserved"}}
        with (
            patch("aura_db.authenticate_token", return_value=user),
            patch("aura_db.save_user_settings", return_value=True) as save_settings,
            urllib.request.urlopen(req, timeout=5) as response
        ):
            data = json.loads(response.read().decode())
        self.assertTrue(data["success"])
        self.assertEqual(data["brain_settings"]["active_model"], "qwen2.5-coder:7b")
        saved = save_settings.call_args.args[1]
        self.assertEqual(saved["other_preference"], "preserved")
        self.assertEqual(saved["brain_settings"]["active_provider"], "ollama")

    def test_model_settings_reject_unknown_provider_or_model(self):
        payload = json.dumps({
            "active_provider": "copilot",
            "active_model": "gpt-4o"
        }).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/settings",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer settings-test-token"
            },
            method="POST"
        )
        with (
            patch("aura_db.authenticate_token", return_value={"id": 42, "settings": {}}),
            patch("aura_db.save_user_settings") as save_settings,
            self.assertRaises(urllib.error.HTTPError) as response
        ):
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(response.exception.code, 400)
        save_settings.assert_not_called()

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
            patch("aura_db.authenticate_token", return_value={
                "id": "test-user",
                "settings": {"brain_settings": {
                    "active_provider": "ollama",
                    "active_model": "qwen2.5-coder:7b"
                }}
            }),
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
            brain_type.assert_called_once_with(provider="ollama", model="qwen2.5-coder:7b")


if __name__ == "__main__":
    unittest.main()
