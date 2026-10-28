"""Serve AURA's self-contained kinetic UI as a loopback-only static preview.

The chat/settings API routes from the initial prototype are intentionally disabled.
Use aura_chat.py for Gemini CLI requests; the browser page cannot run local tools.
"""
from __future__ import annotations

import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent
ALLOWED_HOST_NAMES = {"localhost", "127.0.0.1"}


class AuraWebHandler(BaseHTTPRequestHandler):
    server_version = "AURA-Preview"
    sys_version = ""

    def log_message(self, format: str, *args: object) -> None:
        # Keep preview logs concise and avoid echoing prompt-like request bodies.
        print(f"[AURA preview] {self.address_string()} {format % args}")

    def _host_is_local(self) -> bool:
        host = self.headers.get("Host", "").casefold()
        try:
            name, port_text = host.rsplit(":", 1)
            port = int(port_text)
        except (ValueError, TypeError):
            return False
        return (
            name in ALLOWED_HOST_NAMES
            and port == self.server.server_port
            and self.client_address[0] in {"127.0.0.1", "::1"}
        )

    def _send_page(self, page: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'none'; "
            "frame-ancestors 'none'; form-action 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(page)

    def _reject_nonlocal_host(self) -> bool:
        if self._host_is_local():
            return False
        self.send_error(403, "Only localhost preview requests are accepted")
        return True

    def do_GET(self) -> None:
        if self._reject_nonlocal_host():
            return
        route = urlsplit(self.path).path
        if route not in {"/", "/index.html"}:
            self.send_error(404, "Not Found")
            return
        try:
            page = (ROOT / "index.html").read_bytes()
        except OSError:
            self.send_error(404, "index.html not found")
            return
        self._send_page(page)

    def _method_not_allowed(self) -> None:
        self.send_response(405)
        self.send_header("Allow", "GET")
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_POST(self) -> None:
        if self._reject_nonlocal_host():
            return
        self._method_not_allowed()

    def do_OPTIONS(self) -> None:
        if self._reject_nonlocal_host():
            return
        self._method_not_allowed()


def make_server(port: int = 0) -> HTTPServer:
    """Create a loopback-only static preview server."""
    return HTTPServer(("127.0.0.1", port), AuraWebHandler)


def run() -> None:
    httpd = make_server()
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}/"
    print("=" * 65)
    print("        AURA AGENT - KINETIC UI PREVIEW")
    print("=" * 65)
    print(f"[*] Static preview : {url}")
    print("[*] Chat/settings  : disabled in browser; use python aura_chat.py")
    print("[*] Host binding   : loopback only")
    print("[*] Stop server    : Ctrl+C")
    print("-" * 65)

    try:
        webbrowser.open(url)
    except Exception as error:
        print(f"[!] Could not open a browser automatically ({type(error).__name__}); open the URL above.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Preview server stopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()
