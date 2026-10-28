"""
===================================================================================
                     AURA AGENT - KINETIC WEB DESKTOP SERVER
===================================================================================
Lightweight server bridging the holographic kinetic UI directly to AURA's Brain.
Runs out-of-the-box on standard Python with zero external pip dependencies.
Author: Mohammed Touffeq & Antigravity
===================================================================================
"""

import os
import sys
import json
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add current folder to sys.path so aura_brain can be imported
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from aura_brain import AuraBrain
from aura_settings import AuraSettingsManager

BRAIN = AuraBrain()
SETTINGS = AuraSettingsManager()
PORT = 5050


class AuraWebHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: Dict[str, Any], status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index.html"):
            html_file = ROOT / "index.html"
            if html_file.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_file.read_bytes())
            else:
                self.send_error(404, "index.html not found")
        elif self.path == "/api/settings":
            self._send_json(SETTINGS.config)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        try:
            body = json.loads(post_data) if post_data else {}
        except Exception:
            body = {}

        if self.path == "/api/chat":
            prompt = body.get("prompt", "").strip()
            if not prompt:
                self._send_json({"reply": "Please enter an instruction."}, status=400)
                return

            print(f"\n[*] User Instruction via Web UI: '{prompt}'")
            reply = BRAIN.think_and_act(prompt)
            self._send_json({"reply": reply, "status": "completed"})

        elif self.path == "/api/settings":
            # Update settings
            for cat, opts in body.items():
                if cat in SETTINGS.config and isinstance(opts, dict):
                    SETTINGS.config[cat].update(opts)
            SETTINGS.save_settings()
            self._send_json({"success": True, "config": SETTINGS.config})
        else:
            self.send_error(404, "Not Found")


def run():
    server_address = ("127.0.0.1", PORT)
    httpd = HTTPServer(server_address, AuraWebHandler)
    url = f"http://localhost:{PORT}"
    print("=" * 65)
    print("        AURA AGENT - KINETIC HOLOGRAPHIC DESKTOP SERVER")
    print("                 Created by Mohammed Touffeq")
    print("=" * 65)
    print(f"[*] AURA Web UI Server Running at : {url}")
    print("[*] Gemini 3.1 Next-Gen Brain    : ONLINE")
    print("[*] Real Hardware Tool Execution : ACTIVE")
    print("-" * 65)
    
    # Launch default browser automatically
    webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")


if __name__ == "__main__":
    run()
