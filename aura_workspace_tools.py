"""
===================================================================================
      AURA INTEGRATED TERMINAL & FILE EXPLORER ENGINE (PILLARS 9 & 10)
===================================================================================
Strictly tenant-isolated under each authenticated user's `workspace/user_<id>`:
- Pillar 9 (Integrated Terminal):
  Safe workspace developer shell runner (`ls/dir`, `pwd`, `cat`, `mkdir`, `touch`,
  `mv`, `rm`, `grep`, `tree`, `echo`, `python`, `pytest`, `node`, `git status/diff/log`)
  with strict path containment, timeout guards, per-user history, and AI error diagnosis.
- Pillar 10 (Integrated File Explorer):
  Hierarchical folder & file tree, search & content grep, create file/folder,
  rename/move files & folders, edit/save, and delete — all logged in real time
  to AURA Live Action Timeline (`LIVE_ACTION_HUB`).
===================================================================================
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aura_brain import AuraBrain
from aura_live_actions import LIVE_ACTION_HUB
from aura_os_controller import is_test_runner_active
from coderx_engine import _atomic_write_text

MAX_TERMINAL_HISTORY = 40
MAX_TREE_ITEMS = 400
MAX_EXEC_TIMEOUT_S = 15.0

# Shell operators / dangerous tokens blocked to prevent host escape
_SHELL_ESCAPE_RE = re.compile(r"([;&|`$><]|\$\(|\n|\r)")
_BLOCKED_TOKENS = {
    "sudo", "su", "rm -rf /", "format", "diskpart", "reg", "shutdown",
    "restart-computer", "powershell", "pwsh", "cmd", "bash", "sh", "curl", "wget",
    "invoke-webrequest", "iwr", "nc", "netcat", "ssh", "scp", "chmod", "chown",
}


def safe_resolve_workspace_path(base_dir: Path, rel_path: str, allow_root: bool = False) -> Optional[Path]:
    """Resolves `rel_path` strictly inside `base_dir`, immune to traversal or sibling prefixes."""
    if not isinstance(rel_path, str):
        return None
    cleaned = rel_path.strip().replace("\\", "/")
    if cleaned in ("", ".", "./"):
        return base_dir.resolve() if allow_root else None
    cleaned = cleaned.lstrip("/")
    if not cleaned:
        return base_dir.resolve() if allow_root else None
    try:
        base_resolved = base_dir.resolve()
        candidate = (base_resolved / cleaned).resolve()
        candidate.relative_to(base_resolved)
        if not allow_root and candidate == base_resolved:
            return None
        return candidate
    except (OSError, ValueError, TypeError):
        return None


# ===================================================================================
# PILLAR 10: INTEGRATED FILE EXPLORER (FOLDERS, FILES, SEARCH, CREATE, RENAME, EDIT)
# ===================================================================================
def list_workspace_fs_tree(user_id: Any, ws_dir: Path, search: str = "") -> Dict[str, Any]:
    """Returns full hierarchical folders + files inside `ws_dir` with optional filename search."""
    ws = ws_dir.resolve()
    ws.mkdir(parents=True, exist_ok=True)
    q = str(search or "").strip().lower()

    folders: List[Dict[str, Any]] = []
    files: List[Dict[str, Any]] = []
    hidden_names = {".aura_snapshots", "__pycache__", ".pytest_cache", ".git", "node_modules"}

    for root, dirnames, filenames in os.walk(ws):
        dirnames[:] = sorted(d for d in dirnames if d not in hidden_names and not d.startswith("."))
        root_p = Path(root)
        for d in dirnames:
            dp = root_p / d
            rel = dp.relative_to(ws).as_posix()
            if q and q not in rel.lower():
                continue
            folders.append({
                "name": d,
                "path": rel,
                "parent": dp.parent.relative_to(ws).as_posix() if dp.parent != ws else "",
                "type": "folder",
                "depth": len(Path(rel).parts) - 1,
            })
            if len(folders) + len(files) >= MAX_TREE_ITEMS:
                break
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            fp = root_p / fn
            rel = fp.relative_to(ws).as_posix()
            if q and q not in rel.lower():
                continue
            try:
                st = fp.stat()
                size_bytes = st.st_size
                mtime = st.st_mtime
            except OSError:
                size_bytes = 0
                mtime = 0.0
            files.append({
                "name": fn,
                "path": rel,
                "parent": fp.parent.relative_to(ws).as_posix() if fp.parent != ws else "",
                "type": "file",
                "ext": fp.suffix.lower(),
                "size_bytes": size_bytes,
                "size_kb": round(size_bytes / 1024.0, 2),
                "mtime": mtime,
                "depth": len(Path(rel).parts) - 1,
            })
            if len(folders) + len(files) >= MAX_TREE_ITEMS:
                break
        if len(folders) + len(files) >= MAX_TREE_ITEMS:
            break

    return {
        "success": True,
        "workspace_scope": f"user_{user_id}",
        "total_folders": len(folders),
        "total_files": len(files),
        "folders": folders,
        "files": files,
    }


def create_workspace_folder(user_id: Any, ws_dir: Path, rel_path: str) -> Dict[str, Any]:
    ws = ws_dir.resolve()
    target = safe_resolve_workspace_path(ws, rel_path, allow_root=False)
    if target is None:
        return {"success": False, "error": "Folder path outside workspace is forbidden."}
    try:
        target.mkdir(parents=True, exist_ok=True)
        norm_rel = target.relative_to(ws).as_posix()
        LIVE_ACTION_HUB.record(
            user_id,
            "files",
            "mkdir",
            f"Created folder: {norm_rel}",
            target=norm_rel,
            engine="workspace_explorer",
        )
        return {"success": True, "path": norm_rel, "type": "folder"}
    except Exception as exc:
        return {"success": False, "error": f"Failed to create folder: {exc}"}


def create_or_save_workspace_file(user_id: Any, ws_dir: Path, rel_path: str, content: str = "") -> Dict[str, Any]:
    ws = ws_dir.resolve()
    target = safe_resolve_workspace_path(ws, rel_path, allow_root=False)
    if target is None:
        return {"success": False, "error": "File path outside workspace is forbidden."}
    try:
        existed = target.exists()
        _atomic_write_text(target, str(content or ""), encoding="utf-8")
        norm_rel = target.relative_to(ws).as_posix()
        LIVE_ACTION_HUB.record(
            user_id,
            "files",
            "edit_file" if existed else "create_file",
            f"{'Updated' if existed else 'Created'} file: {norm_rel} ({len(content)} bytes)",
            target=norm_rel,
            engine="workspace_explorer",
        )
        return {"success": True, "path": norm_rel, "bytes": len(content), "created": not existed}
    except Exception as exc:
        return {"success": False, "error": f"Failed to save file: {exc}"}


def rename_workspace_entry(user_id: Any, ws_dir: Path, old_rel: str, new_rel: str) -> Dict[str, Any]:
    ws = ws_dir.resolve()
    src = safe_resolve_workspace_path(ws, old_rel, allow_root=False)
    dst = safe_resolve_workspace_path(ws, new_rel, allow_root=False)
    if src is None or dst is None:
        return {"success": False, "error": "Rename path outside workspace is forbidden."}
    if not src.exists():
        return {"success": False, "error": f"Source path not found: {old_rel}"}
    if dst.exists():
        return {"success": False, "error": f"Destination already exists: {new_rel}"}
    # Prevent moving a folder inside itself
    try:
        dst.relative_to(src)
        return {"success": False, "error": "Cannot move a folder inside itself."}
    except ValueError:
        pass
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        old_posix = src.relative_to(ws).as_posix()
        new_posix = dst.relative_to(ws).as_posix()
        LIVE_ACTION_HUB.record(
            user_id,
            "files",
            "rename",
            f"Renamed {old_posix} -> {new_posix}",
            target=new_posix,
            engine="workspace_explorer",
        )
        return {"success": True, "old_path": old_posix, "new_path": new_posix}
    except Exception as exc:
        return {"success": False, "error": f"Rename failed: {exc}"}


def delete_workspace_entry(user_id: Any, ws_dir: Path, rel_path: str) -> Dict[str, Any]:
    ws = ws_dir.resolve()
    target = safe_resolve_workspace_path(ws, rel_path, allow_root=False)
    if target is None:
        return {"success": False, "error": "Delete path outside workspace is forbidden."}
    if not target.exists():
        return {"success": False, "error": f"Path not found: {rel_path}"}
    norm_rel = target.relative_to(ws).as_posix()
    try:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        LIVE_ACTION_HUB.record(
            user_id,
            "files",
            "delete",
            f"Deleted {norm_rel}",
            target=norm_rel,
            engine="workspace_explorer",
        )
        return {"success": True, "deleted": norm_rel}
    except Exception as exc:
        return {"success": False, "error": f"Delete failed: {exc}"}


# ===================================================================================
# PILLAR 9: INTEGRATED WORKSPACE TERMINAL + AI ERROR DIAGNOSIS
# ===================================================================================
class WorkspaceTerminalManager:
    """Per-user isolated workspace terminal with strict safety allowlist & error diagnostics."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _uid(user_id: Any) -> str:
        return str(user_id if user_id is not None else "guest")

    def _get_session(self, user_id: Any) -> Dict[str, Any]:
        uid = self._uid(user_id)
        with self._lock:
            sess = self._sessions.get(uid)
            if not sess:
                sess = {"cwd": ".", "history": [], "seq": 0}
                self._sessions[uid] = sess
            return sess

    def get_history(self, user_id: Any) -> Dict[str, Any]:
        sess = self._get_session(user_id)
        with self._lock:
            return {
                "success": True,
                "cwd": sess["cwd"],
                "history": list(sess["history"][-MAX_TERMINAL_HISTORY:]),
            }

    def _resolve_cwd(self, ws: Path, rel_cwd: str) -> Path:
        p = safe_resolve_workspace_path(ws, rel_cwd or ".", allow_root=True)
        if p is None or not p.exists() or not p.is_dir():
            return ws.resolve()
        return p

    def _run_builtin(
        self,
        cmd_name: str,
        args: List[str],
        ws: Path,
        cwd: Path,
        sess: Dict[str, Any],
    ) -> Optional[Tuple[int, str, str]]:
        """Handles safe cross-platform built-in commands identically on Windows & Vercel Linux."""
        low = cmd_name.lower()

        if low == "help":
            return 0, (
                "AURA Integrated Workspace Terminal (Isolated Sandbox)\n"
                "Commands: ls, dir, pwd, cd <dir>, cat <file>, mkdir <dir>, touch <file>,\n"
                "          mv <old> <new>, rm <path>, tree, grep <term>, echo <text>,\n"
                "          python <args>, pytest <args>, node <args>, clear"
            ), ""

        if low == "pwd":
            rel = cwd.relative_to(ws).as_posix() if cwd != ws else "."
            return 0, f"/workspace/{rel}" if rel != "." else "/workspace", ""

        if low == "echo":
            return 0, " ".join(args), ""

        if low == "cd":
            target_arg = args[0] if args else "."
            if target_arg in ("/", "~", "."):
                sess["cwd"] = "."
                return 0, "/workspace", ""
            cand = safe_resolve_workspace_path(ws, (Path(sess["cwd"]) / target_arg).as_posix(), allow_root=True)
            if cand is None:
                return 1, "", "Permission denied: cannot navigate outside isolated workspace."
            if not cand.exists() or not cand.is_dir():
                return 1, "", f"Directory not found: {target_arg}"
            rel = cand.relative_to(ws).as_posix() if cand != ws else "."
            sess["cwd"] = rel
            return 0, f"/workspace/{rel}" if rel != "." else "/workspace", ""

        if low in ("ls", "dir"):
            sub = args[0] if args and not args[0].startswith("-") else "."
            target_dir = safe_resolve_workspace_path(ws, (Path(sess["cwd"]) / sub).as_posix(), allow_root=True)
            if target_dir is None or not target_dir.exists() or not target_dir.is_dir():
                return 1, "", f"Directory not found: {sub}"
            entries = sorted(target_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            lines = []
            for ent in entries:
                if ent.name.startswith(".") or ent.name == "__pycache__":
                    continue
                if ent.is_dir():
                    lines.append(f"[DIR]   {ent.name}/")
                else:
                    sz = ent.stat().st_size
                    lines.append(f"[FILE]  {ent.name:<32} {sz:>7} B")
            return 0, "\n".join(lines) if lines else "(empty workspace directory)", ""

        if low == "tree":
            lines = ["."]
            count = 0
            for root, dirnames, filenames in os.walk(cwd):
                dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d != "__pycache__")
                rp = Path(root)
                depth = len(rp.relative_to(cwd).parts) if rp != cwd else 0
                indent = "  " * depth
                if rp != cwd:
                    lines.append(f"{indent}{rp.name}/")
                for fn in sorted(filenames):
                    if fn.startswith("."):
                        continue
                    lines.append(f"{indent}  {fn}")
                    count += 1
                    if count >= 120:
                        lines.append("... (truncated)")
                        return 0, "\n".join(lines), ""
            return 0, "\n".join(lines), ""

        if low in ("cat", "type"):
            if not args:
                return 1, "", f"Usage: {low} <file>"
            target = safe_resolve_workspace_path(ws, (Path(sess["cwd"]) / args[0]).as_posix(), allow_root=False)
            if target is None:
                return 1, "", "Access denied: path outside workspace."
            if not target.exists() or not target.is_file():
                return 1, "", f"File not found: {args[0]}"
            return 0, target.read_text(encoding="utf-8", errors="replace")[:12000], ""

        if low == "mkdir":
            if not args:
                return 1, "", "Usage: mkdir <folder>"
            target = safe_resolve_workspace_path(ws, (Path(sess["cwd"]) / args[-1]).as_posix(), allow_root=False)
            if target is None:
                return 1, "", "Access denied: path outside workspace."
            target.mkdir(parents=True, exist_ok=True)
            return 0, f"Created folder: {target.relative_to(ws).as_posix()}", ""

        if low == "touch":
            if not args:
                return 1, "", "Usage: touch <file> [initial content]"
            target = safe_resolve_workspace_path(ws, (Path(sess["cwd"]) / args[0]).as_posix(), allow_root=False)
            if target is None:
                return 1, "", "Access denied: path outside workspace."
            content = " ".join(args[1:]) if len(args) > 1 else ""
            if not target.exists() or content:
                _atomic_write_text(target, content, encoding="utf-8")
            return 0, f"Saved file: {target.relative_to(ws).as_posix()}", ""

        if low in ("mv", "ren", "rename"):
            if len(args) < 2:
                return 1, "", "Usage: mv <old_path> <new_path>"
            src = safe_resolve_workspace_path(ws, (Path(sess["cwd"]) / args[0]).as_posix(), allow_root=False)
            dst = safe_resolve_workspace_path(ws, (Path(sess["cwd"]) / args[1]).as_posix(), allow_root=False)
            if src is None or dst is None:
                return 1, "", "Access denied: path outside workspace."
            if not src.exists():
                return 1, "", f"Source not found: {args[0]}"
            if dst.exists():
                return 1, "", f"Destination already exists: {args[1]}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            return 0, f"Moved {src.relative_to(ws).as_posix()} -> {dst.relative_to(ws).as_posix()}", ""

        if low in ("rm", "del"):
            clean_args = [a for a in args if not a.startswith("-")]
            if not clean_args:
                return 1, "", "Usage: rm <path>"
            target = safe_resolve_workspace_path(ws, (Path(sess["cwd"]) / clean_args[0]).as_posix(), allow_root=False)
            if target is None:
                return 1, "", "Access denied: path outside workspace."
            if not target.exists():
                return 1, "", f"Not found: {clean_args[0]}"
            rel = target.relative_to(ws).as_posix()
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            return 0, f"Removed: {rel}", ""

        if low == "grep":
            if not args:
                return 1, "", "Usage: grep <pattern>"
            needle = args[0].lower()
            matches: List[str] = []
            for fp in cwd.rglob("*"):
                if not fp.is_file() or fp.name.startswith(".") or "__pycache__" in fp.parts:
                    continue
                if fp.stat().st_size > 200_000:
                    continue
                try:
                    for ln_no, ln in enumerate(fp.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                        if needle in ln.lower():
                            matches.append(f"{fp.relative_to(ws).as_posix()}:{ln_no}: {ln.strip()[:120]}")
                            if len(matches) >= 60:
                                return 0, "\n".join(matches), ""
                except Exception:
                    continue
            return (0, "\n".join(matches), "") if matches else (1, "", f"No matches found for '{args[0]}'")

        return None

    def execute(self, user_id: Any, ws_dir: Path, raw_command: str) -> Dict[str, Any]:
        """Executes an allowlisted developer command strictly inside user's isolated workspace."""
        ws = ws_dir.resolve()
        ws.mkdir(parents=True, exist_ok=True)
        cmd_str = str(raw_command or "").strip()
        if not cmd_str:
            return {"success": False, "error": "Command cannot be empty."}
        if len(cmd_str) > 600:
            return {"success": False, "error": "Command exceeds 600-character safety limit."}

        # Strict shell-escape / host-command safety guard
        if _SHELL_ESCAPE_RE.search(cmd_str):
            LIVE_ACTION_HUB.record(
                user_id, "terminal", "exec", f"Blocked unsafe shell syntax: {cmd_str[:64]}", status="blocked"
            )
            return {
                "success": False,
                "error": "Shell chaining/redirection operators (;, &&, |, `, $, >, <) are blocked inside workspace sandbox.",
            }

        try:
            tokens = shlex.split(cmd_str, posix=(os.name != "nt"))
        except ValueError as exc:
            return {"success": False, "error": f"Invalid command quoting: {exc}"}
        if not tokens:
            return {"success": False, "error": "Empty command."}

        cmd_name = tokens[0].strip()
        args = [t.strip('"').strip("'") for t in tokens[1:]]
        low_cmd = cmd_name.lower()
        low_full = cmd_str.lower()

        if low_cmd in _BLOCKED_TOKENS or any(b in low_full for b in ("rm -rf /", "format ", "diskpart", "..\\..", "../..")):
            LIVE_ACTION_HUB.record(
                user_id, "terminal", "exec", f"Blocked restricted command: {cmd_str[:64]}", status="blocked"
            )
            return {"success": False, "error": f"Command '{cmd_name}' is restricted by AURA workspace sandbox policy."}

        # Reject absolute paths or parent traversal in args for subprocess safety
        for a in args:
            if ".." in a.replace("\\", "/").split("/") or re.match(r"^[a-zA-Z]:[/\\]", a) or a.startswith(("/", "\\\\")):
                return {"success": False, "error": f"Path argument '{a}' outside isolated workspace is blocked."}

        sess = self._get_session(user_id)
        cwd = self._resolve_cwd(ws, sess["cwd"])
        t0 = time.perf_counter()

        # 1. Cross-platform safe built-ins
        builtin_res = self._run_builtin(cmd_name, args, ws, cwd, sess)
        if builtin_res is not None:
            exit_code, stdout_txt, stderr_txt = builtin_res
            engine = "workspace_builtin"
        else:
            # 2. Strictly allowlisted dev executables (python, pytest, node, git read-only)
            exec_argv: Optional[List[str]] = None
            if low_cmd in ("python", "python3", "py"):
                # Disallow arbitrary `-c` OS escape imports? Allow `-m py_compile`, `-m unittest`, `-m pytest`, `--version`, or workspace `.py` scripts
                if "-c" in args:
                    code_idx = args.index("-c") + 1
                    snippet = args[code_idx] if code_idx < len(args) else ""
                    if re.search(r"\b(os\.system|subprocess|shutil\.rmtree|open\s*\(\s*['\"][A-Za-z]:|open\s*\(\s*['\"]/etc)", snippet):
                        return {"success": False, "error": "Inline python command contains restricted host APIs."}
                exec_argv = [sys.executable, *args]
            elif low_cmd == "pytest":
                exec_argv = [sys.executable, "-m", "pytest", *args]
            elif low_cmd == "node":
                node_bin = shutil.which("node")
                if not node_bin:
                    return {"success": False, "error": "Node.js runtime is not installed in this environment."}
                exec_argv = [node_bin, *args]
            elif low_cmd == "git":
                allowed_git = {"status", "log", "diff", "branch", "--version"}
                if not args or args[0].lower() not in allowed_git:
                    return {"success": False, "error": "Only read-only git commands (status, log, diff, branch) are allowed."}
                git_bin = shutil.which("git")
                if not git_bin:
                    return {"success": False, "error": "git is not installed in this environment."}
                exec_argv = [git_bin, *args]
            else:
                return {
                    "success": False,
                    "error": (
                        f"Unsupported command '{cmd_name}'. Allowed: ls, dir, pwd, cd, cat, mkdir, touch, mv, rm, "
                        "tree, grep, echo, python, pytest, node, git status/diff/log, help."
                    ),
                }

            try:
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
                proc = subprocess.run(
                    exec_argv,
                    cwd=str(cwd),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=MAX_EXEC_TIMEOUT_S,
                    creationflags=creationflags,
                )
                exit_code = int(proc.returncode)
                stdout_txt = (proc.stdout or "")[:14000]
                stderr_txt = (proc.stderr or "")[:8000]
                engine = f"sandbox_{low_cmd}"
            except subprocess.TimeoutExpired:
                exit_code = 124
                stdout_txt = ""
                stderr_txt = f"Command timed out after {int(MAX_EXEC_TIMEOUT_S)}s."
                engine = f"sandbox_{low_cmd}"
            except Exception as exc:
                exit_code = 1
                stdout_txt = ""
                stderr_txt = str(exc)
                engine = f"sandbox_{low_cmd}"

        dur = int((time.perf_counter() - t0) * 1000)
        entry = {
            "id": sess["seq"] + 1,
            "command": cmd_str,
            "cwd": sess["cwd"],
            "exit_code": exit_code,
            "stdout": stdout_txt,
            "stderr": stderr_txt,
            "duration_ms": dur,
            "engine": engine,
            "timestamp": time.time(),
            "time_label": time.strftime("%H:%M:%S"),
        }
        with self._lock:
            sess["seq"] = entry["id"]
            sess["history"].append(entry)
            if len(sess["history"]) > MAX_TERMINAL_HISTORY:
                del sess["history"][:-MAX_TERMINAL_HISTORY]

        LIVE_ACTION_HUB.record(
            user_id,
            "terminal",
            "exec",
            f"$ {cmd_str[:68]} (exit {exit_code})",
            target=sess["cwd"],
            status="completed" if exit_code == 0 else "error",
            duration_ms=dur,
            detail=(stderr_txt or stdout_txt)[:240],
            engine=engine,
        )
        return {"success": True, "entry": entry, "cwd": sess["cwd"]}

    def diagnose_error(
        self,
        user_id: Any,
        *,
        command: str = "",
        stdout: str = "",
        stderr: str = "",
        exit_code: Optional[int] = None,
        brain: Optional[AuraBrain] = None,
    ) -> Dict[str, Any]:
        """Analyzes terminal errors and returns root cause + exact actionable fix."""
        sess = self._get_session(user_id)
        if not command and not stderr and not stdout and sess["history"]:
            last = sess["history"][-1]
            command = last["command"]
            stdout = last["stdout"]
            stderr = last["stderr"]
            exit_code = last["exit_code"]

        combined = f"{stderr}\n{stdout}".strip()
        if not combined and not command:
            return {"success": False, "error": "Run a terminal command first so AURA can diagnose its output."}

        t0 = time.perf_counter()
        diagnosis = ""
        if brain is not None and not is_test_runner_active():
            prompt = (
                f"Diagnose this workspace terminal execution cleanly.\n"
                f"Command: {command}\nExit Code: {exit_code}\n"
                f"STDOUT:\n{stdout[:2000]}\nSTDERR:\n{stderr[:2000]}\n\n"
                "Return concise Markdown with:\n"
                "1. **Root Cause**\n2. **Exact Fix**\n3. **Verification Command**"
            )
            try:
                resp = brain._call_api([{"role": "user", "parts": [{"text": prompt}]}], tools=None, deadline_override=14.0)
                cands = resp.get("candidates") or []
                if cands:
                    parts = (cands[0].get("content") or {}).get("parts") or []
                    diagnosis = "\n".join(str(p.get("text") or "") for p in parts if isinstance(p, dict) and p.get("text")).strip()
                    if any(tok in diagnosis.lower() for tok in ("high student traffic", "temporarily throttled", "rate limit")):
                        diagnosis = ""
            except Exception:
                diagnosis = ""

        if not diagnosis:
            # Deterministic fast traceback diagnostic analyzer
            err_type = "Command Error"
            hint = "Check syntax, file paths, and missing dependencies inside your workspace."
            m_py = re.search(r"([A-Za-z]+Error|Exception):\s*(.+)", combined)
            m_line = re.search(r'File "([^"]+)", line (\d+)', combined)
            if m_py:
                err_type = m_py.group(1)
                err_msg = m_py.group(2).strip()[:180]
                loc = f" at `{m_line.group(1)}:{m_line.group(2)}`" if m_line else ""
                if err_type == "SyntaxError":
                    hint = "Fix missing colon, bracket, quote, or indentation on the reported line."
                elif err_type in ("ModuleNotFoundError", "ImportError"):
                    hint = "Ensure the imported module exists in your workspace or correct the relative import path."
                elif err_type == "AssertionError":
                    hint = "A unit test expectation failed — compare actual return value vs expected assertion."
                elif err_type == "NameError":
                    hint = "Define or import the referenced identifier before calling it."
                elif err_type == "ZeroDivisionError":
                    hint = "Guard division operations against zero denominators before dividing."
                diagnosis = (
                    f"**Root Cause:** `{err_type}`{loc} — {err_msg}\n\n"
                    f"**Recommended Fix:** {hint}\n\n"
                    f"**Verification Command:** Re-run `{command or 'python -m unittest'}` after patching."
                )
            elif exit_code == 0:
                diagnosis = f"**Status:** Command `{command}` succeeded cleanly with `exit 0`. No errors detected."
            else:
                diagnosis = (
                    f"**Root Cause:** Command `{command}` exited with code `{exit_code}`.\n\n"
                    f"**Output Excerpt:** `{combined[:280]}`\n\n"
                    f"**Recommended Fix:** {hint}"
                )

        dur = int((time.perf_counter() - t0) * 1000)
        LIVE_ACTION_HUB.record(
            user_id,
            "terminal",
            "diagnose",
            f"Diagnosed terminal output for `{command[:48]}`",
            target=command[:100],
            duration_ms=dur,
            detail=diagnosis[:240],
            engine="aura_diagnostics",
        )
        return {"success": True, "command": command, "exit_code": exit_code, "diagnosis": diagnosis}


WORKSPACE_TERMINAL = WorkspaceTerminalManager()
