"""
===================================================================================
AURA WORKSPACE IDE ENGINE
===================================================================================
Shared, tenant-isolated file inspection, surgical editing, workspace grep search,
localhost dev/preview server management, and terminal URL detection utilities used
by both `aura_brain.py` and `aura_web.py`.
===================================================================================
"""

from __future__ import annotations

import atexit
import difflib
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from coderx_engine import _atomic_write_text

SKIP_SEARCH_DIRS = frozenset({
    ".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv", "dist", "build"
})

SAFE_PREVIEW_MIME_TYPES: Dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}

LOCALHOST_URL_RE = re.compile(r"https?://(?:127\.0\.0\.1|localhost|0\.0\.0\.0):\d{2,5}(?:/[^\s\"'<>)]*)?", re.I)


def extract_localhost_urls(text: str) -> List[str]:
    """Extracts unique localhost/loopback URLs emitted by terminal commands or servers."""
    if not text:
        return []
    seen: List[str] = []
    for raw in LOCALHOST_URL_RE.findall(str(text)):
        normalized = re.sub(r"://0\.0\.0\.0:", "://127.0.0.1:", raw.rstrip(".,;:"))
        if normalized not in seen:
            seen.append(normalized)
    return seen


def read_workspace_lines(
    resolved_path: Path,
    workspace_root: Path,
    start_line: int = 1,
    end_line: Optional[int] = None,
    max_lines: int = 250,
    max_bytes: int = 32768,
) -> Dict[str, Any]:
    """Reads an inclusive 1-based line slice cleanly from a workspace file with line numbers."""
    if not resolved_path.exists() or not resolved_path.is_file():
        return {"success": False, "error": f"File not found: {resolved_path.name}"}

    raw_text = resolved_path.read_text(encoding="utf-8", errors="replace")
    all_lines = raw_text.splitlines()
    total_lines = len(all_lines)
    rel = resolved_path.resolve().relative_to(workspace_root.resolve()).as_posix()

    if total_lines == 0:
        return {
            "success": True,
            "file": str(resolved_path),
            "rel_path": rel,
            "start_line": 1,
            "end_line": 0,
            "total_lines": 0,
            "truncated": False,
            "content": "",
            "numbered_content": "",
        }

    s_line = max(1, int(start_line or 1))
    if s_line > total_lines:
        return {
            "success": False,
            "error": f"start_line {s_line} exceeds file length ({total_lines} lines).",
            "total_lines": total_lines,
        }

    default_end = min(total_lines, s_line + max_lines - 1)
    e_line = min(total_lines, max(s_line, int(end_line) if end_line else default_end))
    if (e_line - s_line + 1) > max_lines:
        e_line = s_line + max_lines - 1

    slice_lines = all_lines[s_line - 1 : e_line]
    plain_lines: List[str] = []
    numbered_lines: List[str] = []
    used_bytes = 0
    truncated = e_line < total_lines

    for offset, line in enumerate(slice_lines):
        line_bytes = len(line.encode("utf-8", errors="ignore")) + 1
        if plain_lines and (used_bytes + line_bytes) > max_bytes:
            e_line = s_line + offset - 1
            truncated = True
            break
        plain_lines.append(line)
        numbered_lines.append(f"{s_line + offset}: {line}")
        used_bytes += line_bytes

    return {
        "success": True,
        "file": str(resolved_path),
        "rel_path": rel,
        "start_line": s_line,
        "end_line": e_line,
        "total_lines": total_lines,
        "truncated": truncated,
        "content": "\n".join(plain_lines),
        "numbered_content": "\n".join(numbered_lines),
    }


def edit_workspace_file(
    resolved_path: Path,
    workspace_root: Path,
    target: str,
    replacement: str,
    replace_all: bool = False,
) -> Dict[str, Any]:
    """
    Performs surgical search-and-replace on a workspace file atomically and returns a
    unified diff preview. Fails closed when `target` is absent or ambiguous.
    """
    if not resolved_path.exists() or not resolved_path.is_file():
        return {"success": False, "error": f"File not found: {resolved_path.name}"}
    if not isinstance(target, str) or target == "":
        return {"success": False, "error": "Non-empty exact target string is required."}

    original = resolved_path.read_text(encoding="utf-8", errors="replace")
    match_count = original.count(target)
    if match_count == 0:
        return {"success": False, "error": "Target block not found in file; no changes written."}
    if match_count > 1 and not replace_all:
        return {
            "success": False,
            "error": (
                f"Target block matched {match_count} times. Provide a more specific target block "
                "or set replace_all=true."
            ),
            "matches": match_count,
        }

    repl = replacement if isinstance(replacement, str) else ""
    first_idx = original.find(target)
    line_start = original[:first_idx].count("\n") + 1
    updated = original.replace(target, repl) if replace_all else original.replace(target, repl, 1)

    rel = resolved_path.resolve().relative_to(workspace_root.resolve()).as_posix()
    _atomic_write_text(resolved_path, updated, encoding="utf-8")

    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
            lineterm="",
            n=2,
        )
    )
    return {
        "success": True,
        "file": str(resolved_path),
        "rel_path": rel,
        "occurrences_replaced": match_count if replace_all else 1,
        "line_start": line_start,
        "bytes_written": len(updated.encode("utf-8")),
        "diff": "\n".join(diff_lines[:120]),
    }


def delete_workspace_file(resolved_path: Path, workspace_root: Path) -> Dict[str, Any]:
    """Deletes a file strictly inside `workspace_root` (never directories or root)."""
    ws_resolved = workspace_root.resolve()
    target_resolved = resolved_path.resolve()
    if target_resolved == ws_resolved:
        return {"success": False, "error": "Cannot delete workspace root directory."}
    if not target_resolved.exists():
        return {"success": False, "error": "File not found."}
    if not target_resolved.is_file():
        return {"success": False, "error": "Only files can be deleted through workspace editor."}
    rel = target_resolved.relative_to(ws_resolved).as_posix()
    target_resolved.unlink()
    return {"success": True, "deleted_path": rel}


def grep_workspace(
    search_root: Path,
    workspace_root: Path,
    query: str,
    case_sensitive: bool = False,
    regex: bool = False,
    max_hits: int = 80,
) -> Dict[str, Any]:
    """Searches non-binary files under `search_root` inside `workspace_root`."""
    if not isinstance(query, str) or not query.strip():
        return {"success": False, "error": "Search query is required."}
    if not search_root.exists():
        return {"success": False, "error": "Search path does not exist."}

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query if regex else re.escape(query), flags)
    except re.error as exc:
        return {"success": False, "error": f"Invalid regular expression: {exc}"}

    ws_resolved = workspace_root.resolve()
    matches: List[Dict[str, Any]] = []
    files_scanned = 0

    candidates = [search_root] if search_root.is_file() else sorted(search_root.rglob("*"))
    for fpath in candidates:
        if any(part in SKIP_SEARCH_DIRS or part.startswith(".") for part in fpath.parts):
            continue
        if not fpath.is_file():
            continue
        try:
            if fpath.stat().st_size > 1_000_000:
                continue
            raw_bytes = fpath.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw_bytes[:1024]:
            continue

        files_scanned += 1
        rel = fpath.resolve().relative_to(ws_resolved).as_posix()
        text = raw_bytes.decode("utf-8", errors="ignore")
        for line_no, line_txt in enumerate(text.splitlines(), 1):
            if pattern.search(line_txt):
                matches.append({
                    "file": rel,
                    "line": line_no,
                    "text": line_txt.strip()[:220],
                })
                if len(matches) >= max_hits:
                    return {
                        "success": True,
                        "query": query,
                        "files_scanned": files_scanned,
                        "truncated": True,
                        "count": len(matches),
                        "matches": matches,
                    }

    return {
        "success": True,
        "query": query,
        "files_scanned": files_scanned,
        "truncated": False,
        "count": len(matches),
        "matches": matches,
    }


def _make_confined_handler(root_dir: Path):
    """Builds a quiet SimpleHTTPRequestHandler confined strictly to `root_dir`."""
    resolved_root = root_dir.resolve()

    class _StaticPreviewHandler(SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def translate_path(self, path: str) -> str:
            parsed = urllib.parse.urlparse(path).path
            parts = [p for p in urllib.parse.unquote(parsed).split("/") if p and p not in (".", "..")]
            candidate = resolved_root
            for part in parts:
                candidate = candidate / part
            try:
                resolved = candidate.resolve()
                resolved.relative_to(resolved_root)
                return str(resolved)
            except (OSError, ValueError):
                return str(resolved_root / "__blocked_outside_workspace__")

    return partial(_StaticPreviewHandler, directory=str(resolved_root))


class WorkspaceDevServerManager:
    """Tracks per-user localhost static preview servers and background dev processes."""

    def __init__(self, max_per_user: int = 4) -> None:
        self._lock = threading.Lock()
        self._servers: Dict[str, Dict[str, Any]] = {}
        self._counter = 0
        self._max_per_user = max_per_user
        atexit.register(self.stop_all)

    @staticmethod
    def _owner_key(user_id: Optional[int]) -> str:
        return f"user_{int(user_id)}" if user_id is not None else "global"

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}_{int(time.time())}"

    def _evict_dead_and_excess(self, owner: str) -> None:
        for sid, rec in list(self._servers.items()):
            proc = rec.get("proc")
            if proc is not None and proc.poll() is not None:
                rec["running"] = False
            if rec.get("owner") == owner and not rec.get("running", False):
                self._servers.pop(sid, None)

        owner_records = [
            (sid, rec) for sid, rec in self._servers.items() if rec.get("owner") == owner
        ]
        while len(owner_records) >= self._max_per_user:
            oldest_sid, _ = owner_records.pop(0)
            self._stop_unlocked(oldest_sid)

    def _stop_unlocked(self, server_id: str) -> bool:
        rec = self._servers.pop(server_id, None)
        if not rec:
            return False
        httpd = rec.get("httpd")
        if httpd is not None:
            try:
                httpd.shutdown()
                httpd.server_close()
            except Exception:
                pass
        proc = rec.get("proc")
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        rec["running"] = False
        return True

    def start_static_preview(
        self,
        serve_dir: Path,
        entry: str = "index.html",
        port: int = 0,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if os.environ.get("VERCEL"):
            safe_entry = entry.lstrip("/") or "index.html"
            return {
                "success": True,
                "mode": "cloud_preview",
                "serverless": True,
                "url": f"/api/workspace/preview/{safe_entry}",
                "message": "Serverless environment detected: use built-in Workspace Cloud Preview URL.",
            }

        if not serve_dir.exists() or not serve_dir.is_dir():
            return {"success": False, "error": "Preview directory does not exist in workspace."}

        req_port = int(port or 0)
        if req_port != 0 and not (1024 <= req_port <= 65535):
            return {"success": False, "error": "Port must be 0 (auto) or between 1024 and 65535."}

        handler_factory = _make_confined_handler(serve_dir)
        try:
            class _ReusableLoopbackHTTPServer(ThreadingHTTPServer):
                allow_reuse_address = True
                daemon_threads = True

            httpd = _ReusableLoopbackHTTPServer(("127.0.0.1", req_port), handler_factory)
        except OSError as exc:
            return {"success": False, "error": f"Could not bind localhost port {req_port}: {exc}"}

        actual_port = int(httpd.server_address[1])
        clean_entry = str(entry or "index.html").strip().lstrip("/")
        entry_suffix = clean_entry if clean_entry and (serve_dir / clean_entry).exists() else ""
        url = f"http://127.0.0.1:{actual_port}/{entry_suffix}"

        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        owner = self._owner_key(user_id)
        with self._lock:
            self._evict_dead_and_excess(owner)
            sid = self._next_id("static")
            self._servers[sid] = {
                "id": sid,
                "owner": owner,
                "mode": "static",
                "port": actual_port,
                "url": url,
                "cwd": str(serve_dir),
                "httpd": httpd,
                "running": True,
                "started_at": time.time(),
                "logs": [f"Static preview server listening on {url}"],
            }
        return {
            "success": True,
            "server_id": sid,
            "mode": "static",
            "port": actual_port,
            "url": url,
            "cloud_preview_url": f"/api/workspace/preview/{clean_entry}" if clean_entry else "/api/workspace/preview/index.html",
        }

    def start_command_server(
        self,
        command: str,
        cwd: Path,
        safety_checker: Callable[[str], tuple],
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Launches a long-running local dev command (admin-only route enforces auth)."""
        if os.environ.get("VERCEL"):
            return {
                "success": False,
                "serverless": True,
                "error": "Background OS dev servers cannot stay alive on Vercel serverless. Run AURA locally for OS process servers, or use /api/workspace/preview for static apps.",
            }

        cmd = str(command or "").strip()
        if not cmd:
            return {"success": False, "error": "Dev server command is required."}
        is_safe, reason = safety_checker(cmd)
        if not is_safe:
            return {"success": False, "error": f"Security Sandbox: {reason}"}

        if sys.platform == "win32":
            shell_args = ["powershell", "-NoProfile", "-Command", cmd]
        else:
            pwsh_bin = shutil.which("pwsh") or shutil.which("powershell")
            shell_args = [pwsh_bin, "-NoProfile", "-Command", cmd] if pwsh_bin else ["/bin/sh", "-c", cmd]

        try:
            proc = subprocess.Popen(
                shell_args,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as exc:
            return {"success": False, "error": f"Failed to start process: {exc}"}

        logs: List[str] = []
        detected_urls: List[str] = []
        log_lock = threading.Lock()

        def _pump_logs():
            try:
                if proc.stdout is None:
                    return
                for line in proc.stdout:
                    clean = line.rstrip("\r\n")
                    with log_lock:
                        logs.append(clean[:400])
                        if len(logs) > 80:
                            del logs[: len(logs) - 80]
                        for u in extract_localhost_urls(clean):
                            if u not in detected_urls:
                                detected_urls.append(u)
            except Exception:
                pass

        threading.Thread(target=_pump_logs, daemon=True).start()
        time.sleep(0.45)

        owner = self._owner_key(user_id)
        with self._lock:
            self._evict_dead_and_excess(owner)
            sid = self._next_id("proc")
            running = proc.poll() is None
            with log_lock:
                urls_copy = list(detected_urls)
                logs_copy = list(logs)
            self._servers[sid] = {
                "id": sid,
                "owner": owner,
                "mode": "command",
                "command": cmd,
                "pid": proc.pid,
                "proc": proc,
                "cwd": str(cwd),
                "running": running,
                "logs": logs,
                "log_lock": log_lock,
                "detected_urls": detected_urls,
                "url": urls_copy[0] if urls_copy else "",
                "started_at": time.time(),
            }

        return {
            "success": True,
            "server_id": sid,
            "mode": "command",
            "pid": proc.pid,
            "running": running,
            "detected_urls": urls_copy,
            "url": urls_copy[0] if urls_copy else "",
            "logs": logs_copy,
        }

    def list_servers(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        owner = self._owner_key(user_id)
        out: List[Dict[str, Any]] = []
        with self._lock:
            for sid, rec in list(self._servers.items()):
                if rec.get("owner") != owner:
                    continue
                proc = rec.get("proc")
                if proc is not None and proc.poll() is not None:
                    rec["running"] = False
                log_lock = rec.get("log_lock")
                if log_lock:
                    with log_lock:
                        logs = list(rec.get("logs", []))[-25:]
                        urls = list(rec.get("detected_urls", []))
                else:
                    logs = list(rec.get("logs", []))[-25:]
                    urls = [rec["url"]] if rec.get("url") else []
                out.append({
                    "server_id": sid,
                    "mode": rec.get("mode"),
                    "port": rec.get("port"),
                    "pid": rec.get("pid"),
                    "command": rec.get("command", ""),
                    "url": urls[0] if urls else rec.get("url", ""),
                    "detected_urls": urls,
                    "running": bool(rec.get("running", False)),
                    "logs": logs,
                })
        return out

    def stop_server(self, server_id: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        owner = self._owner_key(user_id)
        with self._lock:
            rec = self._servers.get(server_id)
            if not rec or rec.get("owner") != owner:
                return {"success": False, "error": "Server session not found for current user."}
            stopped = self._stop_unlocked(server_id)
            return {"success": stopped, "server_id": server_id}

    def stop_all(self) -> None:
        with self._lock:
            for sid in list(self._servers.keys()):
                self._stop_unlocked(sid)


WORKSPACE_DEV_MANAGER = WorkspaceDevServerManager()
