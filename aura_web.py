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

import base64
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
import aura_membership
import aura_pro_studio
from aura_agent_orchestrator import AGENT_ORCHESTRATOR
from aura_brain import AuraBrain
from aura_computer_use import COMPUTER_USE
from aura_control_intelligence import CONTROL_HUB, redact_secrets
import aura_dev_studio
from aura_engine_base import EngineDispatchPlan, format_thought_block
from aura_jarvis_hub import JARVIS_HUB
from aura_live_actions import LIVE_ACTION_HUB
from aura_live_browser import LIVE_BROWSER
from aura_models_hub import AURA_MODEL_ROUTER
from aura_platform_ext import PLATFORM_EXT
from aura_workspace_tools import (
    WORKSPACE_TERMINAL,
    create_or_save_workspace_file,
    create_workspace_folder,
    delete_workspace_entry,
    list_workspace_fs_tree,
    rename_workspace_entry,
)
from aura_settings import AuraSettingsManager
from aura_voice_cloud import (
    VOICE_ORCHESTRATOR,
    audit_voice_hardware,
    build_language_policy_instruction,
    detect_preferred_language,
    prepare_text_for_speech,
)
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
        SETTINGS.config.get("brain_settings", {}).get("active_model", "gemini-3-flash-preview"),
    )
    if provider == "gemini" and model in ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash-lite"):
        model = "gemini-3-flash-preview"
    if not AuraSettingsManager.validate_model_selection(provider, model):
        provider, model = "gemini", "gemini-3-flash-preview"
    return {"active_provider": provider, "active_model": model}


def _create_user_brain(user: Dict[str, Any]) -> AuraBrain:
    selected = _selected_brain_settings(user)
    brain = AuraBrain(provider=selected["active_provider"], model=selected["active_model"])
    if isinstance(user, dict) and user.get("id") is not None:
        try:
            brain.user_id = int(user["id"])
        except (ValueError, TypeError):
            brain.user_id = None
        brain.user_role = str(user.get("role", "user") or "user").lower()
        user_brain = (user.get("settings") or {}).get("brain_settings") or {}
        if user_brain.get("api_key"):
            brain.api_key = str(user_brain["api_key"]).strip()
        prefs = (user.get("settings") or {}).get("preferences") or {}
        if "temperature" in prefs:
            brain.temperature = _clamp_float(prefs.get("temperature"), 0.3, 0.0, 1.0)
    return brain


def _prepare_chat_dispatch(
    user_id: int,
    prompt: str,
    body: Dict[str, Any],
    permission_mode: str,
    brain: AuraBrain,
) -> Tuple[str, str]:
    """Applies Sovereign reasoning-mode framing and enforces active JARVIS Kill Switch guardrails."""
    reasoning_mode = str(body.get("reasoning_mode", "fast") or "fast").strip().lower()
    dispatch_prompt = prompt
    if prompt and not prompt.startswith("/"):
        if reasoning_mode == "architect":
            dispatch_prompt = (
                "[REASONING MODE: ARCHITECT — Structure concisely with ## Plan, ## Implementation, ## Verification]\n\n"
                + prompt
            )
        elif reasoning_mode == "verifier":
            dispatch_prompt = (
                "[REASONING MODE: STRICT VERIFIER — Audit edge cases, security boundaries, and failure modes explicitly]\n\n"
                + prompt
            )
            brain.temperature = min(float(getattr(brain, "temperature", 0.3)), 0.2)

    effective_permission = "ask_first" if JARVIS_HUB.get_status(user_id).get("halted") else permission_mode
    return dispatch_prompt, effective_permission


def _prepare_aura_turn(
    user: Dict[str, Any],
    prompt: str,
    body: Dict[str, Any],
    permission_mode: str,
    brain: AuraBrain,
    membership: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, Optional[EngineDispatchPlan], Optional[str], str]:
    """Applies AURA 2.0 / 2.3 / 2.6 engine profile, membership rules & @file context, strict language policy, and Kill Switch guardrails."""
    raw_uid = user.get("id")
    try:
        user_id: Any = int(raw_uid)
    except (ValueError, TypeError):
        user_id = str(raw_uid or "guest")
    prefs = ((user.get("settings") or {}).get("preferences") or {})
    raw_tier = body.get("aura_model") or body.get("model_tier") or prefs.get("aura_model")
    if not raw_tier and isinstance(body.get("model"), str):
        raw_tier = AURA_MODEL_ROUTER.normalize_tier(body.get("model"))
    norm_tier = AURA_MODEL_ROUTER.normalize_tier(raw_tier) if raw_tier else None
    voice_turn = bool(body.get("voice_turn", False))
    pref_lang = str(body.get("preferred_language") or body.get("language") or "auto")
    resolved_lang = detect_preferred_language(prompt, None if pref_lang == "auto" else pref_lang)
    brain.voice_turn_mode = voice_turn
    brain.thinking_level = "minimal" if voice_turn else None

    dispatch_prompt, effective_permission = _prepare_chat_dispatch(
        user_id, prompt, body, permission_mode, brain
    )
    if not prompt or prompt.startswith("/"):
        return dispatch_prompt, effective_permission, None, norm_tier, resolved_lang

    mem = membership or aura_membership.resolve_user_membership(user)
    ctx_block = ""
    raw_ctx_files = body.get("context_files")
    if int(mem.get("rank", 0)) >= 1 and isinstance(raw_ctx_files, list) and raw_ctx_files and isinstance(user_id, int):
        ctx_res = aura_pro_studio.read_context_files(_resolve_workspace_dir(user_id), [str(p) for p in raw_ctx_files[:6]])
        ctx_block = ctx_res.get("context_block") or ""
    tier_profile = aura_membership.build_tier_system_profile(mem, context_files_block=ctx_block)

    lang_policy = build_language_policy_instruction(resolved_lang, voice_turn=voice_turn)
    if voice_turn or not norm_tier:
        if voice_turn and getattr(brain, "provider", "gemini") == "gemini":
            brain.model = "gemini-3-flash-preview"
        prefix = f"{lang_policy}\n\n{tier_profile}" if (tier_profile and not voice_turn) else lang_policy
        return f"{prefix}\n\n{dispatch_prompt}", effective_permission, None, norm_tier, resolved_lang

    reasoning_mode = str(body.get("reasoning_mode", "fast") or "fast").strip().lower()
    plan = AURA_MODEL_ROUTER.prepare_turn(user_id, norm_tier, prompt, reasoning_mode=reasoning_mode)
    if brain.provider == "gemini" and getattr(plan, "preferred_llm", ""):
        brain.model = plan.preferred_llm
    if reasoning_mode == "fast":
        brain.temperature = plan.temperature
        brain.thinking_level = "minimal" if (norm_tier == "aura-2.0" or int(mem.get("rank", 0)) >= 1) else "low"
    elif reasoning_mode == "deep" and int(mem.get("rank", 0)) >= 2:
        brain.thinking_level = "high"
    elif reasoning_mode == "verifier":
        brain.thinking_level = "low"
    profile_chunk = f"\n\n{tier_profile}" if tier_profile else ""
    framed_prompt = f"{lang_policy}{profile_chunk}\n\n{plan.system_framing}\n\n{dispatch_prompt}"
    return framed_prompt, effective_permission, plan, norm_tier, resolved_lang


def _build_conversation_history(
    user_id: int,
    thread_id: str,
    window_limit: int = 16,
    recent_char_cap: int = 3500,
    older_char_cap: int = 1200,
) -> List[Dict[str, Any]]:
    """Builds a compacted, alternating-role Gemini history slice."""
    prior_messages = aura_db.get_thread_messages(user_id, thread_id)[:-1]
    if not prior_messages:
        return []
    window = prior_messages[-max(1, int(window_limit)):]
    conv_history: List[Dict[str, Any]] = []
    total = len(window)
    for idx, m in enumerate(window):
        role = "user" if m.get("role") == "user" else "model"
        txt = str(m.get("content", "") or "").strip()
        if not txt:
            continue
        if role == "model" and (txt.startswith("Understood. You said:") or txt.startswith("Hello! I heard you.")):
            continue
        max_chars = recent_char_cap if idx >= total - 4 else older_char_cap
        if len(txt) > max_chars:
            txt = txt[:max_chars] + "\n...[trimmed for speed]"
        if conv_history and conv_history[-1]["role"] == role:
            conv_history[-1]["parts"][0]["text"] += "\n" + txt
        else:
            conv_history.append({"role": role, "parts": [{"text": txt}]})
    return conv_history


DEFAULT_ALLOWED_ORIGINS = {
    "http://127.0.0.1:5050",
    "http://localhost:5050",
    "http://127.0.0.1:5051",
    "http://localhost:5051",
    "http://127.0.0.1:5052",
    "http://localhost:5052",
    "https://aura-agent.vercel.app",
    "https://aura-agent-78dz.vercel.app",
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
    "frame-src 'self' http://127.0.0.1:* http://localhost:* blob: data:; "
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
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS, HEAD")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token, X-CSRF-Token, X-Gemini-Key, X-Aura-Membership, X-Admin-Vault-Token")

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

    def _extract_account_proofs_map(self) -> Dict[str, str]:
        """Reads the persistent HttpOnly `aura_acct_proofs` map of recent encrypted `aura_ap1.` proofs."""
        raw_cookie = self.headers.get("Cookie", "")
        if not raw_cookie:
            return {}
        try:
            cookie = SimpleCookie()
            cookie.load(raw_cookie)
            if "aura_acct_proofs" not in cookie:
                return {}
            val = cookie["aura_acct_proofs"].value.strip()
            if not val:
                return {}
            padded = val + "=" * (-len(val) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
            if not isinstance(decoded, dict):
                return {}
            clean: Dict[str, str] = {}
            for k, v in decoded.items():
                ku = str(k or "").strip().lower()
                pv = str(v or "").strip()
                if ku and pv.startswith("aura_ap1.") and not ku.startswith("guest_"):
                    clean[ku] = pv
            return clean
        except Exception:
            return {}

    def _get_cookie_account_proof(self, username: str) -> str:
        uname = str(username or "").strip().lower()
        if not uname:
            return ""
        return self._extract_account_proofs_map().get(uname, "")

    def _build_account_proofs_cookie(self, proofs_map: Dict[str, str]) -> str:
        is_https = bool(os.environ.get("VERCEL")) or (self.headers.get("X-Forwarded-Proto", "").lower() == "https")
        secure_attr = "; Secure" if is_https else ""
        # Cap at 5 most recent named accounts so cookie stays compact (< 2.5 KB)
        items = [
            (str(k).strip().lower(), str(v).strip())
            for k, v in (proofs_map or {}).items()
            if str(k).strip() and str(v).strip().startswith("aura_ap1.") and not str(k).strip().lower().startswith("guest_")
        ][-5:]
        if not items:
            return f"aura_acct_proofs=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict{secure_attr}"
        encoded = base64.urlsafe_b64encode(
            json.dumps(dict(items), separators=(",", ":")).encode("utf-8")
        ).decode("ascii").rstrip("=")
        return f"aura_acct_proofs={encoded}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Strict{secure_attr}"

    def _build_updated_account_proof_cookie(self, username: str, proof: str = "", remove: bool = False) -> Optional[str]:
        uname = str(username or "").strip().lower()
        if not uname or uname.startswith("guest_"):
            return None
        cur = self._extract_account_proofs_map()
        if remove:
            if uname not in cur:
                return None
            cur.pop(uname, None)
            return self._build_account_proofs_cookie(cur)
        if not proof or not str(proof).startswith("aura_ap1."):
            return None
        cur.pop(uname, None)
        cur[uname] = str(proof).strip()
        return self._build_account_proofs_cookie(cur)

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

    def _resolve_membership(self, user: Dict[str, Any], body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        proof = str(self.headers.get("X-Aura-Membership") or "").strip()
        if not proof and isinstance(body, dict):
            proof = str(body.get("membership_proof") or "").strip()
        return aura_membership.resolve_user_membership(user, membership_proof=proof)

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

        if used_cookie and getattr(self, "command", "GET").upper() in ("POST", "DELETE"):
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
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
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

        elif path in ("/manifest.json", "/sw.js", "/api/pwa/icon.svg"):
            if path == "/api/pwa/icon.svg":
                svg_data = (
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192">'
                    '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
                    '<stop offset="0%" stop-color="#0066ff"/><stop offset="100%" stop-color="#00d4ff"/>'
                    '</linearGradient></defs>'
                    '<rect width="192" height="192" rx="44" fill="#0d0e12"/>'
                    '<rect x="18" y="18" width="156" height="156" rx="34" fill="url(#g)"/>'
                    '<path d="M108 38L58 106h36l-10 48 50-68H98z" fill="#ffffff"/>'
                    '</svg>'
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(svg_data)))
                self.send_header("Connection", "close")
                self._apply_security_and_cors_headers()
                self.end_headers()
                self.wfile.write(svg_data)
                return
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

        elif path == "/api/workspace/preview" or path.startswith("/api/workspace/preview/"):
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            rel_part = urllib.parse.unquote(path[len("/api/workspace/preview"):]).lstrip("/")
            if not rel_part:
                rel_part = str(query.get("path", ["index.html"])[0] or "index.html")
            ws = _resolve_workspace_dir(user["id"])
            target_file = _safe_resolve_under(ws, rel_part)
            if target_file is None:
                self._send_json({"success": False, "error": "Path traversal restricted"}, status=403)
                return
            if target_file.is_dir():
                target_file = target_file / "index.html"
            if not target_file.exists() or not target_file.is_file():
                self._send_json({"success": False, "error": "Preview file not found"}, status=404)
                return
            from aura_workspace_ide import SAFE_PREVIEW_MIME_TYPES
            ext = target_file.suffix.lower()
            ctype = SAFE_PREVIEW_MIME_TYPES.get(ext)
            if not ctype:
                self._send_json({"success": False, "error": f"Unsupported preview file type: {ext}"}, status=415)
                return
            data = target_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "private, no-store")
            self.send_header("Connection", "close")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:; "
                "img-src 'self' data: blob: https:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; frame-ancestors 'self'; object-src 'none'"
            )
            self.end_headers()
            self.wfile.write(data)
            return

        elif path == "/api/workspace/devserver/status":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_workspace_ide import WORKSPACE_DEV_MANAGER
            servers = WORKSPACE_DEV_MANAGER.list_servers(user_id=user["id"])
            self._send_json({
                "success": True,
                "serverless": bool(os.environ.get("VERCEL")),
                "servers": servers,
            })

        elif path == "/api/auth/me":
            user = self._get_auth_user()
            storage_status = aura_db.get_storage_status()
            if not user:
                self._send_json({"authenticated": False, "storage_status": storage_status}, status=401)
            else:
                # Auto-heal ephemeral shadow row on cold serverless container using HttpOnly account proof cookie
                cookie_proof = self._get_cookie_account_proof(user["username"])
                if cookie_proof:
                    aura_db.heal_shadow_user_credentials(user["id"], user["username"], cookie_proof)
                real_proof = aura_db.get_account_proof_for_user(user["id"])
                extra_headers = []
                if real_proof:
                    ap_cookie = self._build_updated_account_proof_cookie(user["username"], real_proof)
                    if ap_cookie:
                        extra_headers.append(("Set-Cookie", ap_cookie))
                mem = self._resolve_membership(user)
                quota = aura_membership.get_user_quota_status(user, mem)
                payload = {
                    "authenticated": True,
                    "user": user,
                    "csrf_token": user.get("csrf_token"),
                    "storage_status": storage_status,
                    "membership": mem,
                    "quota": quota,
                    "is_key_admin": aura_membership.is_key_admin_user(user),
                    "subscription_contact": aura_membership.SUBSCRIPTION_CONTACT,
                    "user_vault": aura_db.export_user_vault(user["id"]),
                }
                if real_proof:
                    payload["account_proof"] = real_proof
                self._send_json(payload, extra_headers=extra_headers or None)

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
            prefs = (user.get("settings") or {}).get("preferences", {})
            active_aura = AURA_MODEL_ROUTER.normalize_tier(prefs.get("aura_model")) or AURA_MODEL_ROUTER.get_user_tier(user["id"])
            mem = self._resolve_membership(user)
            quota = aura_membership.get_user_quota_status(user, mem)
            self._send_json({
                "success": True,
                "brain_settings": _selected_brain_settings(user),
                "security_mode": permission_manager.get_security_mode(user["id"]).value,
                "user_preferences": prefs,
                "active_aura_model": active_aura,
                "aura_models": AURA_MODEL_ROUTER.list_catalog(),
                "providers": AuraSettingsManager.public_model_catalog(),
                "gemini_key_configured": bool(BRAIN.api_key and not BRAIN.api_key.startswith("YOUR_")),
                "membership": mem,
                "quota": quota,
                "membership_tiers": aura_membership.list_public_tiers(),
                "is_key_admin": aura_membership.is_key_admin_user(user),
                "subscription_contact": aura_membership.SUBSCRIPTION_CONTACT,
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

        elif path in ("/api/bharatcode10/overview", "/api/sovereign10/overview"):
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_bharatcode_top10 import BHARATCODE_TOP10_SUITE
            self._send_json(BHARATCODE_TOP10_SUITE.get_overview())

        elif path == "/api/antigravity/overview":
            if not self._get_auth_user():
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_antigravity_core import AURA_ANTIGRAVITY_CORE
            self._send_json(AURA_ANTIGRAVITY_CORE.get_overview())

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

        elif path == "/api/health":
            self._send_json({
                "success": True,
                "status": "ok",
                "service": "aura-core",
                "models": ["aura-2.0", "aura-2.3", "aura-2.6"],
            })

        elif path == "/api/membership/status":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user)
            quota = aura_membership.get_user_quota_status(user, mem)
            self._send_json({
                "success": True,
                "membership": mem,
                "quota": quota,
                "tiers": aura_membership.list_public_tiers(),
                "contact": aura_membership.SUBSCRIPTION_CONTACT,
                "is_key_admin": aura_membership.is_key_admin_user(user),
                "os_actions": aura_pro_studio.OS_ACTION_CATALOG,
            })

        elif path == "/api/admin/keys/list":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            vault_tok = str(self.headers.get("X-Admin-Vault-Token") or "").strip()
            if not aura_membership.verify_admin_vault_token(user, vault_tok):
                self._send_json({"success": False, "error": "Forbidden: Admin Key Vault access requires @ig.ahmed.irl vault authentication."}, status=403)
                return
            status_f = str((query.get("status") or ["all"])[0])[:24]
            search_q = str((query.get("search") or [""])[0])[:120]
            self._send_json(aura_membership.admin_list_keys(status_filter=status_f, search=search_q))

        elif path == "/api/pro/index":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user)
            if int(mem.get("rank", 0)) < 3:
                self._send_json({
                    "success": False,
                    "error": "Codebase AST & Symbol Indexer requires AURA Sovereign (Plan 1) or higher. Activate a key in Settings.",
                    "required_rank": 3,
                }, status=403)
                return
            self._send_json(aura_pro_studio.index_workspace_symbols(_resolve_workspace_dir(user["id"])))

        elif path == "/api/pro/templates":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            templates = [
                {"id": tid, "name": spec["name"], "stack": spec["stack"], "files": list(spec["files"].keys())}
                for tid, spec in aura_pro_studio.PROJECT_TEMPLATES.items()
            ]
            self._send_json({"success": True, "templates": templates})

        elif path == "/api/pro/snapshots":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user)
            if int(mem.get("rank", 0)) < 3:
                self._send_json({"success": False, "error": "Rollback snapshots require AURA Sovereign (Plan 1) or higher.", "required_rank": 3}, status=403)
                return
            self._send_json({"success": True, "snapshots": aura_pro_studio.list_workspace_snapshots(_resolve_workspace_dir(user["id"]))})

        elif path == "/api/models/aura":
            user = self._get_auth_user()
            active_tier = "aura-2.3"
            if user:
                prefs = (user.get("settings") or {}).get("preferences") or {}
                active_tier = AURA_MODEL_ROUTER.normalize_tier(prefs.get("aura_model")) or AURA_MODEL_ROUTER.get_user_tier(user["id"])
            self._send_json({
                "success": True,
                "active_aura_model": active_tier,
                "models": AURA_MODEL_ROUTER.list_catalog(),
            })

        elif path == "/api/jarvis/status":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            self._send_json(JARVIS_HUB.get_status(user["id"]))

        elif self._handle_agent_workspace_get(path, query):
            return

        elif self._handle_voice_get(path, query):
            return

        else:
            self._send_json({"success": False, "error": "Not Found"}, status=404)

    def _handle_agent_workspace_get(self, path: str, query: Dict[str, List[str]]) -> bool:
        """Handles GET routes for AURA Live Browser, Computer Use, and Live Action View."""
        if path == "/api/browser/state":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            inc_shot = str((query.get("screenshot") or ["1"])[0]).lower() not in ("0", "false", "no")
            self._send_json(LIVE_BROWSER.get_state(user["id"], include_screenshot=inc_shot))
            return True

        if path == "/api/computer/status":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            self._send_json(COMPUTER_USE.get_status(user["id"]))
            return True

        if path == "/api/computer/screenshot":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            w = _clamp_int((query.get("width") or [1280])[0], 1280, 480, 1440)
            q = _clamp_int((query.get("quality") or [62])[0], 62, 35, 85)
            snap = COMPUTER_USE.capture_screen_frame(user["id"], width=w, quality=q)
            snap.pop("jpeg_bytes", None)
            self._send_json(snap)
            return True

        if path == "/api/computer/stream":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            fps = _clamp_float((query.get("fps") or [3.0])[0], 3.0, 0.5, 8.0)
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Connection", "close")
            self._apply_security_and_cors_headers()
            self.end_headers()
            try:
                for chunk in COMPUTER_USE.iter_mjpeg_frames(user["id"], max_seconds=45.0, fps=fps):
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            return True

        if path == "/api/computer/ui_tree":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            max_nodes = _clamp_int((query.get("max_nodes") or [28])[0], 28, 5, 40)
            self._send_json(COMPUTER_USE.inspect_ui_tree(user["id"], max_nodes=max_nodes))
            return True

        if path == "/api/actions/feed":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            src = str((query.get("source") or ["all"])[0])[:24]
            lim = _clamp_int((query.get("limit") or [50])[0], 50, 1, 120)
            since = _clamp_int((query.get("since_id") or [0])[0], 0, 0, 10_000_000)
            inc_thumbs = str((query.get("thumbs") or ["1"])[0]).lower() not in ("0", "false", "no")
            self._send_json(
                LIVE_ACTION_HUB.get_feed(
                    user["id"],
                    source=src,
                    limit=lim,
                    since_id=since,
                    include_thumbnails=inc_thumbs,
                )
            )
            return True

        if path == "/api/orchestrator/dashboard":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            self._send_json(AGENT_ORCHESTRATOR.get_dashboard(user["id"]))
            return True

        if path == "/api/workspace/fs/tree":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            search_q = str((query.get("search") or [""])[0])[:120]
            self._send_json(list_workspace_fs_tree(user["id"], _resolve_workspace_dir(user["id"]), search=search_q))
            return True

        if path == "/api/workspace/terminal/history":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            self._send_json(WORKSPACE_TERMINAL.get_history(user["id"]))
            return True

        # --- PART 1-3 GET ROUTES (DEV STUDIO, GIT, DELIVERABLES, AUTOMATION, CONTROL & REMOTE) ---
        if path == "/api/dev/codebase_map":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            self._send_json(aura_dev_studio.analyze_codebase_architecture(user["id"], _resolve_workspace_dir(user["id"])))
            return True

        if path == "/api/git/status":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            self._send_json(aura_dev_studio.git_get_status_and_diffs(user["id"], _resolve_workspace_dir(user["id"])))
            return True

        if path == "/api/snapshots/list":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            self._send_json({"success": True, "snapshots": aura_dev_studio.list_project_snapshots(_resolve_workspace_dir(user["id"]))})
            return True

        if path == "/api/deliverables/list":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            self._send_json(aura_dev_studio.VISUAL_DELIVERABLES.list_artifacts(user["id"]))
            return True

        if path == "/api/platform/overview":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            self._send_json(PLATFORM_EXT.get_overview(user["id"], _resolve_workspace_dir(user["id"])))
            return True

        if path == "/api/control/overview":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            self._send_json(CONTROL_HUB.get_control_and_intelligence_overview(user["id"], _resolve_workspace_dir(user["id"])))
            return True

        if path == "/api/control/evaluate":
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            self._send_json(CONTROL_HUB.evaluate_agents(user["id"], _resolve_workspace_dir(user["id"])))
            return True

        if path == "/api/remote/status":
            rem_tok = str(self.headers.get("X-Remote-Token") or (query.get("token") or [""])[0]).strip()
            uid = CONTROL_HUB.resolve_remote_token(rem_tok)
            if not uid:
                self._send_json({"success": False, "error": "Valid X-Remote-Token required"}, status=401)
                return True
            ws = _resolve_workspace_dir(int(uid)) if uid.isdigit() else _resolve_workspace_dir(None)
            self._send_json({
                "success": True,
                "remote_authorized": True,
                "orchestrator": AGENT_ORCHESTRATOR.get_dashboard(uid),
                "control": CONTROL_HUB.get_control_and_intelligence_overview(uid, ws),
            })
            return True

        return False

    def _voice_subpath(self, path: str) -> str:
        return path[4:] if path.startswith("/api/v1/") else path

    def _handle_voice_get(self, path: str, query: Dict[str, List[str]]) -> bool:
        vp = self._voice_subpath(path)
        if vp == "/v1/voices":
            lang_f = query.get("language", [None])[0]
            gender_f = query.get("gender", [None])[0]
            comm_only = str(query.get("commercial_only", "")).lower() in ("1", "true", "yes")
            self._send_json({
                "success": True,
                "voices": VOICE_ORCHESTRATOR.list_voices(language=lang_f, gender=gender_f, commercial_only=comm_only),
                "engines": VOICE_ORCHESTRATOR.get_engine_statuses(),
            })
            return True
        if vp == "/v1/languages":
            self._send_json({"success": True, "languages": VOICE_ORCHESTRATOR.list_languages()})
            return True
        if vp in ("/v1/voice/hardware", "/api/voice/hardware", "/v1/hardware"):
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            self._send_json({
                "success": True,
                "hardware": audit_voice_hardware(),
                "engines": VOICE_ORCHESTRATOR.get_engine_statuses(),
            })
            return True
        if vp.startswith("/v1/speech/"):
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            sid = vp[len("/v1/speech/"):].strip("/")
            art = VOICE_ORCHESTRATOR.get_artifact_by_speech_id(sid, user["id"])
            if not art:
                self._send_json({"success": False, "error": "Speech job not found"}, status=404)
                return True
            self._send_json({"success": True, "speech": art.to_public_dict()})
            return True
        if vp.startswith("/v1/audio/"):
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            aid = vp[len("/v1/audio/"):].strip("/")
            loaded = VOICE_ORCHESTRATOR.get_audio_bytes(aid, user["id"])
            if not loaded:
                self._send_json({"success": False, "error": "Audio artifact not found"}, status=404)
                return True
            audio_bytes, art = loaded
            self.send_response(200)
            self.send_header("Content-Type", art.content_type)
            self.send_header("Content-Length", str(len(audio_bytes)))
            self.send_header("Cache-Control", "private, max-age=300")
            self.send_header("Content-Disposition", f'inline; filename="{art.audio_id}.{art.format}"')
            self.send_header("Connection", "close")
            self._apply_security_and_cors_headers()
            self.end_headers()
            self.wfile.write(audio_bytes)
            return True
        if vp.startswith("/v1/calls/"):
            user = self._get_auth_user()
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            cid = vp[len("/v1/calls/"):].strip("/")
            sess = VOICE_ORCHESTRATOR.get_call_session(cid, user["id"])
            if not sess:
                self._send_json({"success": False, "error": "Call session not found"}, status=404)
                return True
            self._send_json({"success": True, "call": sess})
            return True
        return False

    def do_DELETE(self):
        try:
            path, _ = self._extract_request_path()
            vp = self._voice_subpath(path)
            if vp.startswith("/v1/audio/"):
                user = self._get_auth_user()
                if not user:
                    self._send_json({"success": False, "error": "Authentication required"}, status=401)
                    return
                aid = vp[len("/v1/audio/"):].strip("/")
                ok = VOICE_ORCHESTRATOR.delete_audio(aid, user["id"])
                self._send_json({"success": ok, "deleted": aid if ok else None}, status=200 if ok else 404)
                return
            self._send_json({"success": False, "error": "Not Found"}, status=404)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
        except Exception as exc:
            self._send_json({"success": False, "error": f"Server error: {exc}"}, status=500)

    def do_POST(self):
        try:
            self._handle_post()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
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
                ap_cookie = self._build_updated_account_proof_cookie(res["user"]["username"], res.get("account_proof", ""))
                if ap_cookie:
                    extra.append(("Set-Cookie", ap_cookie))
                self._send_json(res, status=200, extra_headers=extra)
            else:
                status = 503 if res.get("storage_unavailable") else 400
                self._send_json(res, status=status)

        elif path == "/api/auth/login":
            username = str(body.get("username", ""))
            password = str(body.get("password", ""))
            vault_backup = body.get("vault_backup") if isinstance(body.get("vault_backup"), dict) else None
            account_proof = str(body.get("account_proof", "") or "") or None
            cookie_proof = self._get_cookie_account_proof(username)
            backup_proofs = [cookie_proof] if cookie_proof else None
            res = aura_db.login_user(
                username,
                password,
                vault_backup=vault_backup,
                account_proof=account_proof,
                backup_proofs=backup_proofs,
            )
            res["storage_status"] = aura_db.get_storage_status()
            if res.get("success") and res.get("token"):
                uid = int(res["user"]["id"])
                _resolve_workspace_dir(uid)
                # Only AFTER password authentication succeeds may the user sync their non-credential vault
                if vault_backup and not res.get("vault_restored"):
                    aura_db.restore_user_vault(vault_backup, authenticated_user_id=uid)
                res["csrf_token"] = aura_db.compute_csrf_token(res["token"])
                res["user_vault"] = aura_db.export_user_vault(uid)
                extra = [("Set-Cookie", self._build_session_cookie(res["token"]))]
                ap_cookie = self._build_updated_account_proof_cookie(res["user"]["username"], res.get("account_proof", ""))
                if ap_cookie:
                    extra.append(("Set-Cookie", ap_cookie))
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
            acct_proof = str(body.get("account_proof", "") or "") or self._get_cookie_account_proof(user["username"]) or None
            res = aura_db.change_user_password(user["id"], current_pw, new_pw, account_proof=acct_proof)
            if not res.get("success"):
                self._send_json(res, status=400)
                return
            # Issue a fresh session for the user after revoking all prior sessions
            relogin = aura_db.login_user(user["username"], new_pw)
            extra = []
            if relogin.get("success") and relogin.get("token"):
                res["token"] = relogin["token"]
                res["csrf_token"] = aura_db.compute_csrf_token(relogin["token"])
                if relogin.get("account_proof"):
                    res["account_proof"] = relogin["account_proof"]
                extra.append(("Set-Cookie", self._build_session_cookie(relogin["token"])))
            ap_cookie = self._build_updated_account_proof_cookie(user["username"], res.get("account_proof", ""))
            if ap_cookie:
                extra.append(("Set-Cookie", ap_cookie))
            self._send_json(res, status=200, extra_headers=extra)

        elif path == "/api/auth/delete_account":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            pw = str(body.get("password", ""))
            uid = int(user["id"])
            acct_proof = str(body.get("account_proof", "") or "") or self._get_cookie_account_proof(user["username"]) or None
            res = aura_db.delete_user_account(uid, pw, account_proof=acct_proof)
            if not res.get("success"):
                self._send_json(res, status=400)
                return
            user_ws = _resolve_workspace_dir(uid)
            shutil.rmtree(user_ws, ignore_errors=True)
            extra = [("Set-Cookie", self._build_session_cookie("", clear=True))]
            rm_cookie = self._build_updated_account_proof_cookie(user["username"], remove=True)
            if rm_cookie:
                extra.append(("Set-Cookie", rm_cookie))
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
            self._send_json({
                "success": True,
                "thread": thread,
                "user_vault": aura_db.export_user_vault(user_id),
            })

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
            self._send_json({
                "success": ok,
                "user_vault": aura_db.export_user_vault(user["id"]) if ok else None,
            })

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
            self._send_json({
                "success": ok,
                "user_vault": aura_db.export_user_vault(user["id"]) if ok else None,
            })

        elif path == "/api/threads/delete":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            thread_id = str(body.get("thread_id", "")).strip()
            ok = aura_db.delete_user_thread(user["id"], thread_id)
            self._send_json({
                "success": ok,
                "user_vault": aura_db.export_user_vault(user["id"]) if ok else None,
            })

        elif path == "/api/threads/sync":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            owner_username = str(body.get("username") or user["username"])
            threads_payload = body.get("threads") if isinstance(body.get("threads"), list) else []
            messages_payload = body.get("messages") if isinstance(body.get("messages"), list) else []
            memories_payload = body.get("user_memories") if isinstance(body.get("user_memories"), list) else []
            projects_payload = body.get("projects") if isinstance(body.get("projects"), list) else []
            sync_res = aura_db.sync_user_history(
                authenticated_user_id=int(user["id"]),
                owner_username=owner_username,
                threads=threads_payload,
                messages=messages_payload,
                user_memories=memories_payload,
                projects=projects_payload,
            )
            if not sync_res.get("success"):
                self._send_json(sync_res, status=int(sync_res.get("status", 400)))
                return
            self._send_json({
                "success": True,
                "restored_threads": sync_res.get("restored_threads", 0),
                "restored_messages": sync_res.get("restored_messages", 0),
                "threads": aura_db.get_user_threads(user["id"]),
                "user_vault": aura_db.export_user_vault(user["id"]),
            })

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
            prompt = str(body.get("prompt", "")).strip()[:32000]
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

            membership = self._resolve_membership(user, body)
            quota_ok, quota_status = aura_membership.check_and_consume_chat_quota(user, prompt, membership)
            if not quota_ok:
                self._send_json({
                    "success": False,
                    "error": "daily_limit_reached",
                    "reply": (
                        f"Daily chat limit reached ({quota_status['used']}/{quota_status['limit']} chats on {membership['name']}). "
                        f"Quota refreshes automatically in {quota_status['reset_label']}. "
                        f"Activate a membership key in Settings for expanded or unlimited access."
                    ),
                    "quota": quota_status,
                    "membership": membership,
                }, status=429)
                return

            display_prompt = prompt
            if attachments:
                att_names = [str(a.get("name", "attachment"))[:80] for a in attachments if isinstance(a, dict)]
                display_prompt += f"\n[📎 {len(att_names)} Attachment(s): {', '.join(att_names)}]"

            aura_db.save_message(user_id, thread_id, "user", display_prompt)
            is_voice_turn = bool(body.get("voice_turn", False))
            conv_history = (
                _build_conversation_history(user_id, thread_id, window_limit=6, recent_char_cap=900, older_char_cap=400)
                if is_voice_turn
                else _build_conversation_history(user_id, thread_id)
            )

            brain = _create_user_brain(user)
            byok = str(self.headers.get("X-Gemini-Key") or body.get("user_gemini_key") or "").strip()
            if byok:
                brain.user_api_key = byok[:120]
            dispatch_prompt, permission_mode, engine_plan, active_tier, resolved_lang = _prepare_aura_turn(
                user, prompt, body, permission_mode, brain, membership=membership
            )
            reply = brain.think_and_act(
                dispatch_prompt,
                attachments=attachments,
                permission_mode=permission_mode,
                approved=approved,
                conversation_history=conv_history,
            )
            if engine_plan is not None and active_tier and not bool(body.get("voice_turn", False)):
                reply = AURA_MODEL_ROUTER.postprocess_reply(active_tier, prompt, reply, engine_plan)
            tools_used = getattr(brain, "last_tools", [])
            aura_db.save_message(user_id, thread_id, "assistant", reply, tools_used)

            self._send_json({
                "reply": reply,
                "speech_text": prepare_text_for_speech(reply, resolved_lang),
                "resolved_language": resolved_lang,
                "tools": tools_used,
                "aura_model": active_tier,
                "membership": membership,
                "quota": quota_status,
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
            prompt = str(body.get("prompt", "")).strip()[:32000]
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

            membership = self._resolve_membership(user, body)
            quota_ok, quota_status = aura_membership.check_and_consume_chat_quota(user, prompt, membership)
            if not quota_ok:
                self._send_json({
                    "success": False,
                    "error": "daily_limit_reached",
                    "message": (
                        f"Daily chat limit reached ({quota_status['used']}/{quota_status['limit']} chats on {membership['name']}). "
                        f"Quota refreshes automatically in {quota_status['reset_label']}."
                    ),
                    "quota": quota_status,
                    "membership": membership,
                }, status=429)
                return

            display_prompt = prompt
            if attachments:
                att_names = [str(a.get("name", "attachment"))[:80] for a in attachments if isinstance(a, dict)]
                display_prompt += f"\n[📎 {len(att_names)} Attachment(s): {', '.join(att_names)}]"

            aura_db.save_message(user_id, thread_id, "user", display_prompt)
            is_voice_turn = bool(body.get("voice_turn", False))
            conv_history = (
                _build_conversation_history(user_id, thread_id, window_limit=6, recent_char_cap=900, older_char_cap=400)
                if is_voice_turn
                else _build_conversation_history(user_id, thread_id)
            )

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store")
            self.send_header("Connection", "close")
            self._apply_security_and_cors_headers()
            self.end_headers()

            brain = _create_user_brain(user)
            byok = str(self.headers.get("X-Gemini-Key") or body.get("user_gemini_key") or "").strip()
            if byok:
                brain.user_api_key = byok[:120]
            dispatch_prompt, permission_mode, engine_plan, active_tier, resolved_lang = _prepare_aura_turn(
                user, prompt, body, permission_mode, brain, membership=membership
            )
            accumulated_text = ""
            tools_used = []

            try:
                if engine_plan is not None and engine_plan.thought_steps and not bool(body.get("voice_turn", False)):
                    trace_prefix = format_thought_block(
                        engine_plan.trace_title,
                        engine_plan.thought_steps,
                        engine_plan.elapsed_ms,
                    )
                    accumulated_text += trace_prefix
                    trace_payload = json.dumps({"type": "token", "delta": trace_prefix})
                    self.wfile.write(f"data: {trace_payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                final_reply_text = ""
                for chunk in brain.think_and_act_stream(
                    dispatch_prompt,
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
                        tool_entry = {"name": chunk.get("name"), "output": chunk.get("output")}
                        tools_used.append(tool_entry)
                        payload = json.dumps({"type": "tool", "name": chunk.get("name"), "output": chunk.get("output")})
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    elif chunk_type == "done":
                        final_reply_text = accumulated_text or chunk.get("reply", "")
                        aura_db.save_message(user_id, thread_id, "assistant", final_reply_text, tools_used)
                        fresh_vault = aura_db.export_user_vault(user_id)
                        fresh_threads = aura_db.get_user_threads(user_id)
                        payload = json.dumps({
                            "type": "done",
                            "reply": final_reply_text,
                            "tools": tools_used,
                            "thread_id": thread_id,
                            "threads": fresh_threads,
                            "membership": membership,
                            "quota": quota_status,
                            "user_vault": fresh_vault,
                        })
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                        self.wfile.flush()

                if not final_reply_text and accumulated_text:
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
            saved = dict(user.get("settings") or {})
            provider = requested.get("active_provider")
            model = requested.get("active_model")
            raw_aura_model = body.get("aura_model") or requested.get("aura_model") or (body.get("preferences") or {}).get("aura_model")
            norm_aura_model = AURA_MODEL_ROUTER.normalize_tier(raw_aura_model) if raw_aura_model else None

            if provider is not None or model is not None:
                if not AuraSettingsManager.validate_model_selection(provider, model):
                    self._send_json({"success": False, "error": "Unsupported provider or model"}, status=400)
                    return
                saved["brain_settings"] = {
                    "active_provider": provider,
                    "active_model": model.strip(),
                }
            elif norm_aura_model is None:
                self._send_json({"success": False, "error": "Unsupported provider or model"}, status=400)
                return
            elif "brain_settings" not in saved:
                saved["brain_settings"] = _selected_brain_settings(user)

            prefs = dict(saved.get("preferences") or {})
            if norm_aura_model is not None:
                prefs["aura_model"] = AURA_MODEL_ROUTER.set_user_tier(user["id"], norm_aura_model)
            if isinstance(body.get("preferences"), dict):
                if "temperature" in body["preferences"]:
                    prefs["temperature"] = _clamp_float(body["preferences"]["temperature"], 0.3, 0.0, 1.0)
                if "theme" in body["preferences"]:
                    prefs["theme"] = str(body["preferences"]["theme"])[:40]
                if "execution_mode" in body["preferences"]:
                    exec_mode = str(body["preferences"]["execution_mode"]).strip().lower()
                    if exec_mode in ("ask_first", "auto_pilot"):
                        prefs["execution_mode"] = exec_mode
                        from aura_permission_system import SecurityMode, permission_manager
                        sec_target = SecurityMode.PARANOID.value if exec_mode == "ask_first" else SecurityMode.PROMPT_HIGH_RISK.value
                        permission_manager.set_security_mode(sec_target, user_id=user["id"], is_admin=(user.get("role") in ("admin", "superuser")))
            if prefs:
                saved["preferences"] = prefs
            if not aura_db.save_user_settings(user["id"], saved):
                self._send_json({"success": False, "error": "Could not save model settings"}, status=500)
                return
            user["settings"] = saved
            self._send_json({
                "success": True,
                "brain_settings": _selected_brain_settings(user),
                "preferences": saved.get("preferences", {}),
                "active_aura_model": prefs.get("aura_model", AURA_MODEL_ROUTER.get_user_tier(user["id"])),
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

        elif path == "/api/workspace/edit":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            file_rel = str(body.get("path", ""))
            target_txt = body.get("target", "")
            replacement_txt = body.get("replacement", "")
            replace_all = bool(body.get("replace_all", False))
            ws = _resolve_workspace_dir(user["id"])
            target_p = _safe_resolve_under(ws, file_rel)
            if target_p is None:
                self._send_json({"success": False, "error": "Edit path outside workspace is forbidden"}, status=403)
                return
            from aura_workspace_ide import edit_workspace_file
            res = edit_workspace_file(target_p, ws, target=str(target_txt), replacement=str(replacement_txt), replace_all=replace_all)
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/workspace/grep":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            query_txt = str(body.get("query", ""))
            subdir = str(body.get("path", ".") or ".").strip() or "."
            case_sensitive = bool(body.get("case_sensitive", False))
            regex_mode = bool(body.get("regex", False))
            ws = _resolve_workspace_dir(user["id"])
            search_root = _safe_resolve_under(ws, subdir, allow_root=True)
            if search_root is None:
                self._send_json({"success": False, "error": "Search path outside workspace is forbidden"}, status=403)
                return
            from aura_workspace_ide import grep_workspace
            res = grep_workspace(search_root, ws, query=query_txt, case_sensitive=case_sensitive, regex=regex_mode)
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/workspace/delete":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            file_rel = str(body.get("path", ""))
            ws = _resolve_workspace_dir(user["id"])
            target_p = _safe_resolve_under(ws, file_rel)
            if target_p is None:
                self._send_json({"success": False, "error": "Delete path outside workspace is forbidden"}, status=403)
                return
            from aura_workspace_ide import delete_workspace_file
            res = delete_workspace_file(target_p, ws)
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/workspace/devserver/start":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mode = str(body.get("mode", "static")).strip().lower()
            ws = _resolve_workspace_dir(user["id"])
            from aura_workspace_ide import WORKSPACE_DEV_MANAGER
            if mode == "command":
                if not self._is_authorized_admin(body):
                    self._send_json({"success": False, "error": "Unauthorized: Admin authentication required for shell dev server"}, status=401)
                    return
                from aura_brain import is_safe_command
                cmd = str(body.get("command", ""))
                res = WORKSPACE_DEV_MANAGER.start_command_server(cmd, ws, safety_checker=is_safe_command, user_id=user["id"])
                self._send_json(res, status=200 if res.get("success") else 400)
                return
            subdir = str(body.get("directory", ".") or ".").strip() or "."
            serve_dir = _safe_resolve_under(ws, subdir, allow_root=True)
            if serve_dir is None:
                self._send_json({"success": False, "error": "Directory outside workspace is forbidden"}, status=403)
                return
            entry = str(body.get("entry", "index.html") or "index.html").strip()
            port = _clamp_int(body.get("port"), 0, 0, 65535)
            res = WORKSPACE_DEV_MANAGER.start_static_preview(serve_dir, entry=entry, port=port, user_id=user["id"])
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/workspace/devserver/stop":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            sid = str(body.get("server_id", "")).strip()
            from aura_workspace_ide import WORKSPACE_DEV_MANAGER
            res = WORKSPACE_DEV_MANAGER.stop_server(sid, user_id=user["id"])
            self._send_json(res, status=200 if res.get("success") else 404)

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
            from aura_workspace_ide import extract_localhost_urls
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
                stdout_txt = proc.stdout[:32768]
                stderr_txt = proc.stderr[:32768]
                self._send_json({
                    "success": proc.returncode == 0,
                    "command": cmd,
                    "cwd": str(ws),
                    "exit_code": proc.returncode,
                    "stdout": stdout_txt,
                    "stderr": stderr_txt,
                    "detected_urls": extract_localhost_urls(stdout_txt + "\n" + stderr_txt),
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

        # 10. SOVEREIGN 10-NEXUS SUPER-SUITE ROUTES
        elif path in ("/api/bharatcode10/execute", "/api/sovereign10/execute"):
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_bharatcode_top10 import BHARATCODE_TOP10_SUITE
            engine_key = body.get("engine_id") or body.get("engine") or "trinetra"
            payload = body.get("payload") or body.get("goal") or body.get("prompt") or ""
            res = BHARATCODE_TOP10_SUITE.execute_engine(engine_key, payload=payload)
            self._send_json(res)

        elif path in ("/api/bharatcode10/superpipeline", "/api/sovereign10/superpipeline"):
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_bharatcode_top10 import BHARATCODE_TOP10_SUITE
            goal = str(body.get("goal") or body.get("payload") or "Run all 10 Sovereign Nexus engines end-to-end")[:2000]
            res = BHARATCODE_TOP10_SUITE.run_all_10_superpipeline(mission_goal=goal)
            self._send_json(res)

        # 11. AURA ANTIGRAVITY OMNI-CORE ROUTES (SLASH COMMANDS, SWARM, DESKTOP BRIDGE)
        elif path == "/api/antigravity/slash":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_antigravity_core import AURA_ANTIGRAVITY_CORE
            command = str(body.get("command") or "/goal")[:64]
            prompt = str(body.get("prompt") or body.get("goal") or "")[:2000]
            self._send_json(AURA_ANTIGRAVITY_CORE.execute_slash_command(command, prompt))

        elif path == "/api/antigravity/swarm":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_antigravity_core import AURA_ANTIGRAVITY_CORE
            title = str(body.get("title") or "AURA Antigravity Swarm")[:120]
            mission = str(body.get("mission") or body.get("goal") or "")[:2000]
            self._send_json(AURA_ANTIGRAVITY_CORE.run_swarm(title=title, mission=mission))

        elif path == "/api/antigravity/desktop":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            from aura_antigravity_core import AURA_ANTIGRAVITY_CORE
            action = str(body.get("action") or "set_brightness")[:64]
            target = str(body.get("target") or "display")[:120]
            value = body.get("value", 50)
            self._send_json(AURA_ANTIGRAVITY_CORE.execute_desktop_action(action=action, target=target, value=value))

        # 12. JARVIS AUTOMATIONS & HARDWARE KILL-SWITCH ROUTES
        elif path == "/api/jarvis/run":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            routine = str(body.get("routine") or "repo_health_audit")[:64]
            target = str(body.get("target") or "")[:500]
            res = JARVIS_HUB.run_routine(user["id"], routine, target=target)
            if isinstance(res, dict):
                res["jarvis_status"] = JARVIS_HUB.get_status(user["id"])
            status = 423 if res.get("halted") else (200 if res.get("success", True) else 400)
            self._send_json(res, status=status)

        elif path == "/api/jarvis/kill_switch":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            halted = bool(body.get("halted", True))
            reason = str(body.get("reason") or "Operator toggle")[:200]
            res = JARVIS_HUB.set_kill_switch(user["id"], halted=halted, reason=reason)
            self._send_json(res)

        # 13. 3-PLAN SUBSCRIPTIONS, EXCLUSIVE ADMIN KEY VAULT (ig.ahmed.irl) & PRO/APEX STUDIO ROUTES
        elif path == "/api/admin/keys/unlock":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            pw = str(body.get("password") or body.get("admin_password") or "")
            res = aura_membership.unlock_admin_key_vault(user, pw)
            self._send_json(res, status=int(res.get("status", 200 if res.get("success") else 403)))

        elif path in ("/api/admin/keys/generate", "/api/admin/keys/renew", "/api/admin/keys/toggle", "/api/admin/keys/unbind"):
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            vault_tok = str(self.headers.get("X-Admin-Vault-Token") or body.get("admin_vault_token") or "").strip()
            if not aura_membership.verify_admin_vault_token(user, vault_tok):
                self._send_json({"success": False, "error": "Forbidden: Admin Key Vault access requires @ig.ahmed.irl vault authentication."}, status=403)
                return
            if path == "/api/admin/keys/generate":
                raw_days = body.get("duration_days")
                days_val = int(raw_days) if raw_days is not None and str(raw_days).strip() else None
                res = aura_membership.admin_generate_keys(
                    tier_id=str(body.get("tier_id") or "tier_3"),
                    duration_days=days_val,
                    count=int(body.get("count") or 1),
                    note=str(body.get("note") or ""),
                    created_by=str(user.get("username") or "ig.ahmed.irl"),
                )
            elif path == "/api/admin/keys/renew":
                raw_days = body.get("duration_days")
                days_val = int(raw_days) if raw_days is not None and str(raw_days).strip() else None
                res = aura_membership.admin_renew_key(
                    key_code=str(body.get("key_code") or body.get("key") or ""),
                    duration_days=days_val,
                    tier_id=str(body.get("tier_id") or "") or None,
                    note=body.get("note"),
                )
            elif path == "/api/admin/keys/toggle":
                res = aura_membership.admin_toggle_key_status(
                    key_code=str(body.get("key_code") or body.get("key") or ""),
                    disable=bool(body.get("disable", True)),
                )
            else:
                res = aura_membership.admin_unbind_key(
                    key_code=str(body.get("key_code") or body.get("key") or ""),
                )
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/membership/activate":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            raw_key = str(body.get("key") or body.get("activation_key") or "").strip()
            res = aura_membership.activate_membership_key(user, raw_key)
            if res.get("success"):
                res["user_vault"] = aura_db.export_user_vault(user["id"])
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/membership/deactivate":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            res = aura_membership.deactivate_membership(user)
            res["user_vault"] = aura_db.export_user_vault(user["id"])
            self._send_json(res)

        elif path == "/api/membership/rules":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user, body)
            res = aura_membership.save_user_aura_rules(user, str(body.get("rules") or ""), membership=mem)
            if res.get("success"):
                res["user_vault"] = aura_db.export_user_vault(user["id"])
            self._send_json(res, status=200 if res.get("success") else 403)

        elif path == "/api/pro/context_files":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user, body)
            if int(mem.get("rank", 0)) < 3:
                self._send_json({"success": False, "error": "@file context injection requires AURA Sovereign (Plan 1) or higher.", "required_rank": 3}, status=403)
                return
            paths = body.get("paths") if isinstance(body.get("paths"), list) else []
            self._send_json(aura_pro_studio.read_context_files(_resolve_workspace_dir(user["id"]), [str(p) for p in paths[:6]]))

        elif path in ("/api/pro/diff_plan", "/api/pro/apply_diff"):
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user, body)
            if int(mem.get("rank", 0)) < 3:
                self._send_json({"success": False, "error": "Multi-File Unified Diff Composer requires AURA Sovereign (Plan 1) or higher.", "required_rank": 3}, status=403)
                return
            edits = body.get("edits") if isinstance(body.get("edits"), list) else []
            do_apply = (path == "/api/pro/apply_diff") or bool(body.get("apply", False))
            label = str(body.get("label") or "Multi-File Diff Apply")[:80]
            res = aura_pro_studio.plan_and_apply_multifile_diff(_resolve_workspace_dir(user["id"]), edits, apply=do_apply, label=label)
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/pro/rollback":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user, body)
            if int(mem.get("rank", 0)) < 3:
                self._send_json({"success": False, "error": "Snapshot rollback requires AURA Sovereign (Plan 1) or higher.", "required_rank": 3}, status=403)
                return
            snap_id = str(body.get("snapshot_id") or "").strip()
            res = aura_pro_studio.rollback_workspace_snapshot(_resolve_workspace_dir(user["id"]), snap_id)
            self._send_json(res, status=200 if res.get("success") else 404)

        elif path == "/api/pro/run_code":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user, body)
            if int(mem.get("rank", 0)) < 3:
                self._send_json({"success": False, "error": "Polyglot Code Sandbox requires AURA Sovereign (Plan 1) or higher.", "required_rank": 3}, status=403)
                return
            lang = str(body.get("language") or "python")[:32]
            code = str(body.get("code") or "")
            stdin_txt = str(body.get("stdin") or "")[:4000]
            res = aura_pro_studio.execute_polyglot_sandbox(_resolve_workspace_dir(user["id"]), lang, code, stdin_text=stdin_txt)
            self._send_json(res, status=200 if res.get("error") is None else 400)

        elif path == "/api/pro/self_heal":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user, body)
            if int(mem.get("rank", 0)) < 3:
                self._send_json({"success": False, "error": "Autonomous Self-Healing Repair requires AURA Sovereign (Tier 3) or higher.", "required_rank": 3}, status=403)
                return
            target_file = str(body.get("path") or body.get("file") or "").strip()
            auto_apply = bool(body.get("auto_apply", False))
            brain = _create_user_brain(user)
            byok = str(self.headers.get("X-Gemini-Key") or "").strip()
            if byok:
                brain.user_api_key = byok[:120]
            res = aura_pro_studio.run_self_heal_loop(_resolve_workspace_dir(user["id"]), target_file, brain, auto_apply=auto_apply)
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/pro/scaffold":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user, body)
            if int(mem.get("rank", 0)) < 3:
                self._send_json({"success": False, "error": "Production Repo Scaffolder requires AURA Sovereign (Tier 3) or higher.", "required_rank": 3}, status=403)
                return
            tmpl = str(body.get("template") or "modern_webapp").strip()
            pname = str(body.get("project_name") or "aura_starter").strip()
            res = aura_pro_studio.scaffold_project_template(_resolve_workspace_dir(user["id"]), tmpl, pname)
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/pro/security_audit":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user, body)
            if int(mem.get("rank", 0)) < 4:
                self._send_json({"success": False, "error": "Workspace Security AST Audit requires AURA Titan (Tier 4) or higher.", "required_rank": 4}, status=403)
                return
            self._send_json(aura_pro_studio.audit_workspace_security(_resolve_workspace_dir(user["id"])))

        elif path == "/api/pro/war_room":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user, body)
            if int(mem.get("rank", 0)) < 4:
                self._send_json({"success": False, "error": "Parallel 4-Agent War Room requires AURA Titan (Tier 4) or higher.", "required_rank": 4}, status=403)
                return
            objective = str(body.get("objective") or body.get("prompt") or "").strip()
            byok = str(self.headers.get("X-Gemini-Key") or "").strip()
            def _make_b():
                b = _create_user_brain(user)
                if byok:
                    b.user_api_key = byok[:120]
                return b
            res = aura_pro_studio.run_parallel_war_room(objective, _resolve_workspace_dir(user["id"]), _make_b, rules_text=mem.get("aura_rules", ""))
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/pro/os_action/propose":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user, body)
            if int(mem.get("rank", 0)) < 4:
                self._send_json({"success": False, "error": "Guarded Desktop/Laptop OS Automation requires AURA Titan (Tier 4) or higher.", "required_rank": 4}, status=403)
                return
            res = aura_pro_studio.propose_guarded_os_action(
                user,
                action_type=str(body.get("action_type") or ""),
                target=str(body.get("target") or ""),
                reason=str(body.get("reason") or ""),
                params=body.get("params") if isinstance(body.get("params"), dict) else {},
            )
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/pro/os_action/commit":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user, body)
            if int(mem.get("rank", 0)) < 4:
                self._send_json({"success": False, "error": "Guarded Desktop/Laptop OS Automation requires AURA Titan (Tier 4) or higher.", "required_rank": 4}, status=403)
                return
            res = aura_pro_studio.commit_guarded_os_action(
                user,
                signed_ticket=str(body.get("signed_ticket") or ""),
                decision=str(body.get("decision") or "DENY"),
                workspace_dir=_resolve_workspace_dir(user["id"]),
                deny_note=str(body.get("deny_note") or ""),
            )
            self._send_json(res, status=200 if res.get("success") else 400)

        elif path == "/api/pro/apex_execute":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return
            mem = self._resolve_membership(user, body)
            if int(mem.get("rank", 0)) < 5:
                self._send_json({"success": False, "error": "AURA Apex Omnis 6-Stage Autonomous Pipeline requires Tier 5 activation.", "required_rank": 5}, status=403)
                return
            goal = str(body.get("goal") or body.get("prompt") or "").strip()
            language = str(body.get("language") or "python").strip()[:32]
            auto_apply = bool(body.get("auto_apply", False))
            brain = _create_user_brain(user)
            byok = str(self.headers.get("X-Gemini-Key") or "").strip()
            if byok:
                brain.user_api_key = byok[:120]
            res = aura_pro_studio.run_apex_autonomous_pipeline(
                goal,
                language,
                _resolve_workspace_dir(user["id"]),
                brain,
                rules_text=mem.get("aura_rules", ""),
                auto_apply=auto_apply,
            )
            self._send_json(res, status=200 if res.get("success") else 400)

        elif self._handle_agent_workspace_post(path, body):
            return

        elif self._handle_voice_post(path, body):
            return

        else:
            self._send_json({"success": False, "error": "Not Found"}, status=404)

    def _handle_agent_workspace_post(self, path: str, body: Dict[str, Any]) -> bool:
        """Handles POST routes for AURA Live Browser, Computer Use, and Live Action View."""
        if path == "/api/browser/tab/new":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            url = str(body.get("url") or "").strip()[:2048]
            res = LIVE_BROWSER.new_tab(user["id"], url=url)
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/browser/tab/switch":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            tab_id = str(body.get("tab_id") or "").strip()[:32]
            res = LIVE_BROWSER.switch_tab(user["id"], tab_id)
            self._send_json(res, status=200 if res.get("success") else 404)
            return True

        if path == "/api/browser/tab/close":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            tab_id = str(body.get("tab_id") or "").strip()[:32]
            res = LIVE_BROWSER.close_tab(user["id"], tab_id)
            self._send_json(res, status=200 if res.get("success") else 404)
            return True

        if path == "/api/browser/navigate":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            raw_url = str(body.get("url") or "").strip()[:2048]
            tab_id = str(body.get("tab_id") or "").strip()[:32] or None
            res = LIVE_BROWSER.navigate(user["id"], raw_url, tab_id=tab_id)
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/browser/action":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            action = str(body.get("action") or "").strip()[:32]
            tab_id = str(body.get("tab_id") or "").strip()[:32] or None
            x_val = body.get("x")
            y_val = body.get("y")
            el_idx = body.get("element_index")
            res = LIVE_BROWSER.perform_action(
                user["id"],
                action,
                tab_id=tab_id,
                x=float(x_val) if isinstance(x_val, (int, float)) else None,
                y=float(y_val) if isinstance(y_val, (int, float)) else None,
                selector=str(body.get("selector") or "")[:240],
                text=str(body.get("text") or "")[:1000],
                key=str(body.get("key") or "")[:40],
                delta_y=_clamp_int(body.get("delta_y", 420), 420, -3000, 3000),
                delta_x=_clamp_int(body.get("delta_x", 0), 0, -2000, 2000),
                submit=bool(body.get("submit", False)),
                clear=bool(body.get("clear", False)),
                element_index=int(el_idx) if isinstance(el_idx, int) else None,
            )
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/browser/agent":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            goal = str(body.get("goal") or body.get("prompt") or "").strip()[:1200]
            tab_id = str(body.get("tab_id") or "").strip()[:32] or None
            brain = _create_user_brain(user)
            byok = str(self.headers.get("X-Gemini-Key") or "").strip()
            if byok:
                brain.user_api_key = byok[:120]
            res = LIVE_BROWSER.run_agent_goal(user["id"], goal, brain=brain, tab_id=tab_id)
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/browser/understand":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            question = str(body.get("question") or body.get("prompt") or "Summarize this page and its interactive actions.").strip()[:1200]
            tab_id = str(body.get("tab_id") or "").strip()[:32] or None
            brain = _create_user_brain(user)
            byok = str(self.headers.get("X-Gemini-Key") or "").strip()
            if byok:
                brain.user_api_key = byok[:120]
            res = LIVE_BROWSER.understand_page(user["id"], question=question, brain=brain, tab_id=tab_id)
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/computer/control":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            cmd = str(body.get("command") or "").strip()[:32]
            goal = str(body.get("goal") or "").strip()[:500]
            brain = _create_user_brain(user)
            byok = str(self.headers.get("X-Gemini-Key") or "").strip()
            if byok:
                brain.user_api_key = byok[:120]
            res = COMPUTER_USE.control(user["id"], cmd, goal=goal, brain=brain)
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/computer/action":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            action = str(body.get("action") or "").strip()[:32]
            x_val = body.get("x")
            y_val = body.get("y")
            raw_keys = body.get("keys")
            keys_list = [str(k)[:24] for k in raw_keys[:5]] if isinstance(raw_keys, list) else None
            res = COMPUTER_USE.execute_action(
                user["id"],
                action,
                x=float(x_val) if isinstance(x_val, (int, float)) else None,
                y=float(y_val) if isinstance(y_val, (int, float)) else None,
                text=str(body.get("text") or "")[:400],
                keys=keys_list,
                delta_y=_clamp_int(body.get("delta_y", -300), -300, -2400, 2400),
                app_name=str(body.get("app_name") or "")[:64],
                window_title=str(body.get("window_title") or "")[:120],
            )
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/computer/analyze_frame":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            goal = str(body.get("goal") or body.get("prompt") or "Analyze the live desktop screen and suggest the next step.").strip()[:800]
            frame_b64 = str(body.get("frame_b64") or "")[:3_500_000]
            brain = _create_user_brain(user)
            byok = str(self.headers.get("X-Gemini-Key") or "").strip()
            if byok:
                brain.user_api_key = byok[:120]
            res = COMPUTER_USE.analyze_frame_with_vision(user["id"], goal=goal, frame_b64=frame_b64, brain=brain)
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/actions/clear":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            self._send_json(LIVE_ACTION_HUB.clear(user["id"]))
            return True

        # --- PILLARS 1-5: MULTI-AGENT ORCHESTRATOR, PLANNER, AGENT MANAGER & SELF-VERIFY ---
        if path == "/api/orchestrator/plan":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            goal = str(body.get("goal") or body.get("prompt") or "").strip()[:1200]
            enabled = body.get("enabled_specialists") if isinstance(body.get("enabled_specialists"), list) else None
            req_ap = body.get("require_approval_agents") if isinstance(body.get("require_approval_agents"), list) else None
            auto_ap = bool(body.get("auto_approve", False))
            brain = _create_user_brain(user)
            byok = str(self.headers.get("X-Gemini-Key") or "").strip()
            if byok:
                brain.user_api_key = byok[:120]
            res = AGENT_ORCHESTRATOR.create_plan(
                user["id"],
                goal,
                enabled_specialists=[str(x)[:32] for x in enabled] if enabled else None,
                require_approval_agents=[str(x)[:32] for x in req_ap] if req_ap else None,
                auto_approve=auto_ap,
                ws_dir=_resolve_workspace_dir(user["id"]),
                brain=brain,
            )
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/orchestrator/mission/approve":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            mid = str(body.get("mission_id") or "").strip()[:64]
            enabled = body.get("enabled_specialists") if isinstance(body.get("enabled_specialists"), list) else None
            req_ap = body.get("require_approval_agents") if isinstance(body.get("require_approval_agents"), list) else None
            wait_sync = bool(body.get("wait_sync", False))
            brain = _create_user_brain(user)
            byok = str(self.headers.get("X-Gemini-Key") or "").strip()
            if byok:
                brain.user_api_key = byok[:120]
            res = AGENT_ORCHESTRATOR.approve_and_launch_mission(
                user["id"],
                mid,
                _resolve_workspace_dir(user["id"]),
                enabled_specialists=[str(x)[:32] for x in enabled] if enabled else None,
                require_approval_agents=[str(x)[:32] for x in req_ap] if req_ap else None,
                brain=brain,
                wait_sync=wait_sync,
            )
            self._send_json(res, status=200 if res.get("success") else 404)
            return True

        if path == "/api/orchestrator/agent/control":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            mid = str(body.get("mission_id") or "").strip()[:64]
            aid = str(body.get("agent_id") or "").strip()[:32]
            cmd = str(body.get("command") or "").strip()[:32]
            brain = _create_user_brain(user)
            res = AGENT_ORCHESTRATOR.control_agent(
                user["id"], mid, aid, cmd, _resolve_workspace_dir(user["id"]), brain=brain
            )
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/orchestrator/verify":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            target_path = str(body.get("target_path") or body.get("path") or ".").strip()[:260]
            test_cmd = str(body.get("test_command") or "").strip()[:260]
            max_att = _clamp_int(body.get("max_attempts", 3), 3, 1, 4)
            brain = _create_user_brain(user)
            byok = str(self.headers.get("X-Gemini-Key") or "").strip()
            if byok:
                brain.user_api_key = byok[:120]
            res = AGENT_ORCHESTRATOR.run_self_verification_loop(
                user["id"],
                _resolve_workspace_dir(user["id"]),
                target_path,
                test_command=test_cmd,
                max_attempts=max_att,
                brain=brain,
            )
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        # --- PILLAR 9: INTEGRATED WORKSPACE TERMINAL & ERROR DIAGNOSIS ---
        if path == "/api/workspace/terminal/exec":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            cmd_txt = str(body.get("command") or "").strip()
            res = WORKSPACE_TERMINAL.execute(user["id"], _resolve_workspace_dir(user["id"]), cmd_txt)
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/workspace/terminal/diagnose":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            brain = _create_user_brain(user)
            byok = str(self.headers.get("X-Gemini-Key") or "").strip()
            if byok:
                brain.user_api_key = byok[:120]
            ec = body.get("exit_code")
            res = WORKSPACE_TERMINAL.diagnose_error(
                user["id"],
                command=str(body.get("command") or "")[:300],
                stdout=str(body.get("stdout") or "")[:5000],
                stderr=str(body.get("stderr") or "")[:5000],
                exit_code=int(ec) if isinstance(ec, int) else None,
                brain=brain,
            )
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        # --- PILLAR 10: INTEGRATED FILE EXPLORER (MKDIR / CREATE / RENAME / DELETE) ---
        if path == "/api/workspace/fs/mkdir":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            rel_p = str(body.get("path") or "").strip()
            res = create_workspace_folder(user["id"], _resolve_workspace_dir(user["id"]), rel_p)
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/workspace/fs/create":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            rel_p = str(body.get("path") or "").strip()
            content = str(body.get("content") or "")
            res = create_or_save_workspace_file(user["id"], _resolve_workspace_dir(user["id"]), rel_p, content)
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/workspace/fs/rename":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            old_p = str(body.get("old_path") or "").strip()
            new_p = str(body.get("new_path") or "").strip()
            res = rename_workspace_entry(user["id"], _resolve_workspace_dir(user["id"]), old_p, new_p)
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/workspace/fs/delete":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            rel_p = str(body.get("path") or "").strip()
            res = delete_workspace_entry(user["id"], _resolve_workspace_dir(user["id"]), rel_p)
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        # --- PART 1: PROFESSIONAL CODING, GIT STUDIO, SNAPSHOTS & VISUAL DELIVERABLES (#13-#28, #40-#45) ---
        if path in (
            "/api/dev/autocomplete", "/api/dev/inline_edit", "/api/dev/explain",
            "/api/dev/bugs", "/api/dev/refactor", "/api/dev/multifile_edit",
            "/api/dev/smart_search", "/api/dev/generate_tests",
        ):
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            ws = _resolve_workspace_dir(user["id"])
            brain = _create_user_brain(user)
            byok = str(self.headers.get("X-Gemini-Key") or "").strip()
            if byok:
                brain.user_api_key = byok[:120]

            if path == "/api/dev/autocomplete":
                res = aura_dev_studio.ai_autocomplete(user["id"], ws, path=str(body.get("path") or ""), prefix=str(body.get("prefix") or ""), suffix=str(body.get("suffix") or ""), brain=brain)
            elif path == "/api/dev/inline_edit":
                res = aura_dev_studio.inline_ai_edit(user["id"], ws, path=str(body.get("path") or ""), selected_code=str(body.get("selected_code") or ""), instruction=str(body.get("instruction") or ""), apply=bool(body.get("apply", False)), brain=brain)
            elif path == "/api/dev/explain":
                res = aura_dev_studio.explain_code(user["id"], ws, path=str(body.get("path") or ""), code=str(body.get("code") or ""), brain=brain)
            elif path == "/api/dev/bugs":
                res = aura_dev_studio.detect_bugs(user["id"], ws, path=str(body.get("path") or ""))
            elif path == "/api/dev/refactor":
                res = aura_dev_studio.refactor_file(user["id"], ws, path=str(body.get("path") or ""), goal=str(body.get("goal") or ""), apply=bool(body.get("apply", False)), brain=brain)
            elif path == "/api/dev/multifile_edit":
                edits = body.get("edits") if isinstance(body.get("edits"), list) else []
                res = aura_dev_studio.apply_multifile_edits(user["id"], ws, edits=edits, label=str(body.get("label") or "Multi-File Edit"), dry_run=bool(body.get("dry_run", False)))
            elif path == "/api/dev/smart_search":
                res = aura_dev_studio.smart_search_workspace(user["id"], ws, str(body.get("query") or ""))
            else:
                res = aura_dev_studio.generate_unit_tests(user["id"], ws, path=str(body.get("path") or ""), save=bool(body.get("save", True)), brain=brain)
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path in ("/api/git/review", "/api/git/worktree", "/api/git/branch", "/api/git/commit", "/api/git/pr"):
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            ws = _resolve_workspace_dir(user["id"])
            if path == "/api/git/review":
                res = aura_dev_studio.git_review_file_decision(user["id"], ws, str(body.get("path") or ""), str(body.get("decision") or "approve"))
            elif path == "/api/git/worktree":
                res = aura_dev_studio.git_manage_worktree(user["id"], ws, str(body.get("action") or "create"), str(body.get("name") or ""))
            elif path == "/api/git/branch":
                res = aura_dev_studio.git_manage_branch(user["id"], ws, str(body.get("action") or "switch"), str(body.get("branch") or ""))
            elif path == "/api/git/commit":
                res = aura_dev_studio.git_commit_and_push(
                    user["id"], ws,
                    message=str(body.get("message") or ""),
                    stage_all=bool(body.get("stage_all", True)),
                    push=bool(body.get("push", False)),
                    push_approved=bool(body.get("push_approved", False)),
                )
                if res.get("success"):
                    ev_res = PLATFORM_EXT.fire_event(user["id"], ws, "on_commit")
                    res["event_triggers_fired"] = ev_res.get("triggered_count", 0)
            else:
                brain = _create_user_brain(user)
                res = aura_dev_studio.git_pull_request_assistant(user["id"], ws, title=str(body.get("title") or ""), review_feedback=str(body.get("review_feedback") or ""), brain=brain)
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path in ("/api/snapshots/create", "/api/snapshots/rollback"):
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            ws = _resolve_workspace_dir(user["id"])
            if path == "/api/snapshots/create":
                res = aura_dev_studio.create_project_snapshot(user["id"], ws, label=str(body.get("label") or "Manual Checkpoint"))
            else:
                res = aura_dev_studio.rollback_project_snapshot(user["id"], ws, str(body.get("snapshot_id") or ""))
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path in ("/api/deliverables/artifact", "/api/deliverables/report", "/api/browser/record", "/api/browser/feedback"):
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            ws = _resolve_workspace_dir(user["id"])
            if path == "/api/deliverables/artifact":
                res = aura_dev_studio.VISUAL_DELIVERABLES.save_artifact(user["id"], title=str(body.get("title") or "Artifact"), kind=str(body.get("kind") or "doc"), content=str(body.get("content") or ""), source_path=str(body.get("source_path") or ""))
            elif path == "/api/deliverables/report":
                res = aura_dev_studio.VISUAL_DELIVERABLES.build_final_execution_report(user["id"], ws, title=str(body.get("title") or "AURA Final Execution Report"))
            elif path == "/api/browser/record":
                res = aura_dev_studio.VISUAL_DELIVERABLES.control_browser_recording(user["id"], str(body.get("command") or "start"), label=str(body.get("label") or ""))
            else:
                res = aura_dev_studio.VISUAL_DELIVERABLES.add_visual_feedback(user["id"], url=str(body.get("url") or ""), note=str(body.get("note") or ""), screenshot_b64=str(body.get("screenshot_b64") or ""))
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        # --- PART 2: EXTENSIBILITY (SKILLS, MCP, PLUGINS, AGENTS, RULES, PERMS) & AUTOMATIONS (#29-#39) ---
        if path.startswith("/api/platform/"):
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            ws = _resolve_workspace_dir(user["id"])
            sub = path[len("/api/platform/"):]
            if sub == "skills/save":
                res = PLATFORM_EXT.save_skill(user["id"], ws, body)
            elif sub == "skills/delete":
                res = PLATFORM_EXT.delete_skill(user["id"], ws, str(body.get("id") or ""))
            elif sub == "mcp/save":
                res = PLATFORM_EXT.save_mcp_server(user["id"], ws, body)
            elif sub == "mcp/invoke":
                res = PLATFORM_EXT.invoke_mcp_tool(user["id"], ws, str(body.get("server_id") or ""), str(body.get("tool") or ""), body.get("params") if isinstance(body.get("params"), dict) else None)
            elif sub == "plugins/manage":
                res = PLATFORM_EXT.manage_plugin(user["id"], ws, str(body.get("plugin_id") or ""), str(body.get("action") or "enable"), body.get("config") if isinstance(body.get("config"), dict) else None)
            elif sub == "agents/save":
                res = PLATFORM_EXT.save_custom_agent(user["id"], ws, body)
            elif sub == "agents/delete":
                res = PLATFORM_EXT.delete_custom_agent(user["id"], ws, str(body.get("id") or ""))
            elif sub == "rules":
                res = PLATFORM_EXT.update_rules_and_memory(user["id"], ws, body)
            elif sub == "permissions":
                res = PLATFORM_EXT.update_tool_permissions(user["id"], ws, body.get("permissions") if isinstance(body.get("permissions"), dict) else body)
            elif sub == "workflows/save":
                res = PLATFORM_EXT.save_workflow(user["id"], ws, body)
            elif sub == "workflows/run":
                brain = _create_user_brain(user)
                res = PLATFORM_EXT.run_workflow(user["id"], ws, str(body.get("workflow_id") or ""), trigger_source=str(body.get("trigger_source") or "manual"), brain=brain)
            elif sub == "schedules/save":
                res = PLATFORM_EXT.save_schedule(user["id"], ws, body)
            elif sub == "triggers/save":
                res = PLATFORM_EXT.save_event_trigger(user["id"], ws, body)
            elif sub == "triggers/fire":
                res = PLATFORM_EXT.fire_event(user["id"], ws, str(body.get("event") or "on_commit"))
            elif sub == "background/start":
                res = PLATFORM_EXT.start_background_agent(user["id"], ws, name=str(body.get("name") or "Background Agent"), workflow_id=str(body.get("workflow_id") or "wf_code_quality_pipeline"))
            elif sub == "notifications/read":
                res = PLATFORM_EXT.mark_notifications_read(user["id"], ws, clear_all=bool(body.get("clear_all", False)))
            else:
                return False
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        # --- PART 3: ADVANCED INTELLIGENCE, REMOTE CONTROL & SECURITY GOVERNANCE (#12, #46-#64) ---
        if path.startswith("/api/control/"):
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            ws = _resolve_workspace_dir(user["id"])
            sub = path[len("/api/control/"):]
            if sub == "emergency_stop":
                res = CONTROL_HUB.trigger_emergency_stop(user["id"], ws, reason=str(body.get("reason") or "Operator Emergency Stop"))
            elif sub == "secrets/scan":
                res = CONTROL_HUB.scan_workspace_secrets(user["id"], ws)
            elif sub == "secrets/redact":
                res = {"success": True, "redacted": redact_secrets(str(body.get("text") or ""))}
            elif sub == "approvals/request":
                res = CONTROL_HUB.request_approval(user["id"], ws, action_type=str(body.get("action_type") or "sensitive_action"), target=str(body.get("target") or ""), reason=str(body.get("reason") or ""), agent_name=str(body.get("agent_name") or "AURA Agent"))
            elif sub == "approvals/decide":
                res = CONTROL_HUB.decide_approval(user["id"], ws, str(body.get("approval_id") or ""), str(body.get("decision") or "reject"))
            elif sub == "recovery/save":
                res = CONTROL_HUB.save_recovery_checkpoint(user["id"], ws, label=str(body.get("label") or "Manual Checkpoint"))
            elif sub == "recovery/restore":
                res = CONTROL_HUB.restore_recovery_checkpoint(user["id"], ws)
            elif sub == "boundaries/update":
                tools_l = body.get("allowed_tools") if isinstance(body.get("allowed_tools"), list) else []
                res = CONTROL_HUB.update_agent_boundary(user["id"], str(body.get("agent_id") or ""), str(body.get("allowed_dir") or "."), tools_l)
            elif sub == "remote/pair":
                res = CONTROL_HUB.create_remote_pairing(user["id"], label=str(body.get("label") or "Authorized Remote Device"), ttl_minutes=_clamp_int(body.get("ttl_minutes", 30), 30, 5, 120))
            elif sub == "remote/revoke":
                res = CONTROL_HUB.revoke_remote_tokens(user["id"])
            elif sub == "routing":
                res = CONTROL_HUB.update_model_routing(user["id"], body)
            elif sub == "handoff":
                files_l = body.get("files") if isinstance(body.get("files"), list) else []
                res = CONTROL_HUB.record_task_handoff(user["id"], str(body.get("from_agent") or "coordinator"), str(body.get("to_agent") or "backend"), str(body.get("summary") or ""), files_l)
            elif sub == "projects":
                res = CONTROL_HUB.manage_projects(user["id"], ws, action=str(body.get("action") or "list"), name=str(body.get("name") or ""))
            elif sub == "cost/log":
                ent = CONTROL_HUB.record_token_usage(user["id"], str(body.get("task") or "task"), str(body.get("model") or "gemini-3-flash-preview"), _clamp_int(body.get("input_tokens", 0), 0, 0, 2_000_000), _clamp_int(body.get("output_tokens", 0), 0, 0, 2_000_000))
                res = {"success": True, "entry": ent}
            else:
                return False
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        if path == "/api/remote/action":
            rem_tok = str(self.headers.get("X-Remote-Token") or body.get("remote_token") or "").strip()
            uid = CONTROL_HUB.resolve_remote_token(rem_tok)
            if not uid:
                self._send_json({"success": False, "error": "Valid X-Remote-Token required"}, status=401)
                return True
            ws = _resolve_workspace_dir(int(uid)) if uid.isdigit() else _resolve_workspace_dir(None)
            act = str(body.get("action") or "").strip().lower()
            if act == "emergency_stop":
                res = CONTROL_HUB.trigger_emergency_stop(uid, ws, reason="Remote Device Emergency Stop")
            elif act in ("approve", "reject"):
                res = CONTROL_HUB.decide_approval(uid, ws, str(body.get("approval_id") or ""), act, actor="remote_device")
            else:
                res = {"success": False, "error": "Remote action must be 'approve', 'reject', or 'emergency_stop'."}
            self._send_json(res, status=200 if res.get("success") else 400)
            return True

        return False

    def _handle_voice_post(self, path: str, body: Dict[str, Any]) -> bool:
        vp = self._voice_subpath(path)
        if vp in ("/v1/speech", "/api/voice/speak"):
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            text = str(body.get("text") or "").strip()
            if not text:
                self._send_json({"success": False, "error": "Text is required for speech synthesis"}, status=400)
                return True
            language = str(body.get("language") or "auto")[:24]
            voice_id = str(body.get("voice_id") or "male_02")[:48]
            engine = str(body.get("engine") or "auto")[:24]
            speed = _clamp_float(body.get("speed", 1.0), 1.0, 0.65, 1.5)
            commercial_only = bool(body.get("commercial_only", False))
            try:
                art = VOICE_ORCHESTRATOR.synthesize_speech(
                    user_id=user["id"],
                    text=text,
                    language=language,
                    voice_id=voice_id,
                    engine=engine,
                    speed=speed,
                    commercial_only=commercial_only,
                )
                payload_out: Dict[str, Any] = {"success": True, "speech": art.to_public_dict()}
                if art.raw_bytes and art.engine != "fallback_pcm" and len(art.raw_bytes) <= 450_000:
                    import base64
                    payload_out["audio_base64"] = base64.b64encode(art.raw_bytes).decode("ascii")
                    payload_out["content_type"] = art.content_type
                self._send_json(payload_out)
            except PermissionError as exc:
                self._send_json({"success": False, "error": str(exc)}, status=403)
            except Exception as exc:
                self._send_json({"success": False, "error": f"Speech generation error: {exc}"}, status=500)
            return True

        if vp == "/v1/calls":
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            sess = VOICE_ORCHESTRATOR.create_call_session(
                user_id=user["id"],
                voice_id=str(body.get("voice_id") or "male_02")[:48],
                language=str(body.get("language") or "en")[:24],
                engine=str(body.get("engine") or "auto")[:24],
                consent_confirmed=bool(body.get("consent_confirmed", True)),
            )
            self._send_json({"success": True, "call": sess})
            return True

        if vp.startswith("/v1/calls/") and vp.endswith("/state"):
            user = self._get_auth_user(body)
            if not user:
                self._send_json({"success": False, "error": "Authentication required"}, status=401)
                return True
            cid = vp[len("/v1/calls/"):-len("/state")].strip("/")
            updates = {}
            for field in ("status", "voice_id", "language", "engine", "interrupted", "turns"):
                if field in body:
                    updates[field] = body[field]
            sess = VOICE_ORCHESTRATOR.update_call_session(cid, user["id"], **updates)
            if not sess:
                self._send_json({"success": False, "error": "Call session not found"}, status=404)
                return True
            self._send_json({"success": True, "call": sess})
            return True

        return False


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
