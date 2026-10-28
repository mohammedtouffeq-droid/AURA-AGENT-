"""Socket-free tests for AURA's static preview request handler."""
from __future__ import annotations

import io
import unittest
from types import SimpleNamespace

from aura_web import AuraWebHandler


class HandlerHarness:
    def __init__(self, route: str = "/", host: str = "127.0.0.1:43210") -> None:
        self.path = route
        self.headers = {"Host": host}
        self.server = SimpleNamespace(server_port=43210)
        self.client_address = ("127.0.0.1", 54321)
        self.status = None
        self.response_headers = {}
        self.wfile = io.BytesIO()
        self.error_message = None

    _host_is_local = AuraWebHandler._host_is_local
    _reject_nonlocal_host = AuraWebHandler._reject_nonlocal_host
    _send_page = AuraWebHandler._send_page
    _method_not_allowed = AuraWebHandler._method_not_allowed

    def send_response(self, status: int) -> None:
        self.status = status

    def send_header(self, name: str, value: str) -> None:
        self.response_headers[name] = value

    def end_headers(self) -> None:
        pass

    def send_error(self, status: int, message: str) -> None:
        self.status = status
        self.error_message = message


class AuraWebTests(unittest.TestCase):
    def test_accepts_only_loopback_host_and_client(self) -> None:
        self.assertTrue(AuraWebHandler._host_is_local(HandlerHarness()))
        self.assertFalse(AuraWebHandler._host_is_local(HandlerHarness(host="attacker.example:43210")))
        remote = HandlerHarness()
        remote.client_address = ("192.0.2.10", 54321)
        self.assertFalse(AuraWebHandler._host_is_local(remote))

    def test_serves_static_page_with_restrictive_headers(self) -> None:
        handler = HandlerHarness()
        AuraWebHandler.do_GET(handler)
        self.assertEqual(handler.status, 200)
        self.assertIn("connect-src 'none'", handler.response_headers["Content-Security-Policy"])
        self.assertEqual(handler.response_headers["X-Frame-Options"], "DENY")
        self.assertIn("AURA — Kinetic Workspace", handler.wfile.getvalue().decode("utf-8"))

    def test_chat_api_post_is_disabled(self) -> None:
        handler = HandlerHarness(route="/api/chat")
        AuraWebHandler.do_POST(handler)
        self.assertEqual(handler.status, 405)
        self.assertEqual(handler.response_headers["Allow"], "GET")

    def test_settings_api_post_is_disabled(self) -> None:
        handler = HandlerHarness(route="/api/settings")
        AuraWebHandler.do_POST(handler)
        self.assertEqual(handler.status, 405)
        self.assertEqual(handler.response_headers["Allow"], "GET")

    def test_unknown_get_route_is_not_served(self) -> None:
        handler = HandlerHarness(route="/api/chat")
        AuraWebHandler.do_GET(handler)
        self.assertEqual(handler.status, 404)


if __name__ == "__main__":
    unittest.main()
