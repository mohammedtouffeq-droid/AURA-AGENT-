"""
===================================================================================
                     AURA AGENT - MULTI-USER WORKSPACE SERVER
===================================================================================
Multi-tenant HTTP Workspace Server supporting:
- Authenticated sessions (Bearer header or HttpOnly SameSite=Strict cookie + CSRF)
- Per-user isolated workspaces (`workspace/user_<id>`) with strict path containment
- Per-user threads, renaming, pinning, projects, memory vault & model settings
- Role-based access control separating standard accounts from administrator OS tools
===================================================================================
"""

import json
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024  # 10 MB strict ceiling


def _resolve_workspace_dir(user_id: Optional[int] = None) -> Path:
    if os.environ.get("VERCEL") or not os.access(ROOT, os.W_OK):
        ws = Path(tempfile.gettempdir()) / "aura_workspace"
    else:
        ws = ROOT / "workspace"
    if user_id is not None:
        ws = ws / f"user_{int(user_id)}"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def _safe_resolve_under(base_dir: Path, rel_path: str, allow_root: bool = False) -> Optional[Path]:
    """Resolves `rel_path` strictly inside `base_dir` using `Path.relative_to` (immune to sibling-prefix bypass)."""
    if not isinstance(rel_path, str):
        return None
    cleaned = rel_path.strip()
    if not cleaned and not allow_root:
        return None
    try:
        base_resolved = base_dir.resolve()
        candidate = (base_resolved / cleaned).resolve()
        candidate.relative_to(base_resolved)
        if not allow_root and candidate == base_resolved:
            return None
        return candidate
    except (OSError, ValueError, TypeError):
        return None


def _clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        if isinstance(value, bool):
            return default
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _clamp_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        if isinstance(value, bool):
            return default
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed:  # NaN check
        return default
    return max(minimum, min(maximum, parsed))


import aura_db
from aura_brain import AuraBrain
from aura_settings import AuraSettingsManager
from coderx_engine import _atomic_write_text

BRAIN = AuraBrain()
SETTINGS = AuraSettingsManager()
HOST = os.environ.get("AURA_HOST", "127.0.0.1")
PORT = int(os.environ.get("AURA_PORT", 5050))


def _selected_brain_settings(user: Dict[str, Any]) -> Dict[str, str]:
    user_settings = user.get("settings") or {}
    user_brain = user_settings.get("brain_settings", {}) if isinstance(user_settings, dict) else {}
    provider = user_brain.get(
        "active_provider",
        SETTINGS.config.get("brain_settings", {}).get("active_provider", "gemini"),
    )
    model = user_brain.get(
        "active_model",
        SETTINGS.config.get("brain_settings", {}).get("active_model", "gemini-flash-lite-latest"),
    )
    if not AuraSettingsManager.validate_model_selection(provider, model):
        provider, model = "gemini", "gemini-flash-lite-latest"
    return {"active_provider": provider, "active_model": model}


def _create_user_brain(user: Dict[str, Any]) -> AuraBrain:
    selected = _selected_brain_settings(user)
    brain = AuraBrain(provider=selected["active_provider"], model=selected["active_model"])
    if isinstance(user, dict) and user.get("id") is not None:
        try:
            brain.user_id = int(user["id"])
        except (ValueError, TypeError):
            brain.user_id = None
        brain.user_role = str(user.get("role") or "user")
        prefs = (user.get("settings") or {}).get("preferences") or {}
        if "temperature" in prefs:
            brain.temperature = _clamp_float(prefs.get("temperature"), 0.3, 0.0, 1.0)
    return brain


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


CSP_HEADER_VALUE = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data: blob: https:; "
    "media-src 'self' blob: data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "object-src 'none'"
)


class AuraWebHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        first_arg = str(args[0]) if args else ""
        if any(noisy in first_arg for noisy in ("/api/permission/pending", "/favicon.ico")):
            return
        super().log_message(format, *args)

    def _resolve_cors_origin(self) -> Optional[str]:
        raw_origin = self.headers.get("Origin") or ""
        req_origin = re.sub(r"[\r\n]", "", raw_origin).strip().rstrip("/")
        if req_origin and req_origin in _get_allowed_origins():
            return req_origin
        return None

    def _extract_request_path(self) -> Tuple[str, Dict[str, List[str]]]:
        matched = (
            self.headers.get("x-matched-path")
            or self.headers.get("x-vercel-matched-path")
            or self.headers.get("x-forwarded-uri")
            or self.headers.get("x-original-url")
            or ""
        )
        parsed_url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_url.query)
        if matched and matched.startswith("/api"):
            path = urllib.parse.urlparse(matched).path
        elif "__route__" in query:
            path = query["__route__"][0]
        else:
            path = parsed_url.path
        return path, query

    def _apply_security_and_cors_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), usb=(), bluetooth=()")
        self.send_header("Content-Security-Policy", CSP_HEADER_VALUE)
        self.send_header("Vary", "Origin")
        cors_origin = self._resolve_cors_origin()
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token, X-CSRF-Token")

    def _send_json(
        self,
        data: Dict[str, Any],
        status: int = 200,
        extra_headers: Optional[List[tuple]] = None,
    ) -> None:
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self._apply_security_and_cors_headers()
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
        self._apply_security_and_cors_headers()
        self.end_headers()

    def do_OPTIONS(self):
        cors_origin = self._resolve_cors_origin()
        self.send_response(204 if cors_origin else 403)
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self._apply_security_and_cors_headers()
        self.end_headers()

    def _get_auth_user(self, body: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Authenticates via `Authorization: Bearer <token>`, `X-Auth-Token`, or
        `HttpOnly` `aura_session` cookie (with mandatory CSRF verification on POST).
        URL query-string tokens (`?token=...`) are intentionally rejected to prevent token leakage.
        """
        auth_header = self.headers.get("Authorization", "")
        token = ""
        used_cookie = False
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        if not token:
            token = self.headers.get("X-Auth-Token", "").strip()
        if not token:
            token = self._extract_cookie_token()
            if token:
                used_cookie = True

        if not token:
            return None

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
            role = user.get("role", "user")
            if role in ("admin", "superuser"):
                return True
        return False

    def do_GET(self):
        try:
            self._handle_get()
        except Exception as exc:
            self._send_json({"success": False, "error": f"Server error: {exc}"}, status=500)

    def _handle_get(self):
        path, query = self._extract_request_path()

        if path in ("/", "/index.html", ""):
            html_file = ROOT / "index.html"
            if html_file.exists():
                data = html_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Connection", "close")
                self._apply_security_and_cors_headers()
                self.end_headers()
                self.wfile.write(data)
            else:
                self._send_json({"success": False, "error": "index.html not found"}, status=404)

        elif path in ("/manifest.json", "/sw.js"):
            asset_file = ROOT / path.lstrip("/")
            if asset_file.exists() and asset_file.is_file():
                data = asset_file.read_bytes()
                ctype = "application/manifest+json" if path.endswith(".json") else "application/javascript"
                self.send_response(200)
                self.send_header("Content-Type", f"{ctype}; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Connection", "close")
                self._apply_security_and_cors_headers()
                self.end_headers()
                self.wfile.write(data)
            else:
                self._send_json({"success": False, "error": "Not found"}, status=404)

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
                    "storage_status": storage_status,
                    "user_vault": aura_db.export_user_vault(user["id"]),
                })

        elif path.startswith("/media/"):
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            media_rel = urllib.parse.unquote(path[7:]).lstrip("/")
            user_ws = _resolve_workspace_dir(user["id"])
            target_file = _safe_resolve_under(user_ws, media_rel)
            if target_file is None or not target_file.exists() or not target_file.is_file():
                self._send_json({"success": False, "error": "Media file not found"}, status=404)
                return

            ext = target_file.suffix.lower()
            mime_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif",
                ".mp4": "video/mp4",
                ".webm": "video/webm",
            }
            content_type = mime_map.get(ext, "application/octet-stream")
            data = target_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "private, no-store")
            self.send_header("Connection", "close")
            self._apply_security_and_cors_headers()
            self.end_headers()
            self.wfile.write(data)
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
            from aura_permission_system import permission_manager
            self._send_json({
                "success": True,
                "brain_settings": _selected_brain_settings(user),
                "security_mode": permission_manager.get_security_mode(user["id"]).value,
                "user_preferences": (user.get("settings") or {}).get("preferences", {}),
                "providers": AuraSettingsManager.public_model_catalog(),
                "gemini_key_configured": bool(BRAIN.api_key and not BRAIN.api_key.startswith("YOUR_")),
            })

        elif path == "/api/projects":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required", "projects": [], "authenticated": False}, status=401)
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
            is_admin = self._is_authorized_admin()
            storage_info = aura_db.get_storage_status()
            public_storage = {
                "backend": storage_info.get("backend"),
                "persistent": storage_info.get("persistent"),
                "serverless": storage_info.get("serverless"),
            }
            payload: Dict[str, Any] = {
                "success": True,
                "sandbox_active": False,
                "command_filter_active": True,
                "per_user_workspace_isolation": True,
                "sandbox_note": "Workspace path containment and command-pattern checks are active; they are not OS-kernel container process isolation.",
                "powershell_sandbox": "Admin-only + command-pattern filter; disabled for standard chat accounts.",
                "multimodal_tools": ["tool_generate_image", "tool_generate_video", "tool_get_weather", "tool_open_browser"],
                "storage_status": storage_info if is_admin else public_storage,
            }
            if is_admin:
                from aura_brain import SAFE_WORKSPACE_ROOTS, STRICTLY_FORBIDDEN_PATHS
                payload["safe_workspaces"] = [str(p) for p in SAFE_WORKSPACE_ROOTS]
                payload["strictly_forbidden_paths"] = [str(p) for p in STRICTLY_FORBIDDEN_PATHS]
            self._send_json(payload)

        elif path == "/api/engines":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_engine_mesh import AURA_ENGINE_MESH
            mesh_status = AURA_ENGINE_MESH.get_mesh_status()
            is_admin = self._is_authorized_admin()
            sanitized_engines = []
            for eng in mesh_status["engines"]:
                item = dict(eng)
                if not is_admin:
                    item.pop("path", None)
                sanitized_engines.append(item)
            self._send_json({
                "success": True,
                "status": mesh_status["status"],
                "catalog_note": "Catalogue of 63 upstream AI ecosystems; 'mounted' indicates local checkout presence, while 'has_adapter' indicates an implemented Python adapter.",
                "total_engines": mesh_status["total_engines"],
                "awakened_engines": mesh_status["awakened_engines"],
                "total_files": mesh_status["total_files"],
                "file_count_scope": mesh_status["file_count_scope"],
                "supervisor_alive": mesh_status["supervisor_alive"],
                "timestamp": mesh_status["timestamp"],
                "engines": sanitized_engines,
            })

        elif path == "/favicon.ico":
            self.send_response(204)
            self._apply_security_and_cors_headers()
            self.end_headers()

        elif path == "/api/engines/search":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_agent import AuraAgent
            agent_inst = AuraAgent()
            keyword = query.get("keyword", [""])[0][:120]
            target_engine = query.get("engine", [None])[0]
            res = agent_inst.search_mesh_code(keyword, target_engine=target_engine)
            self._send_json({"success": True, "results": res})

        elif path == "/api/workspace/tree":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            ws = _resolve_workspace_dir(user["id"])
            files = []
            for f in ws.rglob("*"):
                if f.is_file() and not f.name.startswith("."):
                    files.append({
                        "name": f.name,
                        "rel_path": f.relative_to(ws).as_posix(),
                        "size_kb": round(f.stat().st_size / 1024, 2),
                        "ext": f.suffix.lower(),
                    })
            self._send_json({
                "success": True,
                "workspace_scope": f"user_{user['id']}",
                "total_files": len(files),
                "files": files,
            })

        elif path == "/api/workspace/file":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            file_rel = query.get("path", [""])[0]
            ws = _resolve_workspace_dir(user["id"])
            target_p = _safe_resolve_under(ws, file_rel)
            if target_p is None:
                self._send_json({"success": False, "error": "Path traversal restricted"}, status=403)
                return
            if target_p.exists() and target_p.is_file():
                try:
                    content = target_p.read_text(encoding="utf-8", errors="ignore")
                    self._send_json({"success": True, "path": target_p.relative_to(ws).as_posix(), "content": content})
                except Exception as e:
                    self._send_json({"success": False, "error": str(e)}, status=500)
            else:
                self._send_json({"success": False, "error": "File not found"}, status=404)

        elif path == "/api/cyberheist/status":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            ch_dir = Path(r"C:\Users\hp\cyberheist")
            if not ch_dir.exists():
                ch_dir = ROOT / "cyberheist" if (ROOT / "cyberheist").exists() else _resolve_workspace_dir(user["id"])
            status_payload: Dict[str, Any] = {"success": True, "mounted": ch_dir.exists()}
            if self._is_authorized_admin():
                status_payload["path"] = str(ch_dir)
            if ch_dir.exists():
                try:
                    sims_file = ch_dir / "simulations.json"
                    missions_file = ch_dir / "missions.json"
                    if sims_file.exists() and missions_file.exists():
                        sims = json.loads(sims_file.read_text(encoding="utf-8"))
                        missions = json.loads(missions_file.read_text(encoding="utf-8"))
                        status_payload["missions_count"] = len(missions.get("missions", []))
                        status_payload["labs_count"] = len(sims.get("labs", []))
                        status_payload["tabletops_count"] = len(sims.get("tabletops", []))
                        status_payload["glossary_count"] = len(sims.get("glossary", []))
                except Exception as e:
                    status_payload["error"] = str(e)
            self._send_json(status_payload)

        elif path == "/api/permission/pending":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_permission_system import permission_manager
            pending = permission_manager.get_pending(user_id=user["id"])
            self._send_json({"success": True, "pending": pending, "count": len(pending)})

        elif path == "/api/permission/history":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_permission_system import permission_manager
            self._send_json({"success": True, "history": permission_manager.get_history(user_id=user["id"])})

        elif path == "/api/os/telemetry":
            if not self._is_authorized_admin():
                self._send_json({"success": False, "error": "Admin authentication required"}, status=401)
                return
            from aura_os_controller import laptop_controller
            self._send_json({"success": True, "telemetry": laptop_controller.get_system_telemetry()})

        elif path == "/api/os/brightness":
            if not self._is_authorized_admin():
                self._send_json({"success": False, "error": "Admin authentication required"}, status=401)
                return
            from aura_os_controller import laptop_controller
            self._send_json(laptop_controller.get_brightness())

        elif path == "/api/game/status":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_game_engine import AURA_GAME_STUDIO
            self._send_json({"success": True, "status": AURA_GAME_STUDIO.get_status()})

        elif path == "/api/godot/status":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from godot_engine_manager import AURA_GODOT_MANAGER
            resp_data: Dict[str, Any] = {
                "success": True,
                "installed": AURA_GODOT_MANAGER.is_installed(),
                "version": AURA_GODOT_MANAGER.get_version(),
                "binary_size_mb": AURA_GODOT_MANAGER.get_binary_size_mb(),
            }
            if self._is_authorized_admin():
                resp_data["binary_path"] = str(AURA_GODOT_MANAGER.exe_path)
            self._send_json(resp_data)

        elif path == "/api/godot/projects":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            user_games_dir = _resolve_workspace_dir(user["id"]) / "godot_projects"
            user_games_dir.mkdir(parents=True, exist_ok=True)
            projects = []
            for item in user_games_dir.iterdir():
                if item.is_dir() and (item / "project.godot").exists():
                    projects.append({
                        "name": item.name,
                        "has_web_mirror": (item / "play_crafting_car.html").exists(),
                    })
            self._send_json({"success": True, "projects": projects})

        elif path == "/api/media/status":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_media_engine import AURA_CINEMA
            self._send_json({"success": True, "status": AURA_CINEMA.get_status()})

        elif path == "/api/coderx/status":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from coderx_engine import ROUTER
            self._send_json({
                "success": True,
                "engine": "CoderX Enterprise v2.0",
                "gemini_active": bool(ROUTER.gemini_key),
                "ollama_active": ROUTER.is_ollama_available(),
                "ollama_models": ROUTER.list_ollama_models() if ROUTER.is_ollama_available() else [],
            })

        elif path == "/api/coderx/ast":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from coderx_engine import CodebaseAstMapper
            ws = _resolve_workspace_dir(user["id"])
            repo_map = CodebaseAstMapper.generate_repo_map(ws)
            self._send_json({"success": True, "repo_map": repo_map})

        elif path == "/api/flagship/overview":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_flagship_repos import get_all_flagship_status
            self._send_json(get_all_flagship_status())

        elif path == "/api/systems10/overview":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_10_systems import AURA_10_SYSTEMS
            self._send_json(AURA_10_SYSTEMS.get_overview())

        elif path == "/api/pipeline/status":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_master_pipeline import AURA_PIPELINE
            self._send_json({"success": True, "pipeline": AURA_PIPELINE.get_pipeline_topology()})

        elif path == "/api/pipeline/runs":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            user_runs_dir = _resolve_workspace_dir(user["id"]) / "pipeline_runs"
            runs = []
            if user_runs_dir.exists():
                for f in sorted(user_runs_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
                    try:
                        runs.append(json.loads(f.read_text(encoding="utf-8")))
                    except Exception:
                        pass
            self._send_json({"success": True, "runs": runs})

        else:
            self._send_json({"success": False, "error": "Not Found"}, status=404)

    def do_POST(self):
        try:
            self._handle_post()
        except Exception as exc:
            self._send_json({"success": False, "error": f"Server error: {exc}"}, status=500)

    def _handle_post(self):
        raw_len = self.headers.get("Content-Length", "0")
        try:
            content_length = int(raw_len)
        except (TypeError, ValueError):
            self._send_json({"success": False, "error": "Invalid Content-Length header"}, status=400)
            return

        if content_length < 0:
            self._send_json({"success": False, "error": "Negative Content-Length is invalid"}, status=400)
            return
        if content_length > MAX_REQUEST_BODY_BYTES:
            self._send_json(
                {"success": False, "error": f"Request payload exceeds {MAX_REQUEST_BODY_BYTES // (1024 * 1024)} MB limit"},
                status=413,
            )
            return

        if content_length > 0:
            raw_bytes = self.rfile.read(content_length)
            try:
                post_data = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                self._send_json({"success": False, "error": "Request body must be valid UTF-8 JSON"}, status=400)
                return
            if post_data.strip():
                try:
                    body = json.loads(post_data)
                except json.JSONDecodeError:
                    self._send_json({"success": False, "error": "Malformed JSON request body"}, status=400)
                    return
                if not isinstance(body, dict):
                    self._send_json({"success": False, "error": "JSON request body must be an object"}, status=400)
                    return
            else:
                body = {}
        else:
            body = {}

        path, query = self._extract_request_path()

        # 1. AUTH ROUTES (Vault restore NEVER runs prior to credential verification)
        if path == "/api/auth/register":
            username = str(body.get("username", ""))
            password = str(body.get("password", ""))
            res = aura_db.register_user(username, password)
            res["storage_status"] = aura_db.get_storage_status()
            if res.get("success") and res.get("token"):
                uid = int(res["user"]["id"])
                _resolve_workspace_dir(uid)
                res["csrf_token"] = aura_db.compute_csrf_token(res["token"])
                res["user_vault"] = aura_db.export_user_vault(uid)
                extra = [("Set-Cookie", self._build_session_cookie(res["token"]))]
                self._send_json(res, status=200, extra_headers=extra)
            else:
                status = 503 if res.get("storage_unavailable") else 400
                self._send_json(res, status=status)

        elif path == "/api/auth/login":
            username = str(body.get("username", ""))
            password = str(body.get("password", ""))
            res = aura_db.login_user(username, password)
            res["storage_status"] = aura_db.get_storage_status()
            if res.get("success") and res.get("token"):
                uid = int(res["user"]["id"])
                _resolve_workspace_dir(uid)
                # Only AFTER password authentication succeeds may the user sync their non-credential vault
                if isinstance(body.get("vault_backup"), dict):
                    aura_db.restore_user_vault(body["vault_backup"], authenticated_user_id=uid)
                res["csrf_token"] = aura_db.compute_csrf_token(res["token"])
                res["user_vault"] = aura_db.export_user_vault(uid)
                extra = [("Set-Cookie", self._build_session_cookie(res["token"]))]
                self._send_json(res, status=200, extra_headers=extra)
            else:
                status = 429 if "Too many failed" in str(res.get("error", "")) else (503 if res.get("storage_unavailable") else 401)
                self._send_json(res, status=status)

        elif path == "/api/auth/restore_vault":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "authenticated": False, "restored": False, "error": "Authentication required before vault sync"}, status=401)
                return
            vb = body.get("vault_backup")
            restored = aura_db.restore_user_vault(vb, authenticated_user_id=int(user["id"])) if isinstance(vb, dict) else False
            if restored:
                self._send_json({
                    "success": True,
                    "authenticated": True,
                    "restored": True,
                    "user": user,
                    "csrf_token": user.get("csrf_token"),
                    "storage_status": aura_db.get_storage_status(),
                    "user_vault": aura_db.export_user_vault(user["id"]),
                })
            else:
                self._send_json({"success": False, "authenticated": True, "restored": False, "error": "Invalid or unauthorized vault backup"}, status=400)

        elif path == "/api/auth/change_password":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            current_pw = str(body.get("current_password", ""))
            new_pw = str(body.get("new_password", ""))
            res = aura_db.change_user_password(user["id"], current_pw, new_pw)
            if not res.get("success"):
                self._send_json(res, status=400)
                return
            # Issue a fresh session for the user after revoking all prior sessions
            relogin = aura_db.login_user(user["username"], new_pw)
            extra = []
            if relogin.get("success") and relogin.get("token"):
                res["token"] = relogin["token"]
                res["csrf_token"] = aura_db.compute_csrf_token(relogin["token"])
                extra.append(("Set-Cookie", self._build_session_cookie(relogin["token"])))
            self._send_json(res, status=200, extra_headers=extra)

        elif path == "/api/auth/delete_account":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            pw = str(body.get("password", ""))
            uid = int(user["id"])
            res = aura_db.delete_user_account(uid, pw)
            if not res.get("success"):
                self._send_json(res, status=400)
                return
            user_ws = _resolve_workspace_dir(uid)
            shutil.rmtree(user_ws, ignore_errors=True)
            extra = [("Set-Cookie", self._build_session_cookie("", clear=True))]
            self._send_json(res, status=200, extra_headers=extra)

        elif path == "/api/auth/bootstrap_admin":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            bootstrap_token = str(body.get("bootstrap_token", ""))
            res = aura_db.bootstrap_admin_user(user["id"], bootstrap_token)
            self._send_json(res, status=200 if res.get("success") else 403)

        elif path == "/api/admin/set_role":
            if not self._is_authorized_admin(body):
                self._send_json({"success": False, "error": "Admin authentication required"}, status=401)
                return
            target_uid = _clamp_int(body.get("user_id"), -1, 1, 10**9)
            role = str(body.get("role", "user")).strip()
            if target_uid < 1 or role not in ("user", "admin"):
                self._send_json({"success": False, "error": "Valid user_id and role ('user' or 'admin') required"}, status=400)
                return
            ok = aura_db.set_user_role(target_uid, role)
            self._send_json({"success": ok, "user_id": target_uid, "role": role}, status=200 if ok else 404)

        elif path == "/api/auth/logout":
            token = ""
            auth_header = self.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
            if not token:
                token = self.headers.get("X-Auth-Token", "").strip()
            if not token:
                token = self._extract_cookie_token()
            if not token and isinstance(body.get("token"), str):
                token = body["token"].strip()
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
            title = str(body.get("title", "New Session"))[:120]
            thread_id = body.get("id") or body.get("thread_id")
            if thread_id is not None:
                thread_id = str(thread_id)[:64]
            thread = aura_db.create_user_thread(user_id, title, thread_id=thread_id)
            self._send_json({"success": True, "thread": thread})

        elif path == "/api/threads/rename":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            thread_id = str(body.get("thread_id", "")).strip()
            new_title = str(body.get("title", "")).strip()[:120]
            if not thread_id or not new_title:
                self._send_json({"success": False, "error": "thread_id and title required"}, status=400)
                return
            ok = aura_db.rename_user_thread(user["id"], thread_id, new_title)
            self._send_json({"success": ok})

        elif path == "/api/threads/pin":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            thread_id = str(body.get("thread_id", "")).strip()
            is_pinned = bool(body.get("is_pinned", False))
            if not thread_id:
                self._send_json({"success": False, "error": "thread_id required"}, status=400)
                return
            ok = aura_db.pin_user_thread(user["id"], thread_id, is_pinned)
            self._send_json({"success": ok})

        elif path == "/api/threads/delete":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            thread_id = str(body.get("thread_id", "")).strip()
            ok = aura_db.delete_user_thread(user["id"], thread_id)
            self._send_json({"success": ok})

        # 2B. CODING PROJECTS ROUTES
        elif path == "/api/projects/new":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            user_id = user["id"]
            name = str(body.get("name", "New Project"))[:100]
            company = str(body.get("company", ""))[:100]
            stack = str(body.get("stack", "Python"))[:80]
            proj_path = str(body.get("path", ""))[:260]
            description = str(body.get("description", ""))[:500]
            proj = aura_db.create_user_project(user_id, name, company, stack, proj_path, description)
            self._send_json({"success": True, "project": proj})

        elif path == "/api/projects/pin":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            proj_id = str(body.get("project_id", ""))
            is_pinned = bool(body.get("is_pinned", False))
            ok = aura_db.pin_user_project(user["id"], proj_id, is_pinned)
            self._send_json({"success": ok})

        elif path == "/api/projects/rename":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            proj_id = str(body.get("project_id", ""))
            new_name = str(body.get("name", "")).strip()[:100]
            if not proj_id or not new_name:
                self._send_json({"success": False, "error": "project_id and name required"}, status=400)
                return
            ok = aura_db.rename_user_project(user["id"], proj_id, new_name)
            self._send_json({"success": ok})

        elif path == "/api/projects/delete":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            proj_id = str(body.get("project_id", ""))
            ok = aura_db.delete_user_project(user["id"], proj_id)
            self._send_json({"success": ok})

        # 3. CHAT DISPATCH
        elif path == "/api/chat":
            user = self._get_auth_user(body)
            if not user:
                self._send_json(
                    {"reply": "Session expired or not logged in. Please sign in to save your conversation and execute tasks.", "error": "unauthorized"},
                    status=401,
                )
                return
            user_id = user["id"]
            prompt = str(body.get("prompt", "")).strip()
            thread_id = str(body.get("thread_id", "default"))[:64]
            raw_attachments = body.get("attachments", [])
            attachments = raw_attachments if isinstance(raw_attachments, list) else []
            if len(attachments) > 5:
                self._send_json({"error": "Maximum 5 attachments allowed per message"}, status=400)
                return
            permission_mode = str(body.get("mode", "auto_pilot"))
            approved = bool(body.get("approved", False))

            if not prompt and not attachments:
                self._send_json({"reply": "Please enter an instruction or attach a file."}, status=400)
                return

            display_prompt = prompt
            if attachments:
                att_names = [str(a.get("name", "attachment"))[:80] for a in attachments if isinstance(a, dict)]
                display_prompt += f"\n[📎 {len(att_names)} Attachment(s): {', '.join(att_names)}]"

            aura_db.save_message(user_id, thread_id, "user", display_prompt)

            prior_messages = aura_db.get_thread_messages(user_id, thread_id)
            conv_history = []
            for m in prior_messages[:-1]:
                role = "user" if m.get("role") == "user" else "model"
                txt = m.get("content", "")
                if txt:
                    conv_history.append({"role": role, "parts": [{"text": txt}]})

            brain = _create_user_brain(user)
            reply = brain.think_and_act(
                prompt,
                attachments=attachments,
                permission_mode=permission_mode,
                approved=approved,
                conversation_history=conv_history,
            )
            tools_used = getattr(brain, "last_tools", [])
            aura_db.save_message(user_id, thread_id, "assistant", reply, tools_used)

            self._send_json({
                "reply": reply,
                "tools": tools_used,
                "status": "completed",
                "user_vault": aura_db.export_user_vault(user_id),
            })

        # 3B. STREAMING CHAT DISPATCH (SSE)
        elif path == "/api/chat/stream":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"reply": "Session expired or not logged in.", "error": "unauthorized"}, status=401)
                return
            user_id = user["id"]
            prompt = str(body.get("prompt", "")).strip()
            thread_id = str(body.get("thread_id", "default"))[:64]
            raw_attachments = body.get("attachments", [])
            attachments = raw_attachments if isinstance(raw_attachments, list) else []
            if len(attachments) > 5:
                self._send_json({"error": "Maximum 5 attachments allowed per message"}, status=400)
                return
            permission_mode = str(body.get("mode", "auto_pilot"))
            approved = bool(body.get("approved", False))

            if not prompt and not attachments:
                self._send_json({"error": "Prompt or attachments required"}, status=400)
                return

            display_prompt = prompt
            if attachments:
                att_names = [str(a.get("name", "attachment"))[:80] for a in attachments if isinstance(a, dict)]
                display_prompt += f"\n[📎 {len(att_names)} Attachment(s): {', '.join(att_names)}]"

            aura_db.save_message(user_id, thread_id, "user", display_prompt)

            prior_messages = aura_db.get_thread_messages(user_id, thread_id)
            conv_history = []
            for m in prior_messages[:-1]:
                role = "user" if m.get("role") == "user" else "model"
                txt = m.get("content", "")
                if txt:
                    conv_history.append({"role": role, "parts": [{"text": txt}]})

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store")
            self.send_header("Connection", "keep-alive")
            self._apply_security_and_cors_headers()
            self.end_headers()

            brain = _create_user_brain(user)
            accumulated_text = ""
            tools_used = []

            try:
                for chunk in brain.think_and_act_stream(
                    prompt,
                    attachments=attachments,
                    permission_mode=permission_mode,
                    approved=approved,
                    conversation_history=conv_history,
                ):
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
            key = str(body.get("key", "")).strip()[:120]
            val = str(body.get("value", "")).strip()[:4000]
            if not key or not val:
                self._send_json({"success": False, "error": "Key and value required"}, status=400)
                return
            saved = aura_db.save_user_memory(user["id"], key, val)
            self._send_json({"success": bool(saved), "key": key, "value": val})

        elif path == "/api/memory/delete":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            key = str(body.get("key", "")).strip()
            ok = aura_db.delete_user_memory(user["id"], key)
            self._send_json({"success": ok, "deleted": key})

        # 5. SETTINGS ROUTE
        elif path == "/api/settings":
            user = self._get_auth_user(body)
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
            if isinstance(body.get("preferences"), dict):
                prefs = dict(saved.get("preferences") or {})
                if "temperature" in body["preferences"]:
                    prefs["temperature"] = _clamp_float(body["preferences"]["temperature"], 0.3, 0.0, 1.0)
                if "theme" in body["preferences"]:
                    prefs["theme"] = str(body["preferences"]["theme"])[:40]
                if "execution_mode" in body["preferences"]:
                    exec_mode = str(body["preferences"]["execution_mode"]).strip().lower()
                    if exec_mode in ("ask_first", "auto_pilot"):
                        prefs["execution_mode"] = exec_mode
                        from aura_permission_system import SecurityMode, permission_manager
                        sec_target = SecurityMode.STRICT_APPROVAL if exec_mode == "ask_first" else SecurityMode.WORKSPACE_SAFE
                        permission_manager.set_security_mode(sec_target, user_id=user["id"], is_admin=(user.get("role") in ("admin", "superuser")))
                saved["preferences"] = prefs
            if not aura_db.save_user_settings(user["id"], saved):
                self._send_json({"success": False, "error": "Could not save model settings"}, status=500)
                return
            user["settings"] = saved
            self._send_json({
                "success": True,
                "brain_settings": _selected_brain_settings(user),
                "preferences": saved.get("preferences", {}),
            })

        elif path == "/api/engines/search":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_agent import AuraAgent
            agent_inst = AuraAgent()
            keyword = str(body.get("keyword") or query.get("keyword", [""])[0])[:120]
            target_engine = body.get("engine") or query.get("engine", [None])[0]
            res = agent_inst.search_mesh_code(keyword, target_engine=target_engine)
            self._send_json({"success": True, "results": res})

        elif path == "/api/workspace/save":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            file_rel = str(body.get("path", ""))
            file_content = str(body.get("content", ""))
            ws = _resolve_workspace_dir(user["id"])
            target_p = _safe_resolve_under(ws, file_rel)
            if target_p is None:
                self._send_json({"success": False, "error": "Save path outside workspace is forbidden"}, status=403)
                return
            _atomic_write_text(target_p, file_content, encoding="utf-8")
            self._send_json({
                "success": True,
                "saved_path": target_p.relative_to(ws).as_posix(),
                "bytes": len(file_content),
            })

        elif path == "/api/terminal/exec":
            if not self._is_authorized_admin(body):
                self._send_json({"success": False, "error": "Unauthorized: Admin authentication required for terminal execution"}, status=401)
                return
            user = self._get_auth_user(body)
            cmd = str(body.get("command", ""))
            ws = _resolve_workspace_dir(user["id"] if user else None)
            if not cmd:
                self._send_json({"success": False, "error": "Command is required"}, status=400)
                return
            from aura_brain import is_safe_command
            is_safe, reason = is_safe_command(cmd)
            if not is_safe:
                self._send_json({"success": False, "command": cmd, "error": f"Security Sandbox: {reason}", "exit_code": 1}, status=403)
                return
            import subprocess
            try:
                if sys.platform == "win32":
                    shell_args = ["powershell", "-NoProfile", "-Command", cmd]
                else:
                    pwsh_bin = shutil.which("pwsh") or shutil.which("powershell")
                    shell_args = [pwsh_bin, "-NoProfile", "-Command", cmd] if pwsh_bin else ["/bin/sh", "-c", cmd]
                proc = subprocess.run(shell_args, cwd=str(ws), capture_output=True, text=True, timeout=30)
                self._send_json({
                    "success": proc.returncode == 0,
                    "command": cmd,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout[:32768],
                    "stderr": proc.stderr[:32768],
                })
            except Exception as e:
                self._send_json({"success": False, "command": cmd, "error": str(e), "exit_code": 1})

        elif path == "/api/game/world/generate":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            theme = str(body.get("theme", "gta_city"))[:40]
            chunks = _clamp_int(body.get("chunks"), 4, 1, 16)
            seed = _clamp_int(body.get("seed"), 42, 0, 10**9)
            from aura_game_engine import OpenWorldProceduralGenerator
            res = OpenWorldProceduralGenerator.generate_world(theme=theme, chunks=chunks, seed=seed)
            self._send_json(res)

        elif path == "/api/game/physics/simulate":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            steps = _clamp_int(body.get("steps"), 60, 1, 600)
            name = str(body.get("name", "car"))[:40]
            mass = _clamp_float(body.get("mass"), 1200.0, 0.1, 100000.0)
            pos_y = _clamp_float(body.get("pos_y"), 3.0, -1000.0, 1000.0)
            from aura_game_engine import JoltPhysicsEngine
            jolt = JoltPhysicsEngine()
            jolt.add_body(name, mass=mass, pos=(0, pos_y, 0), restitution=0.3)
            self._send_json(jolt.simulate(steps=steps))

        elif path == "/api/game/navmesh/pathfind":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            sx = _clamp_int(body.get("start_x"), 0, 0, 99)
            sy = _clamp_int(body.get("start_y"), 0, 0, 99)
            gx = _clamp_int(body.get("goal_x"), 10, 0, 99)
            gy = _clamp_int(body.get("goal_y"), 10, 0, 99)
            from aura_game_engine import RecastNavMeshRouter
            res = RecastNavMeshRouter.find_path(start=(sx, sy), goal=(gx, gy), grid_size=max(30, gx + 1, gy + 1, sx + 1, sy + 1))
            self._send_json(res)

        elif path == "/api/game/agent/train":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            episodes = _clamp_int(body.get("episodes"), 5, 1, 50)
            from aura_game_engine import MLAgentsCarlaTrainer
            res = MLAgentsCarlaTrainer.train_driving_agent(episodes=episodes)
            self._send_json(res)

        elif path == "/api/game/multiplayer/sync":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            count = _clamp_int(body.get("player_count"), 100, 2, 500)
            from aura_game_engine import AgonesNetcodeSynchronizer
            res = AgonesNetcodeSynchronizer.simulate_100_player_tick(player_count=count)
            self._send_json(res)

        elif path == "/api/game/project/export":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            proj = str(body.get("project_name", "open_world_demo"))[:64]
            from aura_game_engine import EngineProjectExporter
            res = EngineProjectExporter.export_project(project_name=proj, workspace_dir=_resolve_workspace_dir(user["id"]))
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/godot/build":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            proj = str(body.get("project_name", "CyberCraft3D"))[:64]
            from godot_engine_manager import GodotCarCraftingProjectBuilder
            try:
                res = GodotCarCraftingProjectBuilder.build_project(project_name=proj)
                self._send_json(res)
            except ValueError as ve:
                self._send_json({"success": False, "error": str(ve)}, status=400)

        elif path == "/api/godot/verify":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            proj = str(body.get("project_name", "CyberCraft3D"))[:64]
            from godot_engine_manager import AURA_GODOT_TRAINER
            try:
                res = AURA_GODOT_TRAINER.train_and_verify(project_name=proj)
                self._send_json(res)
            except ValueError as ve:
                self._send_json({"success": False, "error": str(ve)}, status=400)

        elif path == "/api/godot/launch":
            if not self._is_authorized_admin(body):
                self._send_json({"success": False, "error": "Admin authentication required to launch desktop game window"}, status=401)
                return
            proj = str(body.get("project_name", "CyberCraft3D"))[:64]
            from godot_engine_manager import AURA_GODOT_MANAGER, GAMES_WORKSPACE
            proj_dir = _safe_resolve_under(GAMES_WORKSPACE, proj)
            if proj_dir is None:
                self._send_json({"success": False, "error": "Invalid project_name"}, status=400)
                return
            res = AURA_GODOT_MANAGER.launch_windowed_game(proj_dir)
            self._send_json(res)

        elif path == "/api/pipeline/run":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            goal = str(body.get("goal", "Create a coding task"))[:1000]
            domain = body.get("domain")
            params = body.get("params", {}) if isinstance(body.get("params"), dict) else {}
            from aura_master_pipeline import AURA_PIPELINE
            res = AURA_PIPELINE.execute(goal=goal, domain=domain, params=params)
            self._send_json(res)

        elif path == "/api/media/image/generate":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            prompt = str(body.get("prompt", ""))[:1000]
            style = str(body.get("style", "auto"))[:40]
            aspect_ratio = str(body.get("aspect_ratio", "1:1"))[:10]
            from aura_media_engine import AURA_CINEMA
            res = AURA_CINEMA.create_cinematic_image(
                prompt,
                camera_style=style,
                aspect_ratio=aspect_ratio,
                workspace_dir=_resolve_workspace_dir(user["id"]),
            )
            self._send_json(res)

        elif path == "/api/media/image/transform":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            img_rel = str(body.get("image_path", ""))
            instruction = str(body.get("instruction", "iPhone portrait"))[:300]
            user_ws = _resolve_workspace_dir(user["id"])
            safe_inp = _safe_resolve_under(user_ws, img_rel)
            if safe_inp is None:
                self._send_json({"success": False, "error": "Image path must stay inside your workspace"}, status=403)
                return
            from aura_media_engine import AURA_CINEMA
            res = AURA_CINEMA.transform_existing_image(str(safe_inp), instruction, workspace_dir=user_ws)
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/media/image/remove_bg":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            img_rel = str(body.get("image_path", ""))
            user_ws = _resolve_workspace_dir(user["id"])
            safe_inp = _safe_resolve_under(user_ws, img_rel)
            if safe_inp is None:
                self._send_json({"success": False, "error": "Image path must stay inside your workspace"}, status=403)
                return
            from aura_media_engine import NativeSegmentationEngine
            out = safe_inp.parent / f"{safe_inp.stem}_nobg.png"
            res = NativeSegmentationEngine.remove_background(safe_inp, out)
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/media/video/generate":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            prompt = str(body.get("prompt", ""))[:1000]
            duration = _clamp_int(body.get("duration_sec"), 5, 1, 15)
            fps = _clamp_int(body.get("fps"), 24, 8, 30)
            motion = str(body.get("camera_motion", "dolly_zoom"))[:40]
            aspect = str(body.get("aspect_ratio", "16:9"))[:10]
            from aura_media_engine import AURA_CINEMA
            res = AURA_CINEMA.create_cinematic_video(
                prompt,
                duration_sec=duration,
                fps=fps,
                camera_motion=motion,
                aspect_ratio=aspect,
                workspace_dir=_resolve_workspace_dir(user["id"]),
            )
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/coderx/execute":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            goal = str(body.get("goal", ""))[:2000]
            filename = str(body.get("filename", "coderx_script.py"))[:200]
            cmd = str(body.get("test_command", "")).strip()
            max_iter = _clamp_int(body.get("max_iterations"), 5, 1, 10)
            is_admin = self._is_authorized_admin(body)
            if cmd and not is_admin:
                self._send_json(
                    {"success": False, "error": "Custom shell test_command requires administrator privileges"},
                    status=403,
                )
                return
            user_ws = _resolve_workspace_dir(user["id"])
            if _safe_resolve_under(user_ws, filename) is None:
                self._send_json({"success": False, "error": "Target filename must stay inside your workspace"}, status=403)
                return
            from coderx_engine import CoderXStateGraph
            engine = CoderXStateGraph(workspace=user_ws)
            res = engine.run(
                goal=goal,
                target_filename=filename,
                test_command=cmd,
                max_iterations=max_iter,
                allow_custom_command=is_admin,
            )
            self._send_json(res)

        elif path == "/api/coderx/patch":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            file_rel = str(body.get("path", ""))
            patch_text = str(body.get("patch", ""))
            user_ws = _resolve_workspace_dir(user["id"])
            target_p = _safe_resolve_under(user_ws, file_rel)
            if target_p is None:
                self._send_json({"success": False, "error": "Patch target escapes workspace boundary"}, status=403)
                return
            from coderx_engine import AiderDiffPatcher
            res = AiderDiffPatcher.apply_patch_string(target_p, patch_text, workspace_root=user_ws)
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/autonomous/mission":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            goal = str(body.get("goal", ""))[:2000]
            filename = str(body.get("filename", "mission_script.py"))[:200]
            user_ws = _resolve_workspace_dir(user["id"])
            if _safe_resolve_under(user_ws, filename) is None:
                self._send_json({"success": False, "error": "Filename escapes workspace boundary"}, status=403)
                return
            from aura_brain import tool_autonomous_code_loop
            res = tool_autonomous_code_loop(goal=goal, target_filename=filename, user_id=user["id"])
            self._send_json(res)

        elif path == "/api/engines/invoke":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            engine_key = str(body.get("engine", ""))[:80]
            action = str(body.get("action", "run"))[:80]
            params = dict(body.get("params") or {}) if isinstance(body.get("params"), dict) else {}
            if engine_key in ("OpenHands", "open-interpreter") and not self._is_authorized_admin(body):
                self._send_json({"success": False, "error": f"Engine '{engine_key}' command execution requires administrator privileges"}, status=403)
                return
            params.setdefault("workspace", str(_resolve_workspace_dir(user["id"])))
            from aura_engine_mesh import AURA_ENGINE_MESH
            res = AURA_ENGINE_MESH.invoke(engine_key, action=action, **params)
            self._send_json(res)

        elif path == "/api/permission/respond":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            req_id = str(body.get("id", "")).strip()
            decision = str(body.get("decision", "DENY")).strip()
            from aura_permission_system import permission_manager
            ok = permission_manager.respond_request(req_id, decision, user_id=user["id"])
            self._send_json({"success": ok, "id": req_id, "decision": decision}, status=200 if ok else 403)

        elif path == "/api/permission/mode":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mode = str(body.get("mode", "PROMPT_HIGH_RISK")).strip()
            from aura_permission_system import permission_manager
            ok = permission_manager.set_security_mode(
                mode,
                user_id=user["id"],
                is_admin=self._is_authorized_admin(body),
            )
            self._send_json(
                {"success": ok, "mode": permission_manager.get_security_mode(user["id"]).value},
                status=200 if ok else 403,
            )

        elif path == "/api/os/execute":
            if not self._is_authorized_admin(body):
                self._send_json({"success": False, "error": "Unauthorized: Admin authentication required for OS execution"}, status=401)
                return
            cmd = str(body.get("command", ""))
            from aura_brain import is_safe_command
            is_safe, reason = is_safe_command(cmd)
            if not is_safe:
                self._send_json({"success": False, "command": cmd, "error": f"Security Sandbox: {reason}"}, status=403)
                return
            as_admin = bool(body.get("as_admin", False))
            from aura_os_controller import laptop_controller
            res = laptop_controller.execute_powershell(cmd, as_admin=as_admin)
            self._send_json(res)

        elif path == "/api/os/read_file":
            if not self._is_authorized_admin(body):
                self._send_json({"success": False, "error": "Unauthorized: Admin authentication required for file read"}, status=401)
                return
            filepath = str(body.get("path", ""))
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
            filepath = str(body.get("path", ""))
            from aura_brain import validate_safe_path
            try:
                validated_p = validate_safe_path(filepath, allow_create=True)
            except PermissionError as pe:
                self._send_json({"success": False, "error": str(pe)}, status=403)
                return
            file_content = str(body.get("content", ""))
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

        elif path == "/api/os/brightness":
            if not self._is_authorized_admin(body):
                self._send_json({"success": False, "error": "Unauthorized: Admin authentication required"}, status=401)
                return
            level = int(body.get("level", 50))
            from aura_os_controller import laptop_controller
            self._send_json(laptop_controller.set_brightness(level))

        elif path == "/api/os/volume":
            if not self._is_authorized_admin(body):
                self._send_json({"success": False, "error": "Unauthorized: Admin authentication required"}, status=401)
                return
            level = int(body.get("level", 50))
            mute = bool(body.get("mute", False))
            from aura_os_controller import laptop_controller
            self._send_json(laptop_controller.set_volume(level, mute=mute))

        elif path == "/api/os/launch":
            if not self._is_authorized_admin(body):
                self._send_json({"success": False, "error": "Unauthorized: Admin authentication required"}, status=401)
                return
            app_name = str(body.get("app_name", body.get("app", "")))
            from aura_os_controller import laptop_controller
            self._send_json(laptop_controller.launch_app(app_name))

        # 8. FLAGSHIP REPOSITORIES HUB ROUTES
        elif path == "/api/flagship/openhands":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_flagship_repos import OPENHANDS_HUB
            res = OPENHANDS_HUB.execute_swe_task(
                task_prompt=str(body.get("task_prompt") or body.get("goal") or "Inspect project, fix login/auth bug, and run unit tests")[:1000],
                project_name=str(body.get("project_name", "openhands_workspace"))[:64],
                canvas_agent=str(body.get("canvas_agent", "openhands_codeact"))[:64],
                target_file=body.get("target_file"),
                schedule_cron=body.get("schedule_cron"),
            )
            self._send_json(res)

        elif path == "/api/flagship/open_interpreter":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            user_ws = _resolve_workspace_dir(user["id"])
            req_dir = body.get("target_dir")
            if req_dir:
                safe_dir = _safe_resolve_under(user_ws, str(req_dir), allow_root=True)
                if safe_dir is None:
                    self._send_json({"success": False, "error": "target_dir must remain inside your workspace"}, status=403)
                    return
                resolved_dir = str(safe_dir)
            else:
                resolved_dir = str(user_ws)
            from aura_flagship_repos import OPEN_INTERPRETER_HUB
            res = OPEN_INTERPRETER_HUB.execute_computer_use_task(
                prompt=str(body.get("prompt") or body.get("goal") or "Inspect workspace largest files and summarize.")[:1000],
                skill=str(body.get("skill", "auto"))[:40],
                harness=str(body.get("harness", "rust_codex_fast"))[:40],
                model=str(body.get("model", "gemini-flash-lite-latest"))[:60],
                target_dir=resolved_dir,
            )
            self._send_json(res)

        elif path == "/api/flagship/autogpt":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_flagship_repos import AUTOGPT_HUB
            res = AUTOGPT_HUB.build_and_run_workflow(
                goal=str(body.get("goal") or "Research potential customers, analyze website, and prepare outreach draft.")[:1000],
                surface=str(body.get("surface", "autopilot"))[:40],
                template_id=body.get("template_id"),
                trigger_type=str(body.get("trigger_type", "manual_or_api"))[:40],
            )
            self._send_json(res)

        elif path == "/api/flagship/pipeline":
            if not self._get_auth_user(body):
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_flagship_repos import run_flagship_trinity_pipeline
            res = run_flagship_trinity_pipeline(
                goal=str(body.get("goal") or "Build, test, and QA an enterprise authentication & customer workflow module end-to-end")[:1000],
                project_name=str(body.get("project_name", "aura_trinity_mission"))[:64],
                canvas_agent=str(body.get("canvas_agent", "openhands_codeact"))[:64],
                oi_harness=str(body.get("harness", "rust_codex_fast"))[:40],
            )
            self._send_json(res)

        # 9. AURA 10-SYSTEM OMNI-CORE ROUTES
        elif path == "/api/systems10/execute":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_10_systems import AURA_10_SYSTEMS
            sys_id = _clamp_int(body.get("system_id"), 1, 1, 10)
            goal = str(body.get("goal") or body.get("prompt") or "Architect, verify, and benchmark an enterprise AI system module")[:1000]
            res = AURA_10_SYSTEMS.execute_single_system(system_id=sys_id, goal=goal)
            self._send_json(res)

        elif path == "/api/systems10/omnipipeline":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_10_systems import AURA_10_SYSTEMS
            goal = str(body.get("goal") or body.get("prompt") or "Design, simulate, engineer, verify, and audit a full-stack autonomous system across all 10 AI cores")[:1000]
            res = AURA_10_SYSTEMS.run_10_system_omnipipeline(goal=goal, user_tag=user.get("username", "aura_operator"))
            self._send_json(res)

        else:
            self._send_json({"success": False, "error": "Not Found"}, status=404)


def make_server(host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), AuraWebHandler)


# Top-level serverless function entrypoint for Vercel (@vercel/python)
class handler(AuraWebHandler):
    pass

app = handler


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
    print("[*] Per-User Isolation Guard : ACTIVE (workspace/user_<id>)")
    print("-" * 65)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server shutdown gracefully.")


if __name__ == "__main__":
    run()
