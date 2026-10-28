"""Comprehensive integration tests for AURA web server and API endpoints."""
from __future__ import annotations

import json
import threading
import time
import unittest
import urllib.request
from pathlib import Path

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

    def test_get_safety_status(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/system/safety_status")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertTrue(data.get("sandbox_active"))

    def test_get_projects_list(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/projects")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertTrue(data.get("success"))
            self.assertIsInstance(data.get("projects"), list)

    def test_chat_api_post_enabled(self):
        payload = json.dumps({
            "prompt": "What is the weather in Hyderabad?",
            "thread_id": "test_thread",
            "mode": "auto_pilot"
        }).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertEqual(data.get("status"), "completed")
            self.assertIn("reply", data)


if __name__ == "__main__":
    unittest.main()
