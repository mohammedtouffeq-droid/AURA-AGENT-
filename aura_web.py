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
import sqlite3
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add current folder to sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from aura_brain import AuraBrain, DB_PATH
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

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index.html") or self.path == "":
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
        elif self.path == "/api/memory":
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT key, value, timestamp FROM memory ORDER BY timestamp DESC")
                rows = c.fetchall()
                conn.close()
                memories = [{"key": r[0], "value": r[1], "updated_at": str(r[2])} for r in rows]
                self._send_json({"success": True, "memories": memories})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
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
            tools_used = getattr(BRAIN, "last_tools", [])
            self._send_json({
                "reply": reply,
                "tools": tools_used,
                "status": "completed"
            })

        elif self.path == "/api/chat/new":
            BRAIN.clear_history()
            self._send_json({"success": True, "message": "Conversation memory reset for new session."})

        elif self.path == "/api/settings":
            for cat, opts in body.items():
                if cat in SETTINGS.config and isinstance(opts, dict):
                    SETTINGS.config[cat].update(opts)
            SETTINGS.save_settings()
            self._send_json({"success": True, "config": SETTINGS.config})

        elif self.path == "/api/memory/delete":
            key_to_del = body.get("key")
            if not key_to_del:
                self._send_json({"success": False, "error": "Missing key"}, status=400)
                return
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("DELETE FROM memory WHERE key = ?", (key_to_del,))
                conn.commit()
                conn.close()
                self._send_json({"success": True, "deleted": key_to_del})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)

        elif self.path == "/api/memory/add":
            key = body.get("key", "").strip()
            val = body.get("value", "").strip()
            if not key or not val:
                self._send_json({"success": False, "error": "Key and value required"}, status=400)
                return
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO memory (key, value) VALUES (?, ?)", (key, val))
                conn.commit()
                conn.close()
                self._send_json({"success": True, "key": key, "value": val})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
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
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")


if __name__ == "__main__":
    run()
