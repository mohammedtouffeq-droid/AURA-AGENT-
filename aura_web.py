"""
===================================================================================
                     AURA AGENT - MULTI-USER WORKSPACE SERVER
===================================================================================
Enterprise-grade HTTP Server supporting:
- Multi-user authentication & token sessions (SQLite aura_workspace.db)
- Isolated threads, renaming, pinning, and message history
- Per-user memory vault & settings management
- Direct Gemini 3.1 ReAct execution loop with hardware tools
- 0.0.0.0 cloud / LAN host binding for universal deployment
Author: AURA Technologies Inc.
===================================================================================
"""

import os
import sys
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add root folder to sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import aura_db
from aura_brain import AuraBrain
from aura_settings import AuraSettingsManager

BRAIN = AuraBrain()
SETTINGS = AuraSettingsManager()
HOST = os.environ.get("AURA_HOST", "0.0.0.0")
PORT = int(os.environ.get("AURA_PORT", 5050))


class AuraWebHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: Dict[str, Any], status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token")
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
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token")
        self.end_headers()

    def _get_auth_user(self) -> Optional[Dict[str, Any]]:
        auth_header = self.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        if not token:
            token = self.headers.get("X-Auth-Token", "").strip()
        if not token:
            # Query param fallback
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            token = qs.get("token", [""])[0]

        if not token:
            return None
        return aura_db.authenticate_token(token)

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path == "/" or path == "/index.html" or path == "":
            html_file = ROOT / "index.html"
            if html_file.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_file.read_bytes())
            else:
                self.send_error(404, "index.html not found")

        elif path == "/api/auth/me":
            user = self._get_auth_user()
            if not user:
                self._send_json({"authenticated": False}, status=401)
            else:
                self._send_json({"authenticated": True, "user": user})

        elif path == "/api/threads":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            threads = aura_db.get_user_threads(user_id)
            self._send_json({"success": True, "threads": threads})

        elif path == "/api/threads/messages":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            thread_id = query.get("thread_id", [""])[0]
            if not thread_id:
                self._send_json({"success": False, "error": "thread_id required"}, status=400)
                return
            messages = aura_db.get_thread_messages(user_id, thread_id)
            self._send_json({"success": True, "messages": messages})

        elif path == "/api/memory":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            memories = aura_db.get_user_memories(user_id)
            self._send_json({"success": True, "memories": memories})

        elif path == "/api/settings":
            user = self._get_auth_user()
            config = dict(SETTINGS.config)
            if user and user.get("settings"):
                config["user_custom"] = user["settings"]
            self._send_json(config)

        elif path == "/api/engines":
            from aura_agent import AuraAgent
            agent_inst = AuraAgent()
            engines = agent_inst.get_engine_list()
            self._send_json({
                "success": True,
                "total_engines": len(engines),
                "total_files": sum(e["files_available"] for e in engines),
                "engines": engines
            })

        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        elif path == "/api/engines/search":
            from aura_agent import AuraAgent
            agent_inst = AuraAgent()
            keyword = body.get("keyword", "")
            target_engine = body.get("engine", None)
            res = agent_inst.search_mesh_code(keyword, target_engine=target_engine)
            self._send_json({"success": True, "results": res})

        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            body = json.loads(post_data) if post_data else {}
        except Exception:
            body = {}

        path = urllib.parse.urlparse(self.path).path

        # 1. AUTH ROUTES
        if path == "/api/auth/register":
            username = body.get("username", "")
            password = body.get("password", "")
            res = aura_db.register_user(username, password)
            status = 200 if res.get("success") else 400
            self._send_json(res, status=status)

        elif path == "/api/auth/login":
            username = body.get("username", "")
            password = body.get("password", "")
            res = aura_db.login_user(username, password)
            status = 200 if res.get("success") else 401
            self._send_json(res, status=status)

        # 2. THREADS ROUTES
        elif path == "/api/threads/new":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            title = body.get("title", "New Session")
            thread = aura_db.create_user_thread(user_id, title)
            self._send_json({"success": True, "thread": thread})

        elif path == "/api/threads/rename":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            thread_id = body.get("thread_id", "")
            new_title = body.get("title", "").strip()
            if not thread_id or not new_title:
                self._send_json({"success": False, "error": "thread_id and title required"}, status=400)
                return
            ok = aura_db.rename_user_thread(user_id, thread_id, new_title)
            self._send_json({"success": ok})

        elif path == "/api/threads/pin":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            thread_id = body.get("thread_id", "")
            is_pinned = body.get("is_pinned", False)
            ok = aura_db.pin_user_thread(user_id, thread_id, is_pinned)
            self._send_json({"success": ok})

        elif path == "/api/threads/delete":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            thread_id = body.get("thread_id", "")
            ok = aura_db.delete_user_thread(user_id, thread_id)
            self._send_json({"success": ok})

        # 3. CHAT DISPATCH
        elif path == "/api/chat":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            prompt = body.get("prompt", "").strip()
            thread_id = body.get("thread_id", "default")
            attachments = body.get("attachments", [])

            if not prompt and not attachments:
                self._send_json({"reply": "Please enter an instruction or attach a file."}, status=400)
                return

            # Save user turn with attachment summary
            display_prompt = prompt
            if attachments:
                att_names = [a.get("name", "attachment") for a in attachments]
                display_prompt += f"\n[📎 {len(attachments)} Attachment(s): {', '.join(att_names)}]"

            aura_db.save_message(user_id, thread_id, "user", display_prompt)

            print(f"[*] AURA Runtime: User {user_id} in thread '{thread_id}' -> '{prompt}' (Attachments: {len(attachments)})")
            reply = BRAIN.think_and_act(prompt, attachments=attachments)
            tools_used = getattr(BRAIN, "last_tools", [])

            # Save assistant response
            aura_db.save_message(user_id, thread_id, "assistant", reply, tools_used)

            self._send_json({
                "reply": reply,
                "tools": tools_used,
                "status": "completed"
            })

        # 4. MEMORY ROUTES
        elif path == "/api/memory/add":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            key = body.get("key", "").strip()
            val = body.get("value", "").strip()
            if not key or not val:
                self._send_json({"success": False, "error": "Key and value required"}, status=400)
                return
            ok = aura_db.save_user_memory(user_id, key, val)
            self._send_json({"success": ok, "key": key, "value": val})

        elif path == "/api/memory/delete":
            user = self._get_auth_user()
            user_id = user["id"] if user else 1
            key = body.get("key", "").strip()
            ok = aura_db.delete_user_memory(user_id, key)
            self._send_json({"success": ok, "deleted": key})

        # 5. SETTINGS ROUTE
        elif path == "/api/settings":
            user = self._get_auth_user()
            if user:
                aura_db.save_user_settings(user["id"], body)
            for cat, opts in body.items():
                if cat in SETTINGS.config and isinstance(opts, dict):
                    SETTINGS.config[cat].update(opts)
            SETTINGS.save_settings()
            self._send_json({"success": True, "config": SETTINGS.config})

        elif path == "/api/engines/search":
            from aura_agent import AuraAgent
            agent_inst = AuraAgent()
            keyword = body.get("keyword", "")
            target_engine = body.get("engine", None)
            res = agent_inst.search_mesh_code(keyword, target_engine=target_engine)
            self._send_json({"success": True, "results": res})

        else:
            self.send_error(404, "Not Found")


def run():
    server_address = (HOST, PORT)
    httpd = HTTPServer(server_address, AuraWebHandler)
    url = f"http://localhost:{PORT}"
    print("=" * 65)
    print("        AURA AGENT - MULTI-USER CLOUD & LOCAL WORKSPACE")
    print("                    AURA Technologies Inc.")
    print("=" * 65)
    print(f"[*] Workspace Server Binding : {HOST}:{PORT}")
    print(f"[*] Local Access URL         : {url}")
    print("[*] Multi-User Auth SQLite   : ACTIVE (aura_workspace.db)")
    print("[*] ReAct Gemini Brain       : READY")
    print("-" * 65)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server shutdown gracefully.")


if __name__ == "__main__":
    run()
