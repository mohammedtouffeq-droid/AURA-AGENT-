"""
===================================================================================
                     AURA AGENT - MULTI-USER WORKSPACE SERVER
===================================================================================
Enterprise-grade HTTP Server supporting:
- Multi-user authentication & token sessions (SQLite aura_workspace.db)
- Isolated threads, renaming, pinning, and message history
- Per-user memory vault & settings management
- Per-user Gemini or local Ollama ReAct execution with tools
- 0.0.0.0 cloud / LAN host binding for universal deployment
Author: AURA Technologies Inc.
===================================================================================
"""

import os
import sys
import json
import urllib.parse
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
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
HOST = os.environ.get("AURA_HOST", "127.0.0.1")
PORT = int(os.environ.get("AURA_PORT", 5050))


def _selected_brain_settings(user: Dict[str, Any]) -> Dict[str, str]:
    user_settings = user.get("settings") or {}
    user_brain = user_settings.get("brain_settings", {}) if isinstance(user_settings, dict) else {}
    provider = user_brain.get(
        "active_provider",
        SETTINGS.config.get("brain_settings", {}).get("active_provider", "gemini")
    )
    model = user_brain.get(
        "active_model",
        SETTINGS.config.get("brain_settings", {}).get("active_model", "gemini-flash-lite-latest")
    )
    if not AuraSettingsManager.validate_model_selection(provider, model):
        provider, model = "gemini", "gemini-flash-lite-latest"
    return {"active_provider": provider, "active_model": model}


def _create_user_brain(user: Dict[str, Any]) -> AuraBrain:
    selected = _selected_brain_settings(user)
    return AuraBrain(provider=selected["active_provider"], model=selected["active_model"])


DEFAULT_ALLOWED_ORIGINS = {
    "http://127.0.0.1:5050",
    "http://localhost:5050",
    "http://127.0.0.1:5051",
    "http://localhost:5051",
    "http://127.0.0.1:5052",
    "http://localhost:5052",
    "https://aura-agent.vercel.app",
    "https://aura-agent-mohammedtouffeq-7681s-projects.vercel.app",
}


def _get_allowed_origins() -> set:
    origins = set(DEFAULT_ALLOWED_ORIGINS)
    extra = os.environ.get("AURA_ALLOWED_ORIGINS", "")
    for item in extra.split(","):
        cleaned = item.strip().rstrip("/")
        if cleaned:
            origins.add(cleaned)
    vercel_url = os.environ.get("VERCEL_URL", "").strip()
    if vercel_url:
        origins.add(f"https://{vercel_url}")
    return origins


class AuraWebHandler(BaseHTTPRequestHandler):
    def _resolve_cors_origin(self) -> str:
        req_origin = (self.headers.get("Origin") or "").strip().rstrip("/")
        allowed = _get_allowed_origins()
        if req_origin and req_origin in allowed:
            return req_origin
        return "http://127.0.0.1:5050"

    def _send_json(self, data: Dict[str, Any], status: int = 200, extra_headers: Optional[List[tuple]] = None):
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", self._resolve_cors_origin())
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token, X-CSRF-Token")
        if extra_headers:
            for h_name, h_val in extra_headers:
                self.send_header(h_name, h_val)
        self.end_headers()
        self.wfile.write(encoded)

    def _build_session_cookie(self, token: str, clear: bool = False) -> str:
        is_https = bool(os.environ.get("VERCEL")) or (self.headers.get("X-Forwarded-Proto", "").lower() == "https")
        secure_attr = "; Secure" if is_https else ""
        if clear:
            return f"aura_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict{secure_attr}"
        return f"aura_session={token}; Path=/; Max-Age=2592000; HttpOnly; SameSite=Strict{secure_attr}"

    def _extract_cookie_token(self) -> str:
        raw_cookie = self.headers.get("Cookie", "")
        if not raw_cookie:
            return ""
        try:
            cookie = SimpleCookie()
            cookie.load(raw_cookie)
            if "aura_session" in cookie:
                return cookie["aura_session"].value.strip()
        except Exception:
            pass
        return ""

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", self._resolve_cors_origin())
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token, X-CSRF-Token")
        self.end_headers()

    def _get_auth_user(self, body: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        auth_header = self.headers.get("Authorization", "")
        token = ""
        used_cookie = False
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        if not token:
            token = self.headers.get("X-Auth-Token", "").strip()
        if not token and body and isinstance(body, dict):
            token = body.get("session_token", "") or body.get("token", "")
        if not token:
            # Query param fallback
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            token = qs.get("token", [""])[0]
        if not token:
            token = self._extract_cookie_token()
            if token:
                used_cookie = True

        if not token:
            return None

        # Enforce CSRF token check on state-changing requests authenticated solely via cookie
        if used_cookie and getattr(self, "command", "GET").upper() == "POST":
            csrf_token = self.headers.get("X-CSRF-Token", "").strip()
            if not csrf_token and body and isinstance(body, dict):
                csrf_token = str(body.get("csrf_token", "")).strip()
            if not aura_db.verify_csrf_token(token, csrf_token):
                return None

        user = aura_db.authenticate_token(token)
        if user:
            user["csrf_token"] = aura_db.compute_csrf_token(token)
        return user

    def _is_authorized_admin(self, body: Optional[Dict[str, Any]] = None) -> bool:
        user = self._get_auth_user(body)
        if user:
            # Strictly database-backed role enforcement. No username bypasses, no self-promotion via settings.
            role = user.get("role", "user")
            if role in ("admin", "superuser"):
                return True
        return False

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path == "/" or path == "/index.html" or path == "":
            html_file = ROOT / "index.html"
            if html_file.exists():
                data = html_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(404, "index.html not found")

        elif path == "/api/auth/me":
            user = self._get_auth_user()
            storage_status = aura_db.get_storage_status()
            if not user:
                self._send_json({"authenticated": False, "storage_status": storage_status}, status=401)
            else:
                self._send_json({
                    "authenticated": True,
                    "user": user,
                    "csrf_token": user.get("csrf_token"),
                    "storage_status": storage_status
                })

        elif path.startswith("/media/"):
            # Serve generated media securely from workspace
            media_rel = path[7:] # strip "/media/"
            ws = ROOT / "workspace"
            target_file = (ws / media_rel).resolve()
            if str(target_file).startswith(str(ws)) and target_file.exists() and target_file.is_file():
                ext = target_file.suffix.lower()
                mime_map = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".webp": "image/webp",
                    ".gif": "image/gif",
                    ".mp4": "video/mp4",
                    ".webm": "video/webm",
                    ".svg": "image/svg+xml"
                }
                content_type = mime_map.get(ext, "application/octet-stream")
                data = target_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Access-Control-Allow-Origin", self._resolve_cors_origin())
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(data)
                return
            else:
                self.send_error(404, "Media file not found")
                return

        elif path == "/api/threads":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Unauthorized", "threads": []}, status=401)
                return
            threads = aura_db.get_user_threads(user["id"])
            self._send_json({"success": True, "threads": threads})

        elif path == "/api/threads/messages":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Unauthorized", "messages": []}, status=401)
                return
            thread_id = query.get("thread_id", [""])[0]
            if not thread_id:
                self._send_json({"success": False, "error": "thread_id required"}, status=400)
                return
            messages = aura_db.get_thread_messages(user["id"], thread_id)
            self._send_json({"success": True, "messages": messages})

        elif path == "/api/memory":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required", "memories": [], "authenticated": False}, status=401)
                return
            memories = aura_db.get_user_memories(user["id"])
            self._send_json({"success": True, "memories": memories})

        elif path == "/api/settings":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            self._send_json({
                "success": True,
                "brain_settings": _selected_brain_settings(user),
                "providers": AuraSettingsManager.public_model_catalog(),
                "gemini_key_configured": bool(BRAIN.api_key and not BRAIN.api_key.startswith("YOUR_")),
            })

        elif path == "/api/projects":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": True, "projects": [], "authenticated": False})
                return
            projects = aura_db.get_user_projects(user["id"])
            self._send_json({"success": True, "projects": projects})

        elif path == "/api/system/test_browser":
            if not self._is_authorized_admin():
                self._send_json({"success": False, "error": "Unauthorized: Admin authentication required"}, status=401)
                return
            from aura_brain import tool_open_browser
            res = tool_open_browser("https://www.google.com")
            self._send_json(res)

        elif path == "/api/system/safety_status":
            from aura_brain import SAFE_WORKSPACE_ROOTS, STRICTLY_FORBIDDEN_PATHS
            self._send_json({
                "success": True,
                "sandbox_active": False,
                "command_filter_active": True,
                "sandbox_note": "Command-pattern checks are not process isolation.",
                "safe_workspaces": [str(p) for p in SAFE_WORKSPACE_ROOTS],
                "strictly_forbidden_paths": [str(p) for p in STRICTLY_FORBIDDEN_PATHS],
                "hardware_control": "Legacy tools are not all routed through the master-pipeline approval gate.",
                "powershell_sandbox": "Command-pattern filter only; no OS-level isolation",
                "multimodal_tools": ["tool_generate_image", "tool_generate_video", "tool_get_weather", "tool_open_browser"],
                "storage_status": aura_db.get_storage_status()
            })

        elif path == "/api/engines":
            from aura_engine_mesh import AURA_ENGINE_MESH
            mesh_status = AURA_ENGINE_MESH.get_mesh_status()
            self._send_json({
                "success": True,
                "status": mesh_status["status"],
                "total_engines": mesh_status["total_engines"],
                "awakened_engines": mesh_status["awakened_engines"],
                "total_files": mesh_status["total_files"],
                "file_count_scope": mesh_status["file_count_scope"],
                "supervisor_alive": mesh_status["supervisor_alive"],
                "timestamp": mesh_status["timestamp"],
                "engines": mesh_status["engines"]
            })

        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        elif path == "/api/engines/search":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_agent import AuraAgent
            agent_inst = AuraAgent()
            keyword = query.get("keyword", [""])[0]
            target_engine = query.get("engine", [None])[0]
            res = agent_inst.search_mesh_code(keyword, target_engine=target_engine)
            self._send_json({"success": True, "results": res})

        elif path == "/api/workspace/tree":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            ws = ROOT / "workspace"
            ws.mkdir(parents=True, exist_ok=True)
            files = []
            for f in ws.rglob("*"):
                if f.is_file() and not f.name.startswith("."):
                    files.append({
                        "name": f.name,
                        "rel_path": str(f.relative_to(ws)),
                        "size_kb": round(f.stat().st_size / 1024, 2),
                        "ext": f.suffix.lower()
                    })
            self._send_json({"success": True, "workspace": str(ws), "total_files": len(files), "files": files})

        elif path == "/api/workspace/file":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            file_rel = query.get("path", [""])[0]
            ws = ROOT / "workspace"
            target_p = (ws / file_rel).resolve()
            if ws in target_p.parents or target_p == ws or str(target_p).startswith(str(ws)):
                if target_p.exists() and target_p.is_file():
                    try:
                        content = target_p.read_text(encoding="utf-8", errors="ignore")
                        self._send_json({"success": True, "path": file_rel, "content": content})
                    except Exception as e:
                        self._send_json({"success": False, "error": str(e)}, status=500)
                else:
                    self._send_json({"success": False, "error": "File not found"}, status=404)
            else:
                self._send_json({"success": False, "error": "Path traversal restricted"}, status=403)

        elif path == "/api/cyberheist/status":
            ch_dir = Path(r"C:\Users\hp\cyberheist")
            if not ch_dir.exists():
                ch_dir = ROOT / "cyberheist" if (ROOT / "cyberheist").exists() else (ROOT / "workspace")
            status = {"success": True, "mounted": ch_dir.exists(), "path": str(ch_dir)}
            if ch_dir.exists():
                try:
                    sims = json.loads((ch_dir / "simulations.json").read_text(encoding="utf-8"))
                    missions = json.loads((ch_dir / "missions.json").read_text(encoding="utf-8"))
                    status["missions_count"] = len(missions.get("missions", []))
                    status["labs_count"] = len(sims.get("labs", []))
                    status["tabletops_count"] = len(sims.get("tabletops", []))
                    status["glossary_count"] = len(sims.get("glossary", []))
                except Exception as e:
                    status["error"] = str(e)
            self._send_json(status)
        elif path == "/api/permission/pending":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_permission_system import permission_manager
            pending = permission_manager.get_pending()
            self._send_json({"success": True, "pending": pending, "count": len(pending)})

        elif path == "/api/permission/history":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_permission_system import permission_manager
            self._send_json({"success": True, "history": permission_manager.history})

        elif path == "/api/os/telemetry":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_os_controller import laptop_controller
            self._send_json({"success": True, "telemetry": laptop_controller.get_system_telemetry()})

        elif path == "/api/game/status":
            from aura_game_engine import AURA_GAME_STUDIO
            self._send_json({"success": True, "status": AURA_GAME_STUDIO.get_status()})

        elif path == "/api/godot/status":
            from godot_engine_manager import AURA_GODOT_MANAGER
            self._send_json({
                "success": True,
                "installed": AURA_GODOT_MANAGER.is_installed(),
                "version": AURA_GODOT_MANAGER.get_version(),
                "binary_size_mb": AURA_GODOT_MANAGER.get_binary_size_mb(),
                "binary_path": str(AURA_GODOT_MANAGER.exe_path)
            })

        elif path == "/api/godot/projects":
            from godot_engine_manager import GAMES_WORKSPACE
            projects = []
            for item in GAMES_WORKSPACE.iterdir():
                if item.is_dir() and (item / "project.godot").exists():
                    projects.append({
                        "name": item.name,
                        "path": str(item),
                        "has_web_mirror": (item / "play_crafting_car.html").exists()
                    })
            self._send_json({"success": True, "projects": projects})

        elif path == "/api/media/status":
            from aura_media_engine import AURA_CINEMA
            self._send_json({"success": True, "status": AURA_CINEMA.get_status()})

        elif path == "/api/coderx/status":
            from coderx_engine import ROUTER
            self._send_json({
                "success": True,
                "engine": "CoderX Enterprise v2.0",
                "gemini_active": bool(ROUTER.gemini_key),
                "ollama_active": ROUTER.is_ollama_available(),
                "ollama_models": ROUTER.list_ollama_models() if ROUTER.is_ollama_available() else []
            })

        elif path == "/api/coderx/ast":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from coderx_engine import CodebaseAstMapper
            ws = ROOT / "workspace"
            repo_map = CodebaseAstMapper.generate_repo_map(ws)
            self._send_json({"success": True, "repo_map": repo_map})

        elif path == "/api/pipeline/status":
            from aura_master_pipeline import AURA_PIPELINE
            self._send_json({"success": True, "pipeline": AURA_PIPELINE.get_pipeline_topology()})

        elif path == "/api/pipeline/runs":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_master_pipeline import PIPELINE_RUNS_DIR
            runs = []
            for f in sorted(PIPELINE_RUNS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
                try:
                    import json
                    runs.append(json.loads(f.read_text(encoding="utf-8")))
                except Exception:
                    pass
            self._send_json({"success": True, "runs": runs})
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            body = json.loads(post_data) if post_data else {}
        except Exception:
            body = {}

        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # 1. AUTH ROUTES
        if path == "/api/auth/register":
            username = body.get("username", "")
            password = body.get("password", "")
            res = aura_db.register_user(username, password)
            res["storage_status"] = aura_db.get_storage_status()
            if res.get("success") and res.get("token"):
                res["csrf_token"] = aura_db.compute_csrf_token(res["token"])
                extra = [("Set-Cookie", self._build_session_cookie(res["token"]))]
                self._send_json(res, status=200, extra_headers=extra)
            else:
                status = 503 if res.get("storage_unavailable") else 400
                self._send_json(res, status=status)

        elif path == "/api/auth/login":
            username = body.get("username", "")
            password = body.get("password", "")
            res = aura_db.login_user(username, password)
            res["storage_status"] = aura_db.get_storage_status()
            if res.get("success") and res.get("token"):
                res["csrf_token"] = aura_db.compute_csrf_token(res["token"])
                extra = [("Set-Cookie", self._build_session_cookie(res["token"]))]
                self._send_json(res, status=200, extra_headers=extra)
            else:
                status = 503 if res.get("storage_unavailable") else 401
                self._send_json(res, status=status)

        elif path == "/api/auth/logout":
            token = ""
            auth_header = self.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
            if not token:
                token = self.headers.get("X-Auth-Token", "").strip()
            if not token and body and isinstance(body, dict):
                token = body.get("token", "")
            if not token:
                token = self._extract_cookie_token()
            if token:
                aura_db.revoke_session(token)
            extra = [("Set-Cookie", self._build_session_cookie("", clear=True))]
            self._send_json({"success": True, "message": "Session terminated successfully"}, extra_headers=extra)

        # 2. THREADS ROUTES
        elif path == "/api/threads/new":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Unauthorized"}, status=401)
                return
            user_id = user["id"]
            title = body.get("title", "New Session")
            thread_id = body.get("id") or body.get("thread_id")
            thread = aura_db.create_user_thread(user_id, title, thread_id=thread_id)
            self._send_json({"success": True, "thread": thread})

        elif path == "/api/threads/rename":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            user_id = user["id"]
            thread_id = body.get("thread_id", "")
            new_title = body.get("title", "").strip()
            if not thread_id or not new_title:
                self._send_json({"success": False, "error": "thread_id and title required"}, status=400)
                return
            ok = aura_db.rename_user_thread(user_id, thread_id, new_title)
            self._send_json({"success": ok})

        elif path == "/api/threads/pin":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            user_id = user["id"]
            thread_id = body.get("thread_id", "")
            is_pinned = body.get("is_pinned", False)
            ok = aura_db.pin_user_thread(user_id, thread_id, is_pinned)
            self._send_json({"success": ok})

        elif path == "/api/threads/delete":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            user_id = user["id"]
            thread_id = body.get("thread_id", "")
            ok = aura_db.delete_user_thread(user_id, thread_id)
            self._send_json({"success": ok})

        # 2B. CODING PROJECTS ROUTES
        elif path == "/api/projects/new":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            user_id = user["id"]
            name = body.get("name", "New Project")
            company = body.get("company", "")
            stack = body.get("stack", "Python")
            proj_path = body.get("path", "")
            description = body.get("description", "")
            proj = aura_db.create_user_project(user_id, name, company, stack, proj_path, description)
            self._send_json({"success": True, "project": proj})

        elif path == "/api/projects/pin":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            user_id = user["id"]
            proj_id = body.get("project_id", "")
            is_pinned = body.get("is_pinned", False)
            ok = aura_db.pin_user_project(user_id, proj_id, is_pinned)
            self._send_json({"success": ok})

        elif path == "/api/projects/rename":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            user_id = user["id"]
            proj_id = body.get("project_id", "")
            new_name = body.get("name", "").strip()
            ok = aura_db.rename_user_project(user_id, proj_id, new_name)
            self._send_json({"success": ok})

        elif path == "/api/projects/delete":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            user_id = user["id"]
            proj_id = body.get("project_id", "")
            ok = aura_db.delete_user_project(user_id, proj_id)
            self._send_json({"success": ok})

        # 3. CHAT DISPATCH
        elif path == "/api/chat":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"reply": "Session expired or not logged in. Please sign in to save your conversation and execute tasks.", "error": "unauthorized"}, status=401)
                return
            user_id = user["id"]
            prompt = body.get("prompt", "").strip()
            thread_id = body.get("thread_id", "default")
            attachments = body.get("attachments", [])
            permission_mode = body.get("mode", "auto_pilot")
            approved = body.get("approved", False)

            if not prompt and not attachments:
                self._send_json({"reply": "Please enter an instruction or attach a file."}, status=400)
                return

            # Save user turn with attachment summary
            display_prompt = prompt
            if attachments:
                att_names = [a.get("name", "attachment") for a in attachments]
                display_prompt += f"\n[📎 {len(attachments)} Attachment(s): {', '.join(att_names)}]"

            aura_db.save_message(user_id, thread_id, "user", display_prompt)

            # Retrieve prior thread messages for multi-turn conversational memory
            prior_messages = aura_db.get_thread_messages(user_id, thread_id)
            conv_history = []
            for m in prior_messages[:-1]:
                role = "user" if m.get("role") == "user" else "model"
                txt = m.get("content", "")
                if txt:
                    conv_history.append({"role": role, "parts": [{"text": txt}]})

            print(f"[*] AURA Runtime: User {user_id} in thread '{thread_id}' -> '{prompt}' (Mode: {permission_mode}, Attachments: {len(attachments)}, History: {len(conv_history)})")
            brain = _create_user_brain(user)
            reply = brain.think_and_act(prompt, attachments=attachments, permission_mode=permission_mode, approved=approved, conversation_history=conv_history)
            tools_used = getattr(brain, "last_tools", [])

            # Save assistant response
            aura_db.save_message(user_id, thread_id, "assistant", reply, tools_used)

            self._send_json({
                "reply": reply,
                "tools": tools_used,
                "status": "completed"
            })

        # 3B. STREAMING CHAT DISPATCH (SSE)
        elif path == "/api/chat/stream":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"reply": "Session expired or not logged in.", "error": "unauthorized"}, status=401)
                return
            user_id = user["id"]
            prompt = body.get("prompt", "").strip()
            thread_id = body.get("thread_id", "default")
            attachments = body.get("attachments", [])
            permission_mode = body.get("mode", "auto_pilot")
            approved = body.get("approved", False)

            if not prompt and not attachments:
                self._send_json({"error": "Prompt or attachments required"}, status=400)
                return

            display_prompt = prompt
            if attachments:
                att_names = [a.get("name", "attachment") for a in attachments]
                display_prompt += f"\n[📎 {len(attachments)} Attachment(s): {', '.join(att_names)}]"

            aura_db.save_message(user_id, thread_id, "user", display_prompt)

            # Retrieve prior thread messages for multi-turn conversational memory
            prior_messages = aura_db.get_thread_messages(user_id, thread_id)
            conv_history = []
            for m in prior_messages[:-1]:
                role = "user" if m.get("role") == "user" else "model"
                txt = m.get("content", "")
                if txt:
                    conv_history.append({"role": role, "parts": [{"text": txt}]})

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", self._resolve_cors_origin())
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.end_headers()

            brain = _create_user_brain(user)
            accumulated_text = ""
            tools_used = []

            try:
                for chunk in brain.think_and_act_stream(prompt, attachments=attachments, permission_mode=permission_mode, approved=approved, conversation_history=conv_history):
                    chunk_type = chunk.get("type")
                    if chunk_type == "token":
                        accumulated_text += chunk.get("delta", "")
                        payload = json.dumps({"type": "token", "delta": chunk.get("delta", "")})
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    elif chunk_type == "tool":
                        tools_used.append({"name": chunk.get("name")})
                        payload = json.dumps({"type": "tool", "name": chunk.get("name")})
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    elif chunk_type == "done":
                        if not accumulated_text:
                            accumulated_text = chunk.get("reply", "")
                        payload = json.dumps({"type": "done", "reply": accumulated_text, "tools": tools_used})
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                        self.wfile.flush()

                aura_db.save_message(user_id, thread_id, "assistant", accumulated_text, tools_used)
            except Exception as e:
                err_payload = json.dumps({"type": "error", "error": str(e)})
                try:
                    self.wfile.write(f"data: {err_payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    pass
            finally:
                self.close_connection = True
            return

        # 4. MEMORY ROUTES
        elif path == "/api/memory/add":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            user_id = user["id"]
            key = body.get("key", "").strip()
            val = body.get("value", "").strip()
            if not key or not val:
                self._send_json({"success": False, "error": "Key and value required"}, status=400)
                return
            ok = aura_db.save_user_memory(user_id, key, val)
            self._send_json({"success": ok, "key": key, "value": val})

        elif path == "/api/memory/delete":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            user_id = user["id"]
            key = body.get("key", "").strip()
            ok = aura_db.delete_user_memory(user_id, key)
            self._send_json({"success": ok, "deleted": key})

        # 5. SETTINGS ROUTE
        elif path == "/api/settings":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            requested = body.get("brain_settings", body)
            if not isinstance(requested, dict):
                self._send_json({"success": False, "error": "Invalid model settings"}, status=400)
                return
            provider = requested.get("active_provider")
            model = requested.get("active_model")
            if not AuraSettingsManager.validate_model_selection(provider, model):
                self._send_json({"success": False, "error": "Unsupported provider or model"}, status=400)
                return
            saved = dict(user.get("settings") or {})
            saved["brain_settings"] = {
                "active_provider": provider,
                "active_model": model.strip(),
            }
            if not aura_db.save_user_settings(user["id"], saved):
                self._send_json({"success": False, "error": "Could not save model settings"}, status=500)
                return
            user["settings"] = saved
            self._send_json({
                "success": True,
                "brain_settings": _selected_brain_settings(user),
            })

        elif path == "/api/engines/search":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_agent import AuraAgent
            agent_inst = AuraAgent()
            keyword = body.get("keyword") or query.get("keyword", [""])[0]
            target_engine = body.get("engine") or query.get("engine", [None])[0]
            res = agent_inst.search_mesh_code(keyword, target_engine=target_engine)
            self._send_json({"success": True, "results": res})

        elif path == "/api/workspace/save":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            file_rel = body.get("path", "")
            file_content = body.get("content", "")
            ws = ROOT / "workspace"
            target_p = (ws / file_rel).resolve()
            if str(target_p).startswith(str(ws)):
                target_p.parent.mkdir(parents=True, exist_ok=True)
                target_p.write_text(file_content, encoding="utf-8")
                self._send_json({"success": True, "saved_path": str(target_p), "bytes": len(file_content)})
            else:
                self._send_json({"success": False, "error": "Save path outside workspace is forbidden"}, status=403)

        elif path == "/api/terminal/exec":
            if not self._is_authorized_admin(body):
                self._send_json({"success": False, "error": "Unauthorized: Admin authentication required for terminal execution"}, status=401)
                return
            cmd = body.get("command", "")
            ws = ROOT / "workspace"
            ws.mkdir(parents=True, exist_ok=True)
            if not cmd:
                self._send_json({"success": False, "error": "Command is required"}, status=400)
                return
            from aura_brain import is_safe_command
            is_safe, reason = is_safe_command(cmd)
            if not is_safe:
                self._send_json({"success": False, "command": cmd, "error": f"Security Sandbox: {reason}", "exit_code": 1}, status=403)
                return
            import subprocess
            import shutil
            try:
                if sys.platform == "win32":
                    shell_args = ["powershell", "-NoProfile", "-Command", cmd]
                else:
                    pwsh_bin = shutil.which("pwsh") or shutil.which("powershell")
                    shell_args = [pwsh_bin, "-NoProfile", "-Command", cmd] if pwsh_bin else ["/bin/sh", "-c", cmd]
                proc = subprocess.run(shell_args,
                                      cwd=str(ws), capture_output=True, text=True, timeout=30)
                self._send_json({
                    "success": True,
                    "command": cmd,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr
                })
            except Exception as e:
                self._send_json({"success": False, "command": cmd, "error": str(e), "exit_code": 1})

        elif path == "/api/game/world/generate":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            theme = body.get("theme", "gta_city")
            chunks = body.get("chunks", 4)
            seed = body.get("seed", 42)
            from aura_game_engine import OpenWorldProceduralGenerator
            res = OpenWorldProceduralGenerator.generate_world(theme=theme, chunks=chunks, seed=seed)
            self._send_json(res)

        elif path == "/api/game/physics/simulate":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            steps = body.get("steps", 60)
            name = body.get("name", "car")
            mass = body.get("mass", 1200.0)
            pos_y = body.get("pos_y", 3.0)
            from aura_game_engine import JoltPhysicsEngine
            jolt = JoltPhysicsEngine()
            jolt.add_body(name, mass=mass, pos=(0, pos_y, 0), restitution=0.3)
            self._send_json(jolt.simulate(steps=steps))

        elif path == "/api/game/navmesh/pathfind":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            sx = body.get("start_x", 0)
            sy = body.get("start_y", 0)
            gx = body.get("goal_x", 10)
            gy = body.get("goal_y", 10)
            from aura_game_engine import RecastNavMeshRouter
            res = RecastNavMeshRouter.find_path(start=(sx, sy), goal=(gx, gy))
            self._send_json(res)

        elif path == "/api/game/agent/train":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            episodes = body.get("episodes", 5)
            from aura_game_engine import MLAgentsCarlaTrainer
            res = MLAgentsCarlaTrainer.train_driving_agent(episodes=episodes)
            self._send_json(res)

        elif path == "/api/game/multiplayer/sync":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            count = body.get("player_count", 100)
            from aura_game_engine import AgonesNetcodeSynchronizer
            res = AgonesNetcodeSynchronizer.simulate_100_player_tick(player_count=count)
            self._send_json(res)

        elif path == "/api/game/project/export":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            proj = body.get("project_name", "open_world_demo")
            from aura_game_engine import EngineProjectExporter
            res = EngineProjectExporter.export_project(project_name=proj)
            self._send_json(res)

        elif path == "/api/godot/build":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            proj = body.get("project_name", "CyberCraft3D")
            from godot_engine_manager import GodotCarCraftingProjectBuilder
            res = GodotCarCraftingProjectBuilder.build_project(project_name=proj)
            self._send_json(res)

        elif path == "/api/godot/verify":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            proj = body.get("project_name", "CyberCraft3D")
            from godot_engine_manager import AURA_GODOT_TRAINER
            res = AURA_GODOT_TRAINER.train_and_verify(project_name=proj)
            self._send_json(res)

        elif path == "/api/godot/launch":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            proj = body.get("project_name", "CyberCraft3D")
            from godot_engine_manager import AURA_GODOT_MANAGER, GAMES_WORKSPACE
            proj_dir = GAMES_WORKSPACE / proj
            res = AURA_GODOT_MANAGER.launch_windowed_game(proj_dir)
            self._send_json(res)

        elif path == "/api/pipeline/run":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            goal = body.get("goal", "Create a coding task")
            domain = body.get("domain")
            params = body.get("params", {})
            from aura_master_pipeline import AURA_PIPELINE
            res = AURA_PIPELINE.execute(goal=goal, domain=domain, params=params)
            self._send_json(res)

        elif path == "/api/media/image/generate":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            prompt = body.get("prompt", "")
            style = body.get("style", "auto")
            aspect_ratio = body.get("aspect_ratio", "1:1")
            from aura_media_engine import AURA_CINEMA
            res = AURA_CINEMA.create_cinematic_image(prompt, camera_style=style, aspect_ratio=aspect_ratio)
            self._send_json(res)

        elif path == "/api/media/image/transform":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            img_path = body.get("image_path", "")
            instruction = body.get("instruction", "iPhone portrait")
            from aura_media_engine import AURA_CINEMA
            res = AURA_CINEMA.transform_existing_image(img_path, instruction)
            self._send_json(res)

        elif path == "/api/media/image/remove_bg":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            img_path = body.get("image_path", "")
            from aura_media_engine import NativeSegmentationEngine
            inp = Path(img_path)
            out = inp.parent / f"{inp.stem}_nobg.png"
            res = NativeSegmentationEngine.remove_background(inp, out)
            self._send_json(res)

        elif path == "/api/media/video/generate":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            prompt = body.get("prompt", "")
            duration = body.get("duration_sec", 5)
            fps = body.get("fps", 24)
            motion = body.get("camera_motion", "dolly_zoom")
            aspect = body.get("aspect_ratio", "16:9")
            from aura_media_engine import AURA_CINEMA
            res = AURA_CINEMA.create_cinematic_video(prompt, duration_sec=duration, fps=fps, camera_motion=motion, aspect_ratio=aspect)
            self._send_json(res)

        elif path == "/api/coderx/execute":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            goal = body.get("goal", "")
            filename = body.get("filename", "coderx_script.py")
            cmd = body.get("test_command", "")
            max_iter = body.get("max_iterations", 5)
            from coderx_engine import CODERX
            res = CODERX.run(goal=goal, target_filename=filename, test_command=cmd, max_iterations=max_iter)
            self._send_json(res)

        elif path == "/api/coderx/patch":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            file_rel = body.get("path", "")
            patch_text = body.get("patch", "")
            ws = ROOT / "workspace"
            target_p = (ws / file_rel).resolve()
            from coderx_engine import AiderDiffPatcher
            res = AiderDiffPatcher.apply_patch_string(target_p, patch_text)
            self._send_json(res)

        elif path == "/api/autonomous/mission":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            goal = body.get("goal", "")
            filename = body.get("filename", "mission_script.py")
            from aura_autonomous_loop import AURA_LOOP
            from aura_brain import tool_autonomous_code_loop
            res = tool_autonomous_code_loop(goal=goal, target_filename=filename)
            self._send_json(res)

        elif path == "/api/engines/invoke":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            engine_key = body.get("engine", "")
            action = body.get("action", "run")
            params = body.get("params", {})
            from aura_engine_mesh import AURA_ENGINE_MESH
            res = AURA_ENGINE_MESH.invoke(engine_key, action=action, **params)
            self._send_json(res)
        elif path == "/api/permission/respond":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            req_id = body.get("id", "")
            decision = body.get("decision", "DENY")
            from aura_permission_system import permission_manager
            ok = permission_manager.respond_request(req_id, decision)
            self._send_json({"success": ok, "id": req_id, "decision": decision})

        elif path == "/api/permission/mode":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mode = body.get("mode", "PROMPT_HIGH_RISK")
            from aura_permission_system import permission_manager
            ok = permission_manager.set_security_mode(mode)
            self._send_json({"success": ok, "mode": mode})

        elif path == "/api/os/execute":
            if not self._is_authorized_admin(body):
                self._send_json({"success": False, "error": "Unauthorized: Admin authentication required for OS execution"}, status=401)
                return
            cmd = body.get("command", "")
            from aura_brain import is_safe_command
            is_safe, reason = is_safe_command(cmd)
            if not is_safe:
                self._send_json({"success": False, "command": cmd, "error": f"Security Sandbox: {reason}"}, status=403)
                return
            as_admin = body.get("as_admin", False)
            from aura_os_controller import laptop_controller
            res = laptop_controller.execute_powershell(cmd, as_admin=as_admin)
            self._send_json(res)

        elif path == "/api/os/read_file":
            if not self._is_authorized_admin(body):
                self._send_json({"success": False, "error": "Unauthorized: Admin authentication required for file read"}, status=401)
                return
            filepath = body.get("path", "")
            from aura_brain import validate_safe_path
            try:
                validated_p = validate_safe_path(filepath)
            except PermissionError as pe:
                self._send_json({"success": False, "error": str(pe)}, status=403)
                return
            from aura_os_controller import laptop_controller
            res = laptop_controller.read_file(str(validated_p))
            self._send_json(res)

        elif path == "/api/os/write_file":
            if not self._is_authorized_admin(body):
                self._send_json({"success": False, "error": "Unauthorized: Admin authentication required for file write"}, status=401)
                return
            filepath = body.get("path", "")
            from aura_brain import validate_safe_path
            try:
                validated_p = validate_safe_path(filepath, allow_create=True)
            except PermissionError as pe:
                self._send_json({"success": False, "error": str(pe)}, status=403)
                return
            file_content = body.get("content", "")
            from aura_os_controller import laptop_controller
            res = laptop_controller.write_file(str(validated_p), file_content)
            self._send_json(res)

        elif path == "/api/os/screenshot":
            if not self._is_authorized_admin(body):
                self._send_json({"success": False, "error": "Unauthorized: Admin authentication required for screen capture"}, status=401)
                return
            from aura_os_controller import laptop_controller
            res = laptop_controller.capture_screenshot()
            self._send_json(res)
        else:
            self.send_error(404, "Not Found")


def make_server(host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), AuraWebHandler)


# Top-level serverless function entrypoint for Vercel (@vercel/python)
handler = AuraWebHandler
app = AuraWebHandler


def run():
    httpd = make_server(HOST, PORT)
    url = f"http://127.0.0.1:{PORT}"
    print("=" * 65)
    print("        AURA AGENT - MULTI-USER CLOUD & LOCAL WORKSPACE")
    print("                    AURA Technologies Inc.")
    print("=" * 65)
    print(f"[*] Workspace Server Binding : {HOST}:{PORT}")
    print(f"[*] Local Access URL         : {url}")
    print("[*] Multi-User Auth SQLite   : ACTIVE (aura_workspace.db)")
    print("[*] Security Sandbox Guard   : ACTIVE (PathGuard & CommandGuard)")
    print("[*] ReAct Gemini Brain       : READY (Multimodal & 63 Engines)")
    print("-" * 65)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server shutdown gracefully.")


if __name__ == "__main__":
    run()
