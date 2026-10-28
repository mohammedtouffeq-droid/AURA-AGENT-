"""Loopback preview server tests; no Gemini calls or tool execution."""
from __future__ import annotations

import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from aura_web import make_server


class AuraWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = make_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.thread.join(timeout=3)
        cls.server.server_close()

    def test_serves_static_page_with_no_network_connect_policy(self) -> None:
        with urlopen(self.base_url + "/", timeout=3) as response:
            page = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("connect-src 'none'", response.headers["Content-Security-Policy"])
            self.assertIn("AURA — Kinetic Workspace", page)

    def test_rejects_untrusted_host_header(self) -> None:
        port = self.server.server_address[1]
        request = Request(self.base_url + "/", headers={"Host": f"attacker.example:{port}"})
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=3)
        self.assertEqual(error.exception.code, 403)

    def test_chat_api_is_disabled(self) -> None:
        request = Request(
            self.base_url + "/api/chat",
            data=b'{"prompt":"run a command"}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=3)
        self.assertEqual(error.exception.code, 405)

    def test_settings_api_is_disabled(self) -> None:
        request = Request(
            self.base_url + "/api/settings",
            data=b'{"security_and_permissions":{"execution_mode":"auto_pilot"}}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=3)
        self.assertEqual(error.exception.code, 405)


if __name__ == "__main__":
    unittest.main()
