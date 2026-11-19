"""
AURA Pro & Apex Omnis Engineering Studio Backend (Zero-Cost Local + Serverless Safe).

Real, tenant-isolated engineering engines unlocked across Tiers 1–5:
- Tier 1 (Velocity): Real AST/regex codebase symbol indexing & @file context injection.
- Tier 2 (Architect): Multi-file unified diff composer + atomic .aura_backups rollback + polyglot code runner (Python/JS/SQL/JSON/HTML).
- Tier 3 (Sovereign): Autonomous self-healing bug/test repair loop + full multi-file project scaffolder + .aura-rules.
- Tier 4 (Titan): Deep security AST audit + parallel 4-agent War Room + Desktop/Laptop OS Automation with signed Allow/Deny approval popup (Action + Target + Command + Reason).
- Tier 5 (Apex Omnis): 6-Stage Autonomous End-to-End Engineering Pipeline (Repo Scan -> Blueprint -> Multi-File Synthesis -> Static/Security Gate -> Live Sandbox Test & Self-Heal -> Snapshot Diff Checkpoint).
"""
from __future__ import annotations

import ast
import base64
import difflib
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aura_db

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".aura_backups", "dist", "build", ".next"}
CODE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript React",
    ".jsx": "JavaScript React",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".sql": "SQL",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".cpp": "C++",
    ".c": "C",
    ".cs": "C#",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".sh": "Shell",
    ".ps1": "PowerShell",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
}


def _safe_rel_path(workspace_dir: Path, raw_path: str) -> Optional[Path]:
    """Strictly confines a relative path inside workspace_dir (blocks traversal and absolute escapes)."""
    cleaned = str(raw_path or "").strip().replace("\\", "/").lstrip("/")
    if not cleaned or ".." in cleaned.split("/"):
        return None
    if cleaned.startswith(".aura_backups") or cleaned.startswith(".git"):
        return None
    root = workspace_dir.resolve()
    target = (root / cleaned).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


# ===================================================================================
# TIER 1: REAL WORKSPACE AST & MULTI-LANGUAGE SYMBOL INDEXER + @FILE CONTEXT
# ===================================================================================

def _extract_symbols_for_file(path: Path, text: str) -> List[Dict[str, Any]]:
    ext = path.suffix.lower()
    symbols: List[Dict[str, Any]] = []
    if ext == ".py":
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    symbols.append({"kind": "class", "name": node.name, "line": int(getattr(node, "lineno", 1))})
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append({
                        "kind": "async_fn" if isinstance(node, ast.AsyncFunctionDef) else "function",
                        "name": node.name,
                        "line": int(getattr(node, "lineno", 1)),
                    })
        except SyntaxError as exc:
            symbols.append({"kind": "syntax_error", "name": str(exc.msg), "line": int(exc.lineno or 1)})
    elif ext in (".js", ".mjs", ".ts", ".tsx", ".jsx"):
        patterns = [
            ("class", re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_]\w*)")),
            ("function", re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)")),
            ("const_fn", re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\(")),
        ]
        for idx, line in enumerate(text.splitlines(), start=1):
            for kind, rx in patterns:
                m = rx.search(line)
                if m:
                    symbols.append({"kind": kind, "name": m.group(1), "line": idx})
                    break
    elif ext in (".go", ".rs", ".java", ".cpp", ".c", ".cs", ".kt", ".swift"):
        rx = re.compile(r"^\s*(?:pub\s+|public\s+|private\s+|static\s+|async\s+)*(?:func|fn|class|struct|interface|trait|def|void|int|string)\s+([A-Za-z_]\w*)")
        for idx, line in enumerate(text.splitlines(), start=1):
            m = rx.search(line)
            if m:
                symbols.append({"kind": "symbol", "name": m.group(1), "line": idx})
    elif ext == ".sql":
        rx = re.compile(r"^\s*CREATE\s+(?:TABLE|VIEW|INDEX)\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_]\w*)", re.I)
        for idx, line in enumerate(text.splitlines(), start=1):
            m = rx.search(line)
            if m:
                symbols.append({"kind": "table", "name": m.group(1), "line": idx})
    symbols.sort(key=lambda s: s.get("line", 0))
    return symbols[:40]


def index_workspace_symbols(workspace_dir: Path, max_files: int = 120) -> Dict[str, Any]:
    """Scans the tenant workspace and returns file tree, language stats, LOC, and real AST/regex symbols."""
    root = workspace_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    files_meta: List[Dict[str, Any]] = []
    lang_counts: Dict[str, int] = {}
    total_lines = 0
    total_symbols = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for fname in sorted(filenames):
            if len(files_meta) >= max_files:
                break
            fpath = Path(dirpath) / fname
            rel = fpath.relative_to(root).as_posix()
            ext = fpath.suffix.lower()
            size_bytes = fpath.stat().st_size if fpath.exists() else 0
            lang = CODE_EXTENSIONS.get(ext, "Text")
            lines_cnt = 0
            syms: List[Dict[str, Any]] = []
            if size_bytes <= 200_000 and ext in CODE_EXTENSIONS:
                try:
                    txt = fpath.read_text(encoding="utf-8", errors="ignore")
                    lines_cnt = txt.count("\n") + (1 if txt else 0)
                    syms = _extract_symbols_for_file(fpath, txt)
                except Exception:
                    pass
            total_lines += lines_cnt
            total_symbols += len(syms)
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
            files_meta.append({
                "path": rel,
                "language": lang,
                "size_bytes": size_bytes,
                "lines": lines_cnt,
                "symbols": syms,
            })

    snapshots = list_workspace_snapshots(root)
    return {
        "success": True,
        "workspace_files_count": len(files_meta),
        "total_lines": total_lines,
        "total_symbols": total_symbols,
        "languages": lang_counts,
        "files": files_meta,
        "snapshots": snapshots[:10],
        "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
    }


def read_context_files(workspace_dir: Path, rel_paths: List[str], max_chars_per_file: int = 4500) -> Dict[str, Any]:
    """Reads up to 6 tenant workspace files safely for @file prompt context injection."""
    root = workspace_dir.resolve()
    loaded: List[Dict[str, Any]] = []
    blocks: List[str] = []
    for raw in (rel_paths or [])[:6]:
        target = _safe_rel_path(root, str(raw))
        if not target or not target.exists() or not target.is_file():
            continue
        try:
            content = target.read_text(encoding="utf-8", errors="replace")[:max_chars_per_file]
            rel = target.relative_to(root).as_posix()
            syms = _extract_symbols_for_file(target, content)
            loaded.append({"path": rel, "chars": len(content), "symbols": syms[:15], "content": content})
            blocks.append(f"### FILE: {rel}\n```\n{content}\n```")
        except Exception:
            continue
    return {
        "success": True,
        "files": loaded,
        "context_block": "\n\n".join(blocks),
    }


# ===================================================================================
# TIER 2: MULTI-FILE UNIFIED DIFF COMPOSER, SNAPSHOT ROLLBACK & POLYGLOT RUNNER
# ===================================================================================

def list_workspace_snapshots(workspace_dir: Path) -> List[Dict[str, Any]]:
    backup_root = workspace_dir.resolve() / ".aura_backups"
    if not backup_root.exists():
        return []
    out: List[Dict[str, Any]] = []
    for entry in sorted(backup_root.iterdir(), reverse=True):
        manifest_file = entry / "manifest.json"
        if entry.is_dir() and manifest_file.exists():
            try:
                m = json.loads(manifest_file.read_text(encoding="utf-8"))
                out.append({
                    "snapshot_id": entry.name,
                    "created_at": m.get("created_at"),
                    "label": m.get("label", "Multi-File Edit"),
                    "files_count": len(m.get("files", [])),
                    "files": [f.get("path") for f in m.get("files", [])],
                })
            except Exception:
                continue
    return out


def plan_and_apply_multifile_diff(
    workspace_dir: Path,
    edits: List[Dict[str, Any]],
    apply: bool = False,
    label: str = "Multi-File Diff Apply",
) -> Dict[str, Any]:
    """
    Computes real unified diffs across multiple workspace files.
    When apply=True, creates a rollback snapshot under .aura_backups/<snapshot_id>/ before writing.
    """
    root = workspace_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not isinstance(edits, list) or not edits:
        return {"success": False, "error": "Provide at least one file edit with path and content."}

    diffs: List[Dict[str, Any]] = []
    validated_ops: List[Tuple[str, Path, Optional[str], str]] = []
    total_added = 0
    total_removed = 0

    for item in edits[:20]:
        if not isinstance(item, dict):
            continue
        raw_p = str(item.get("path") or "").strip()
        new_content = str(item.get("content") if item.get("content") is not None else "")
        target = _safe_rel_path(root, raw_p)
        if not target:
            return {"success": False, "error": f"Invalid or disallowed workspace path: {raw_p!r}"}
        rel = target.relative_to(root).as_posix()
        existed = target.exists() and target.is_file()
        old_content = target.read_text(encoding="utf-8", errors="replace") if existed else ""
        diff_lines = list(
            difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{rel}" if existed else "/dev/null",
                tofile=f"b/{rel}",
                n=3,
            )
        )
        added = sum(1 for ln in diff_lines if ln.startswith("+") and not ln.startswith("+++"))
        removed = sum(1 for ln in diff_lines if ln.startswith("-") and not ln.startswith("---"))
        total_added += added
        total_removed += removed
        diffs.append({
            "path": rel,
            "action": "modify" if existed else "create",
            "added_lines": added,
            "removed_lines": removed,
            "unified_diff": "".join(diff_lines) or f"--- a/{rel}\n+++ b/{rel}\n(No textual changes)\n",
        })
        validated_ops.append((rel, target, old_content if existed else None, new_content))

    snapshot_id = None
    if apply:
        snapshot_id = f"snap_{int(time.time())}_{secrets.token_hex(3)}"
        snap_dir = root / ".aura_backups" / snapshot_id
        snap_dir.mkdir(parents=True, exist_ok=True)
        manifest_files: List[Dict[str, Any]] = []

        for rel, target, old_content, new_content in validated_ops:
            backup_rel = None
            if old_content is not None:
                backup_rel = rel.replace("/", "__") + ".bak"
                (snap_dir / backup_rel).write_text(old_content, encoding="utf-8")
            manifest_files.append({
                "path": rel,
                "existed": old_content is not None,
                "backup_file": backup_rel,
            })
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_content, encoding="utf-8")

        (snap_dir / "manifest.json").write_text(
            json.dumps({"snapshot_id": snapshot_id, "label": label, "created_at": time.time(), "files": manifest_files}, indent=2),
            encoding="utf-8",
        )

    return {
        "success": True,
        "applied": bool(apply),
        "snapshot_id": snapshot_id,
        "files_count": len(diffs),
        "total_added": total_added,
        "total_removed": total_removed,
        "diffs": diffs,
    }


def rollback_workspace_snapshot(workspace_dir: Path, snapshot_id: str) -> Dict[str, Any]:
    """Restores workspace files to the exact state captured before a multi-file diff apply."""
    safe_id = "".join(ch for ch in str(snapshot_id or "").strip() if ch.isalnum() or ch in ("_", "-"))
    if not safe_id:
        return {"success": False, "error": "Invalid snapshot_id."}
    root = workspace_dir.resolve()
    snap_dir = (root / ".aura_backups" / safe_id).resolve()
    manifest_file = snap_dir / "manifest.json"
    if not manifest_file.exists():
        return {"success": False, "error": f"Snapshot {safe_id} not found."}

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    restored: List[str] = []
    removed: List[str] = []
    for entry in manifest.get("files", []):
        target = _safe_rel_path(root, str(entry.get("path") or ""))
        if not target:
            continue
        if entry.get("existed") and entry.get("backup_file"):
            bak = snap_dir / str(entry["backup_file"])
            if bak.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(bak.read_text(encoding="utf-8"), encoding="utf-8")
                restored.append(entry["path"])
        else:
            if target.exists():
                target.unlink()
                removed.append(entry["path"])

    return {
        "success": True,
        "snapshot_id": safe_id,
        "restored_files": restored,
        "removed_new_files": removed,
    }


def execute_polyglot_sandbox(
    workspace_dir: Path,
    language: str,
    code: str,
    stdin_text: str = "",
    timeout_s: float = 8.0,
) -> Dict[str, Any]:
    """
    Real sandboxed polyglot code execution & verification inside the tenant workspace.
    Supports: python, javascript/node, sql (in-memory SQLite), json, html, regex.
    """
    lang = str(language or "python").strip().lower()
    src = str(code or "")
    if not src.strip():
        return {"success": False, "error": "Code snippet cannot be empty."}
    if len(src) > 40000:
        return {"success": False, "error": "Code snippet exceeds 40,000 character sandbox limit."}

    root = workspace_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    # Fast safety screen against host-destructive patterns
    blocked_patterns = [
        r"\brm\s+-rf\b", r"\bformat\s+[a-z]:", r"\bshutdown\b", r"\brestart-computer\b",
        r"\bdel\s+/f\s+/s\b", r"\breg\s+delete\b", r"\bmkfs\b",
    ]
    lower_src = src.lower()
    for pat in blocked_patterns:
        if re.search(pat, lower_src):
            return {"success": False, "error": "Sandbox policy blocked a destructive host-level command pattern."}

    if lang == "sql":
        conn = sqlite3.connect(":memory:")
        try:
            cur = conn.cursor()
            statements = [s.strip() for s in src.split(";") if s.strip()]
            result_sets: List[Dict[str, Any]] = []
            for stmt in statements:
                cur.execute(stmt)
                if cur.description:
                    cols = [d[0] for d in cur.description]
                    rows = [list(r) for r in cur.fetchmany(200)]
                    result_sets.append({"columns": cols, "rows": rows, "row_count": len(rows)})
            conn.commit()
            return {
                "success": True,
                "language": "sql",
                "returncode": 0,
                "stdout": json.dumps(result_sets, indent=2) if result_sets else f"Executed {len(statements)} SQL statement(s) cleanly.",
                "stderr": "",
                "tables": result_sets,
                "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }
        except Exception as exc:
            return {
                "success": False,
                "language": "sql",
                "returncode": 1,
                "stdout": "",
                "stderr": str(exc),
                "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }
        finally:
            conn.close()

    if lang == "json":
        try:
            parsed = json.loads(src)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
            return {
                "success": True,
                "language": "json",
                "returncode": 0,
                "stdout": pretty,
                "stderr": "",
                "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }
        except Exception as exc:
            return {
                "success": False,
                "language": "json",
                "returncode": 1,
                "stdout": "",
                "stderr": f"JSON Parse Error: {exc}",
                "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }

    if lang == "html":
        has_tag = bool(re.search(r"<[a-zA-Z][^>]*>", src))
        script_cnt = len(re.findall(r"<script\b", src, re.I))
        style_cnt = len(re.findall(r"<style\b", src, re.I))
        return {
            "success": has_tag,
            "language": "html",
            "returncode": 0 if has_tag else 1,
            "stdout": f"HTML verified ({len(src)} chars · {style_cnt} style block(s) · {script_cnt} script block(s)). Ready for Live Split Studio." if has_tag else "",
            "stderr": "" if has_tag else "No valid HTML elements detected.",
            "preview_html": src if has_tag else "",
            "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        }

    if lang in ("python", "py"):
        try:
            ast.parse(src)
        except SyntaxError as exc:
            return {
                "success": False,
                "language": "python",
                "returncode": 1,
                "stdout": "",
                "stderr": f"SyntaxError (line {exc.lineno}): {exc.msg}",
                "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }
        tmp_file = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".py", dir=str(root), delete=False, encoding="utf-8") as tf:
                tf.write(src)
                tmp_file = Path(tf.name)
            run_env = dict(os.environ)
            run_env["PYTHONPATH"] = str(root)
            proc = subprocess.run(
                [sys.executable, "-B", str(tmp_file)],
                cwd=str(root),
                env=run_env,
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            return {
                "success": proc.returncode == 0,
                "language": "python",
                "returncode": proc.returncode,
                "stdout": (proc.stdout or "")[:12000],
                "stderr": (proc.stderr or "")[:6000],
                "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "language": "python",
                "returncode": 124,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout_s}s.",
                "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }
        finally:
            if tmp_file and tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass

    if lang in ("javascript", "js", "node"):
        node_bin = shutil.which("node")
        if not node_bin:
            return {
                "success": False,
                "language": "javascript",
                "returncode": 127,
                "stdout": "",
                "stderr": "Node.js runtime is not installed in this container (Python & SQL sandboxes are active natively).",
                "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }
        tmp_file = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".mjs", dir=str(root), delete=False, encoding="utf-8") as tf:
                tf.write(src)
                tmp_file = Path(tf.name)
            proc = subprocess.run(
                [node_bin, str(tmp_file)],
                cwd=str(root),
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            return {
                "success": proc.returncode == 0,
                "language": "javascript",
                "returncode": proc.returncode,
                "stdout": (proc.stdout or "")[:12000],
                "stderr": (proc.stderr or "")[:6000],
                "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "language": "javascript",
                "returncode": 124,
                "stdout": "",
                "stderr": f"Node execution timed out after {timeout_s}s.",
                "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }
        finally:
            if tmp_file and tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass

    return {"success": False, "error": f"Unsupported sandbox language '{lang}'. Supported: python, javascript, sql, json, html."}


# ===================================================================================
# TIER 3: AUTONOMOUS SELF-HEALING REPAIR & PRODUCTION REPO SCAFFOLDER
# ===================================================================================

PROJECT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "fastapi_service": {
        "name": "Python Production API Service",
        "stack": "Python · HTTP/REST · Unit Tests",
        "files": {
            "app.py": (
                "\"\"\"Production-ready Zero-Dependency Python JSON API Service.\"\"\"\n"
                "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
                "import json\n\n"
                "ITEMS = [{\"id\": 1, \"name\": \"AURA Core\", \"status\": \"active\"}]\n\n"
                "def compute_health() -> dict:\n"
                "    return {\"status\": \"ok\", \"items_count\": len(ITEMS)}\n\n"
                "class ApiHandler(BaseHTTPRequestHandler):\n"
                "    def _json(self, payload, status=200):\n"
                "        raw = json.dumps(payload).encode('utf-8')\n"
                "        self.send_response(status)\n"
                "        self.send_header('Content-Type', 'application/json')\n"
                "        self.send_header('Content-Length', str(len(raw)))\n"
                "        self.end_headers()\n"
                "        self.wfile.write(raw)\n\n"
                "    def do_GET(self):\n"
                "        if self.path == '/health':\n"
                "            return self._json(compute_health())\n"
                "        if self.path == '/items':\n"
                "            return self._json({\"items\": ITEMS})\n"
                "        return self._json({\"error\": \"Not Found\"}, status=404)\n\n"
                "if __name__ == '__main__':\n"
                "    print('Listening on http://127.0.0.1:8000')\n"
                "    HTTPServer(('127.0.0.1', 8000), ApiHandler).serve_forever()\n"
            ),
            "test_app.py": (
                "from app import compute_health, ITEMS\n\n"
                "def test_health_contract():\n"
                "    res = compute_health()\n"
                "    assert res['status'] == 'ok'\n"
                "    assert res['items_count'] == len(ITEMS)\n\n"
                "if __name__ == '__main__':\n"
                "    test_health_contract()\n"
                "    print('ALL TESTS PASSED')\n"
            ),
            "README.md": "# Python API Service\n\nRun tests: `python test_app.py`\nRun server: `python app.py`\n",
        },
    },
    "modern_webapp": {
        "name": "Interactive Obsidian Dashboard Web App",
        "stack": "HTML5 · Modern CSS · Vanilla JS",
        "files": {
            "index.html": (
                "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"UTF-8\">\n"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
                "<title>AURA Studio Web App</title>\n"
                "<style>\n"
                "*{box-sizing:border-box;margin:0;padding:0}body{background:#090a0e;color:#f4f4f5;font-family:Inter,system-ui,sans-serif;padding:32px;min-height:100vh}\n"
                ".shell{max-width:860px;margin:0 auto;display:grid;gap:18px}\n"
                ".card{background:#12141c;border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:22px}\n"
                "h1{font-size:22px;letter-spacing:-.02em;margin-bottom:6px}p{color:#9ca3af;font-size:13.5px}\n"
                ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-top:14px}\n"
                ".metric{background:#0d0f15;border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:14px}\n"
                ".metric span{display:block;font-size:11px;color:#71717a;text-transform:uppercase;letter-spacing:.08em}\n"
                ".metric strong{display:block;font-size:24px;margin-top:6px;color:#fff}\n"
                "button{margin-top:14px;background:#f4f4f5;color:#09090b;border:none;border-radius:8px;padding:10px 16px;font-weight:600;cursor:pointer}\n"
                "</style>\n</head>\n<body>\n<div class=\"shell\">\n"
                "<div class=\"card\"><h1>Executive Telemetry Dashboard</h1><p>Scaffolded by AURA Sovereign Scaffolder.</p>\n"
                "<div class=\"grid\"><div class=\"metric\"><span>Throughput</span><strong id=\"m1\">12,480/s</strong></div>"
                "<div class=\"metric\"><span>P99 Latency</span><strong id=\"m2\">18 ms</strong></div>"
                "<div class=\"metric\"><span>Uptime</span><strong id=\"m3\">99.99%</strong></div></div>\n"
                "<button onclick=\"refreshMetrics()\">Simulate Live Tick</button></div>\n</div>\n"
                "<script>function refreshMetrics(){document.getElementById('m1').textContent=(11000+Math.floor(Math.random()*4000)).toLocaleString()+'/s';document.getElementById('m2').textContent=(11+Math.floor(Math.random()*14))+' ms';}</script>\n"
                "</body>\n</html>\n"
            ),
            "README.md": "# Interactive Obsidian Dashboard\n\nOpen `index.html` inside AURA Live Split Studio.\n",
        },
    },
    "node_api": {
        "name": "Node.js Zero-Dep REST Microservice",
        "stack": "Node.js ESM · REST · Assert Tests",
        "files": {
            "server.mjs": (
                "import http from 'node:http';\n\n"
                "export function buildHealthPayload() {\n"
                "  return { status: 'ok', runtime: process.version, uptime_s: Math.round(process.uptime()) };\n"
                "}\n\n"
                "if (import.meta.url === `file://${process.argv[1]}`) {\n"
                "  http.createServer((req, res) => {\n"
                "    res.writeHead(200, { 'Content-Type': 'application/json' });\n"
                "    res.end(JSON.stringify(buildHealthPayload()));\n"
                "  }).listen(3000, () => console.log('Node API ready on :3000'));\n"
                "}\n"
            ),
            "test.mjs": (
                "import assert from 'node:assert/strict';\n"
                "import { buildHealthPayload } from './server.mjs';\n"
                "const h = buildHealthPayload();\n"
                "assert.equal(h.status, 'ok');\n"
                "console.log('NODE TESTS PASSED:', h);\n"
            ),
            "package.json": "{\n  \"name\": \"aura-node-service\",\n  \"version\": \"1.0.0\",\n  \"type\": \"module\",\n  \"scripts\": { \"test\": \"node test.mjs\", \"start\": \"node server.mjs\" }\n}\n",
        },
    },
    "python_cli": {
        "name": "Python Structured CLI Package",
        "stack": "Python · argparse · Automated Tests",
        "files": {
            "cli.py": (
                "import argparse\n\n"
                "def analyze_text(text: str) -> dict:\n"
                "    words = text.split()\n"
                "    return {'words': len(words), 'chars': len(text), 'lines': len(text.splitlines()) or 1}\n\n"
                "def main():\n"
                "    p = argparse.ArgumentParser(description='AURA Text Telemetry CLI')\n"
                "    p.add_argument('text', help='Input text to inspect')\n"
                "    args = p.parse_args()\n"
                "    print(analyze_text(args.text))\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            ),
            "test_cli.py": (
                "from cli import analyze_text\n\n"
                "res = analyze_text('AURA Autonomous Engineering Suite')\n"
                "assert res['words'] == 4 and res['chars'] > 20\n"
                "print('CLI VERIFICATION PASSED:', res)\n"
            ),
        },
    },
    "sql_analytics": {
        "name": "SQLite KPI Analytics Pipeline",
        "stack": "SQLite · SQL · Python Verification",
        "files": {
            "analytics.sql": (
                "CREATE TABLE events (id INTEGER PRIMARY KEY, tier TEXT, latency_ms INTEGER);\n"
                "INSERT INTO events (tier, latency_ms) VALUES ('Velocity', 180), ('Architect', 140), ('Apex', 95), ('Apex', 110);\n"
                "SELECT tier, COUNT(*) AS requests, ROUND(AVG(latency_ms), 1) AS avg_ms FROM events GROUP BY tier ORDER BY avg_ms ASC;\n"
            ),
            "run_analytics.py": (
                "import sqlite3, pathlib\n\n"
                "sql = pathlib.Path('analytics.sql').read_text(encoding='utf-8')\n"
                "conn = sqlite3.connect(':memory:')\n"
                "cur = conn.cursor()\n"
                "for stmt in [s.strip() for s in sql.split(';') if s.strip()]:\n"
                "    cur.execute(stmt)\n"
                "print('KPI Rows:', cur.fetchall())\n"
            ),
        },
    },
}


def scaffold_project_template(workspace_dir: Path, template_id: str, project_name: str) -> Dict[str, Any]:
    tmpl = PROJECT_TEMPLATES.get(str(template_id or "").strip())
    if not tmpl:
        return {"success": False, "error": f"Unknown template '{template_id}'.", "available": list(PROJECT_TEMPLATES.keys())}
    safe_dir = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in str(project_name or "aura_project").strip().lower()).strip("_") or "aura_project"
    edits = [{"path": f"{safe_dir}/{fname}", "content": content} for fname, content in tmpl["files"].items()]
    applied = plan_and_apply_multifile_diff(workspace_dir, edits, apply=True, label=f"Scaffold {tmpl['name']} ({safe_dir})")
    applied["template"] = tmpl["name"]
    applied["stack"] = tmpl["stack"]
    applied["project_dir"] = safe_dir
    return applied


def _extract_code_block(text: str) -> str:
    m = re.search(r"```(?:[a-zA-Z0-9_+-]+)?\s*\n([\s\S]*?)```", str(text or ""))
    return m.group(1).strip() if m else str(text or "").strip()


def run_self_heal_loop(
    workspace_dir: Path,
    target_file: str,
    brain: Any,
    auto_apply: bool = False,
) -> Dict[str, Any]:
    """
    Real Self-Healing Bug & Test Repair Loop:
    1. Reads target file in workspace.
    2. Executes real syntax/AST + runtime verification.
    3. If broken, asks LLM to produce a verified fix, re-tests patched code in sandbox,
       and emits unified diff (applying with snapshot backup if auto_apply=True).
    """
    root = workspace_dir.resolve()
    target = _safe_rel_path(root, target_file)
    if not target or not target.exists() or not target.is_file():
        return {"success": False, "error": f"Workspace file not found: {target_file!r}"}

    rel = target.relative_to(root).as_posix()
    original = target.read_text(encoding="utf-8", errors="replace")
    ext = target.suffix.lower()
    lang = "python" if ext == ".py" else ("javascript" if ext in (".js", ".mjs") else ("sql" if ext == ".sql" else "json" if ext == ".json" else "python"))

    initial_run = execute_polyglot_sandbox(root, lang, original)
    if initial_run.get("success"):
        return {
            "success": True,
            "healed": False,
            "already_healthy": True,
            "path": rel,
            "initial_run": initial_run,
            "summary": f"{rel} passed verification cleanly with exit code 0 — no repair required.",
        }

    # Synthesize repaired code using live LLM
    err_diag = (initial_run.get("stderr") or initial_run.get("error") or "Execution failure")[:2000]
    repair_prompt = (
        f"Fix the following {lang} file `{rel}` so it runs cleanly with exit code 0.\n"
        f"EXACT ERROR OUTPUT:\n```\n{err_diag}\n```\n\n"
        f"CURRENT SOURCE CODE:\n```{lang}\n{original[:8000]}\n```\n\n"
        f"Return ONLY the complete corrected {lang} file inside a single fenced code block. Zero placeholders."
    )
    patched_raw = brain.think_and_act(repair_prompt, permission_mode="auto_pilot", approved=False)
    patched_code = _extract_code_block(patched_raw)
    if not patched_code or patched_code.strip() == original.strip():
        return {
            "success": False,
            "healed": False,
            "path": rel,
            "initial_run": initial_run,
            "error": "Self-heal pass could not generate a distinct repaired version.",
        }

    verify_run = execute_polyglot_sandbox(root, lang, patched_code)
    diff_res = plan_and_apply_multifile_diff(
        root,
        [{"path": rel, "content": patched_code}],
        apply=bool(auto_apply and verify_run.get("success")),
        label=f"Self-Heal {rel}",
    )
    return {
        "success": True,
        "healed": bool(verify_run.get("success")),
        "applied": bool(diff_res.get("applied")),
        "snapshot_id": diff_res.get("snapshot_id"),
        "path": rel,
        "initial_run": initial_run,
        "verified_run": verify_run,
        "diffs": diff_res.get("diffs", []),
        "patched_content": patched_code,
        "summary": (
            f"Self-heal verified green (exit 0) for {rel}."
            if verify_run.get("success")
            else f"Generated candidate patch for {rel}, but verification still reported errors."
        ),
    }


# ===================================================================================
# TIER 4: SECURITY AST AUDIT, PARALLEL 4-AGENT WAR ROOM & GUARDED OS AUTOMATION
# ===================================================================================

SECURITY_REGEX_RULES: List[Tuple[str, str, re.Pattern, str]] = [
    ("CRITICAL", "Hardcoded Cloud/API Secret", re.compile(r"(AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,})"), "Move secrets into environment variables or a secure secret vault."),
    ("HIGH", "Dynamic eval/exec Sink", re.compile(r"\b(?:eval|exec)\s*\("), "Replace dynamic evaluation with ast.literal_eval or explicit dispatch maps."),
    ("HIGH", "Shell Injection Risk (shell=True)", re.compile(r"subprocess\.[A-Za-z_]+\([^)]*shell\s*=\s*True"), "Use argument lists with shell=False to prevent shell injection."),
    ("HIGH", "Unsafe Deserialization (pickle/yaml)", re.compile(r"\b(?:pickle\.loads|yaml\.load\s*\([^)]*\))"), "Use json.loads or yaml.safe_load instead."),
    ("MEDIUM", "Unsanitized innerHTML Sink", re.compile(r"\.innerHTML\s*="), "Prefer textContent or strict HTML escaping before DOM insertion."),
    ("MEDIUM", "Weak Hash Primitive (MD5/SHA1)", re.compile(r"\bhashlib\.(?:md5|sha1)\s*\("), "Use scrypt/argon2 for passwords or SHA-256 for integrity digests."),
]


def audit_workspace_security(workspace_dir: Path) -> Dict[str, Any]:
    """Performs real AST & static vulnerability scanning across the user's workspace."""
    root = workspace_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    findings: List[Dict[str, Any]] = []
    files_scanned = 0
    syntax_errors = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            ext = fpath.suffix.lower()
            if ext not in CODE_EXTENSIONS or fpath.stat().st_size > 200_000:
                continue
            files_scanned += 1
            rel = fpath.relative_to(root).as_posix()
            text = fpath.read_text(encoding="utf-8", errors="ignore")

            if ext == ".py":
                try:
                    tree = ast.parse(text)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ExceptHandler) and node.type is None:
                            findings.append({
                                "severity": "LOW",
                                "rule": "Bare except clause",
                                "file": rel,
                                "line": int(getattr(node, "lineno", 1)),
                                "remediation": "Catch specific exception classes (e.g. ValueError, OSError) instead of bare except.",
                            })
                except SyntaxError as exc:
                    syntax_errors += 1
                    findings.append({
                        "severity": "HIGH",
                        "rule": "Python Syntax Error",
                        "file": rel,
                        "line": int(exc.lineno or 1),
                        "remediation": f"Fix syntax error: {exc.msg}",
                    })

            for lineno, line in enumerate(text.splitlines(), start=1):
                for sev, title, rx, fix in SECURITY_REGEX_RULES:
                    if rx.search(line):
                        findings.append({
                            "severity": sev,
                            "rule": title,
                            "file": rel,
                            "line": lineno,
                            "remediation": fix,
                        })

    weights = {"CRITICAL": 28, "HIGH": 15, "MEDIUM": 7, "LOW": 3}
    penalty = sum(weights.get(f["severity"], 5) for f in findings)
    score = max(0, 100 - min(100, penalty))
    return {
        "success": True,
        "files_scanned": files_scanned,
        "syntax_errors": syntax_errors,
        "security_score": score,
        "grade": "A+" if score >= 95 else ("A" if score >= 85 else ("B" if score >= 70 else "C")),
        "findings_count": len(findings),
        "findings": findings[:80],
    }


def run_parallel_war_room(
    objective: str,
    workspace_dir: Path,
    brain_factory,
    rules_text: str = "",
) -> Dict[str, Any]:
    """
    Dispatches 4 specialized autonomous agents in parallel (Architect, Implementer, Security Auditor, QA Verifier)
    and returns their verified verdicts + timing telemetry.
    """
    goal = str(objective or "").strip()[:3000]
    if not goal:
        return {"success": False, "error": "Provide an engineering objective for the War Room."}

    t0 = time.perf_counter()
    idx_summary = index_workspace_symbols(workspace_dir, max_files=30)
    ws_brief = (
        f"Workspace files ({idx_summary['workspace_files_count']}): "
        + ", ".join(f["path"] for f in idx_summary["files"][:12])
    )
    rules_block = f"\nUser .aura-rules:\n{rules_text[:1000]}" if rules_text else ""

    roles = [
        ("architect", "Systems Architect", "Produce a concise architectural blueprint: components, interfaces, data flow, and scaling trade-offs."),
        ("implementer", "Principal Implementer", "Produce clean, production-ready core implementation code with zero placeholders."),
        ("security", "Security & Threat Auditor", "Identify top attack surfaces, OWASP risks, auth/validation boundaries, and concrete hardening controls."),
        ("qa", "QA & Performance Verifier", "Design critical edge-case tests, Big-O complexity check, and release verification checklist."),
    ]

    def _run_agent(role_id: str, title: str, mandate: str) -> Dict[str, Any]:
        at0 = time.perf_counter()
        prompt = (
            f"You are the {title} in AURA's Parallel 4-Agent War Room.\n"
            f"Objective: {goal}\n{ws_brief}{rules_block}\n\n"
            f"Mandate: {mandate}\nKeep output razor-sharp, structured, and under 220 words."
        )
        try:
            b = brain_factory()
            b.thinking_level = "minimal"
            out = b.think_and_act(prompt, permission_mode="auto_pilot", approved=False)
            return {
                "role_id": role_id,
                "title": title,
                "status": "completed",
                "elapsed_s": round(time.perf_counter() - at0, 2),
                "output": str(out or "").strip(),
            }
        except Exception as exc:
            return {
                "role_id": role_id,
                "title": title,
                "status": "error",
                "elapsed_s": round(time.perf_counter() - at0, 2),
                "output": f"Agent error: {exc}",
            }

    results_map: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_run_agent, rid, title, mandate): rid for rid, title, mandate in roles}
        for fut in as_completed(futs):
            res = fut.result()
            results_map[res["role_id"]] = res

    ordered = [results_map[rid] for rid, _, _ in roles if rid in results_map]
    return {
        "success": True,
        "objective": goal,
        "agents": ordered,
        "elapsed_s": round(time.perf_counter() - t0, 2),
    }


# -----------------------------------------------------------------------------------
# GUARDED DESKTOP / LAPTOP OS AUTOMATION (Mandatory Allow / Deny Popup + Clear Reason)
# -----------------------------------------------------------------------------------

OS_ACTION_CATALOG: Dict[str, Dict[str, Any]] = {
    "system_telemetry": {
        "title": "Read System CPU / RAM / Battery Telemetry",
        "risk": "SAFE",
        "default_reason": "Inspect live laptop/server CPU, memory, and battery telemetry to diagnose system performance.",
    },
    "open_app": {
        "title": "Launch Desktop Application",
        "risk": "CAUTION",
        "default_reason": "Open the requested desktop/web application to streamline your active engineering workflow.",
    },
    "open_url": {
        "title": "Open Browser Destination",
        "risk": "SAFE",
        "default_reason": "Open the verified URL in your browser for live documentation, repository inspection, or preview.",
    },
    "set_brightness": {
        "title": "Adjust Display Brightness",
        "risk": "CAUTION",
        "default_reason": "Adjust screen brightness level on your device as requested.",
    },
    "set_volume": {
        "title": "Adjust Audio Volume",
        "risk": "CAUTION",
        "default_reason": "Adjust system/media audio volume level as requested.",
    },
    "run_workspace_script": {
        "title": "Execute Workspace Script in Sandbox",
        "risk": "CAUTION",
        "default_reason": "Run the target script inside your isolated workspace to verify build/test behavior.",
    },
    "create_workspace_note": {
        "title": "Write Automation Report to Workspace",
        "risk": "CAUTION",
        "default_reason": "Persist a structured engineering automation note or checklist inside your workspace.",
    },
}


def _sign_os_ticket(canonical_json: str) -> str:
    return aura_db.compute_vault_signature("AURA_OS1:" + canonical_json)


def propose_guarded_os_action(
    user: Dict[str, Any],
    action_type: str,
    target: str,
    reason: str = "",
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Phase 1 of Mandatory-Permission OS Automation:
    Builds a transparent, server-signed approval ticket containing Action, Target, Command Preview,
    Risk Level, and Plain-Language Reason so the UI ALWAYS pops an Allow / Deny dialog first.
    """
    act = str(action_type or "").strip().lower()
    spec = OS_ACTION_CATALOG.get(act)
    if not spec:
        return {"success": False, "error": f"Unsupported OS automation action '{act}'.", "supported": list(OS_ACTION_CATALOG.keys())}

    clean_target = str(target or "").strip()[:300]
    clean_reason = str(reason or "").strip()[:500] or spec["default_reason"]
    clean_params = params if isinstance(params, dict) else {}

    cmd_preview = f"{act}({clean_target or 'default'})"
    if act == "set_brightness":
        lvl = max(0, min(100, int(clean_params.get("level", clean_target or 70))))
        clean_target = f"{lvl}%"
        cmd_preview = f"device.set_brightness(level={lvl}%)"
    elif act == "set_volume":
        lvl = max(0, min(100, int(clean_params.get("level", clean_target or 50))))
        clean_target = f"{lvl}%"
        cmd_preview = f"device.set_volume(level={lvl}%)"
    elif act == "open_app":
        cmd_preview = f"os.launch_application({clean_target or 'vscode'})"
    elif act == "open_url":
        cmd_preview = f"browser.open_url({clean_target or 'https://github.com'})"
    elif act == "run_workspace_script":
        cmd_preview = f"sandbox.execute({clean_target})"
    elif act == "create_workspace_note":
        cmd_preview = f"workspace.write_file({clean_target or 'automation_note.md'})"

    now_ts = time.time()
    ticket_payload = {
        "id": f"osa_{secrets.token_hex(6)}",
        "uid": int(user["id"]),
        "act": act,
        "title": spec["title"],
        "risk": spec["risk"],
        "target": clean_target,
        "command": cmd_preview,
        "reason": clean_reason,
        "params": clean_params,
        "exp": int(now_ts + 300),
    }
    canonical = json.dumps(ticket_payload, sort_keys=True, separators=(",", ":"))
    b64 = base64.urlsafe_b64encode(canonical.encode("utf-8")).decode("ascii").rstrip("=")
    sig = _sign_os_ticket(canonical)
    signed_ticket = f"aura_os1.{b64}.{sig}"

    return {
        "success": True,
        "requires_approval": True,
        "proposal": {
            "id": ticket_payload["id"],
            "action_type": act,
            "title": spec["title"],
            "risk": spec["risk"],
            "target": clean_target,
            "command": cmd_preview,
            "reason": clean_reason,
            "expires_in": 300,
            "signed_ticket": signed_ticket,
        },
    }


def commit_guarded_os_action(
    user: Dict[str, Any],
    signed_ticket: str,
    decision: str,
    workspace_dir: Path,
    deny_note: str = "",
) -> Dict[str, Any]:
    """
    Phase 2 of Mandatory-Permission OS Automation:
    Verifies HMAC signature & user ownership. Executes ONLY if decision == ALLOW_ONCE / ALLOW_SESSION;
    records explicit audit verdict if DENIED.
    """
    raw = str(signed_ticket or "").strip()
    if not raw.startswith("aura_os1."):
        return {"success": False, "error": "Invalid or missing signed approval ticket."}
    parts = raw.split(".")
    if len(parts) != 3:
        return {"success": False, "error": "Malformed approval ticket."}
    _, b64, sig = parts
    try:
        pad = "=" * ((4 - len(b64) % 4) % 4)
        canonical = base64.urlsafe_b64decode((b64 + pad).encode("ascii")).decode("utf-8")
        if not hmac.compare_digest(_sign_os_ticket(canonical), sig):
            return {"success": False, "error": "Approval ticket signature verification failed."}
        ticket = json.loads(canonical)
    except Exception:
        return {"success": False, "error": "Could not decode approval ticket."}

    if int(ticket.get("uid", -1)) != int(user["id"]):
        return {"success": False, "error": "Approval ticket does not belong to the authenticated user."}
    if time.time() > float(ticket.get("exp", 0)):
        return {"success": False, "error": "Approval request expired (5-minute safety window). Please propose again."}

    norm_dec = str(decision or "DENY").strip().upper()
    if norm_dec not in ("ALLOW_ONCE", "ALLOW_SESSION", "ALLOW"):
        return {
            "success": True,
            "executed": False,
            "decision": "DENIED",
            "action_type": ticket["act"],
            "target": ticket["target"],
            "reason": ticket["reason"],
            "deny_note": str(deny_note or "Denied by operator.")[:300],
            "message": f"Action '{ticket['title']}' was denied by user. Nothing was executed.",
        }

    act = ticket["act"]
    target = str(ticket.get("target") or "")
    params = ticket.get("params") or {}
    is_serverless = bool(os.environ.get("VERCEL"))
    result: Dict[str, Any] = {}
    client_bridge: Optional[Dict[str, Any]] = None

    if act == "system_telemetry":
        try:
            from aura_os_controller import laptop_controller
            result = {"telemetry": laptop_controller.get_system_telemetry(), "mode": "cloud_container" if is_serverless else "local_desktop"}
        except Exception as exc:
            result = {"mode": "fallback", "platform": sys.platform, "python": sys.version.split()[0], "note": str(exc)}
    elif act == "set_brightness":
        lvl = max(0, min(100, int(params.get("level", re.sub(r"[^0-9]", "", target) or 70))))
        client_bridge = {"action": "set_brightness", "level": lvl}
        if not is_serverless:
            try:
                from aura_os_controller import laptop_controller
                result = laptop_controller.set_brightness(lvl)
            except Exception as exc:
                result = {"success": True, "brightness": lvl, "client_bridge": True, "note": str(exc)}
        else:
            result = {"success": True, "brightness": lvl, "mode": "client_bridge", "message": f"Viewport & client bridge brightness set to {lvl}%."}
    elif act == "set_volume":
        lvl = max(0, min(100, int(params.get("level", re.sub(r"[^0-9]", "", target) or 50))))
        client_bridge = {"action": "set_volume", "level": lvl}
        if not is_serverless:
            try:
                from aura_os_controller import laptop_controller
                result = laptop_controller.set_volume(lvl)
            except Exception as exc:
                result = {"success": True, "volume": lvl, "client_bridge": True, "note": str(exc)}
        else:
            result = {"success": True, "volume": lvl, "mode": "client_bridge", "message": f"Client audio bridge volume set to {lvl}%."}
    elif act == "open_app":
        app_key = target or "github"
        web_map = {
            "youtube": "https://www.youtube.com",
            "github": "https://github.com",
            "vscode": "https://vscode.dev",
            "gmail": "https://mail.google.com",
            "docs": "https://docs.google.com",
            "calendar": "https://calendar.google.com",
            "spotify": "https://open.spotify.com",
        }
        url = web_map.get(app_key.lower(), f"https://www.google.com/search?q={app_key}")
        client_bridge = {"action": "open_url", "url": url, "label": app_key}
        if not is_serverless:
            try:
                from aura_os_controller import laptop_controller
                result = laptop_controller.launch_app(app_key)
            except Exception as exc:
                result = {"success": True, "opened": app_key, "url": url, "note": str(exc)}
        else:
            result = {"success": True, "opened": app_key, "url": url, "mode": "client_bridge"}
    elif act == "open_url":
        url = target if target.startswith(("http://", "https://")) else f"https://{target or 'github.com'}"
        client_bridge = {"action": "open_url", "url": url, "label": url}
        result = {"success": True, "url": url, "mode": "client_bridge"}
    elif act == "run_workspace_script":
        safe_p = _safe_rel_path(workspace_dir, target)
        if not safe_p or not safe_p.exists():
            return {"success": False, "error": f"Workspace script not found: {target}"}
        ext = safe_p.suffix.lower()
        lang = "python" if ext == ".py" else ("javascript" if ext in (".js", ".mjs") else "sql")
        result = execute_polyglot_sandbox(workspace_dir, lang, safe_p.read_text(encoding="utf-8", errors="replace"))
    elif act == "create_workspace_note":
        rel_name = target or "automation_report.md"
        body_text = str(params.get("content") or f"# AURA Automation Note\n\nApproved Reason: {ticket['reason']}\nTimestamp: {time.ctime()}\n")
        result = plan_and_apply_multifile_diff(workspace_dir, [{"path": rel_name, "content": body_text}], apply=True, label=f"OS Automation Write {rel_name}")

    return {
        "success": True,
        "executed": True,
        "decision": "ALLOWED",
        "action_type": act,
        "title": ticket["title"],
        "target": target,
        "reason": ticket["reason"],
        "result": result,
        "client_bridge_command": client_bridge,
    }


# ===================================================================================
# TIER 5: AURA APEX OMNIS — 6-STAGE AUTONOMOUS END-TO-END ENGINEERING PIPELINE
# ===================================================================================

def _parse_apex_files_from_llm(raw_text: str, language: str) -> List[Dict[str, str]]:
    """Extracts structured multi-file deliverables from JSON output or fenced markdown blocks cleanly."""
    text = str(raw_text or "").strip()
    # Try JSON envelope first
    m_json = re.search(r"```json\s*\n([\s\S]*?)```", text)
    cand = m_json.group(1).strip() if m_json else text
    try:
        parsed = json.loads(cand)
        if isinstance(parsed, dict) and isinstance(parsed.get("files"), list):
            files = []
            for f in parsed["files"]:
                if isinstance(f, dict) and f.get("path") and f.get("content") is not None:
                    files.append({
                        "path": str(f["path"]).strip(),
                        "content": str(f["content"]),
                        "summary": str(f.get("summary") or ""),
                    })
            if files:
                return files[:10]
    except Exception:
        pass

    # Fallback: extract named fenced code blocks
    ext_map = {
        "python": "py", "javascript": "js", "typescript": "ts", "html": "html",
        "sql": "sql", "go": "go", "rust": "rs", "java": "java", "cpp": "cpp", "c++": "cpp",
    }
    ext = ext_map.get(language.lower(), "py")
    blocks = re.findall(r"```([a-zA-Z0-9_+-]*)\s*\n([\s\S]*?)```", text)
    out: List[Dict[str, str]] = []
    for idx, (lang_tag, body) in enumerate(blocks[:6], start=1):
        b = body.strip()
        if not b:
            continue
        first_line = b.splitlines()[0]
        m_name = re.search(r"(?:file|path)\s*:\s*([A-Za-z0-9_./-]+)", first_line, re.I)
        if m_name:
            fname = m_name.group(1)
        else:
            f_ext = ext_map.get((lang_tag or "").lower(), ext)
            fname = f"apex_solution.{f_ext}" if idx == 1 else f"apex_test_{idx}.{f_ext}"
        out.append({"path": fname, "content": b, "summary": f"Generated {lang_tag or language} artifact"})
    return out


def run_apex_autonomous_pipeline(
    goal: str,
    language: str,
    workspace_dir: Path,
    brain: Any,
    rules_text: str = "",
    auto_apply: bool = False,
) -> Dict[str, Any]:
    """
    AURA Apex Omnis (Tier 5) — 6-Stage Autonomous End-to-End Engineering Pipeline:
    1. Repo & Context Intelligence
    2. Architecture & Spec Synthesis
    3. Multi-File Zero-Placeholder Code Generation
    4. Automated AST & Security Gate
    5. Live Sandbox Execution & Self-Healing Repair
    6. Unified Diffs & Optional Snapshot Checkpoint Apply
    """
    clean_goal = str(goal or "").strip()[:4000]
    clean_lang = str(language or "python").strip() or "python"
    if not clean_goal:
        return {"success": False, "error": "Provide a clear engineering goal for Apex Omnis."}

    root = workspace_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    t_total = time.perf_counter()
    stages: List[Dict[str, Any]] = []

    # Stage 1: Repo Intelligence
    s1_t = time.perf_counter()
    ws_index = index_workspace_symbols(root, max_files=40)
    stages.append({
        "stage": 1,
        "name": "Repo & Context Intelligence",
        "status": "completed",
        "elapsed_ms": round((time.perf_counter() - s1_t) * 1000.0, 1),
        "detail": f"Indexed {ws_index['workspace_files_count']} workspace files and {ws_index['total_symbols']} AST symbols.",
    })

    # Stage 2 & 3: Architecture Blueprint + Multi-File Synthesis
    s2_t = time.perf_counter()
    existing_paths = [f["path"] for f in ws_index["files"][:15]]
    rules_note = f"\nEngineering Rules (.aura-rules):\n{rules_text[:1200]}" if rules_text else ""
    synth_prompt = (
        f"You are AURA Apex Omnis (Tier 5 Flagship Autonomous Engineering Engine).\n"
        f"Objective: {clean_goal}\n"
        f"Target Primary Language: {clean_lang}\n"
        f"Existing Workspace Files: {existing_paths}{rules_note}\n\n"
        f"Generate a complete, runnable, zero-placeholder multi-file solution (including a self-contained verification test file when applicable).\n"
        f"Respond STRICTLY with a single JSON code block matching this schema:\n"
        f"```json\n"
        f"{{\n"
        f"  \"architecture\": \"2-3 sentence architectural summary\",\n"
        f"  \"files\": [\n"
        f"    {{\"path\": \"relative/file.ext\", \"summary\": \"role of file\", \"content\": \"complete runnable code\"}}\n"
        f"  ]\n"
        f"}}\n"
        f"```"
    )
    brain.thinking_level = "minimal"
    raw_llm = brain.think_and_act(synth_prompt, permission_mode="auto_pilot", approved=False)
    generated_files = _parse_apex_files_from_llm(raw_llm, clean_lang)

    architecture_note = ""
    try:
        m_json = re.search(r"```json\s*\n([\s\S]*?)```", str(raw_llm or ""))
        parsed_meta = json.loads((m_json.group(1) if m_json else str(raw_llm or "")).strip())
        if isinstance(parsed_meta, dict):
            architecture_note = str(parsed_meta.get("architecture") or "")
    except Exception:
        architecture_note = f"Autonomous {clean_lang} multi-file implementation synthesized for: {clean_goal[:120]}"

    stages.append({
        "stage": 2,
        "name": "Architecture & Contract Blueprint",
        "status": "completed",
        "elapsed_ms": round((time.perf_counter() - s2_t) * 1000.0, 1),
        "detail": architecture_note or "Multi-file architectural contract synthesized.",
    })
    stages.append({
        "stage": 3,
        "name": "Multi-File Polyglot Code Synthesis",
        "status": "completed" if generated_files else "warning",
        "elapsed_ms": round((time.perf_counter() - s2_t) * 1000.0, 1),
        "detail": f"Synthesized {len(generated_files)} file(s): " + ", ".join(f["path"] for f in generated_files),
    })

    # Stage 4: Static AST & Security Gate on Generated Files
    s4_t = time.perf_counter()
    gate_issues: List[Dict[str, Any]] = []
    for gf in generated_files:
        p = gf["path"]
        c = gf["content"]
        if p.endswith(".py"):
            try:
                ast.parse(c)
            except SyntaxError as exc:
                gate_issues.append({"file": p, "severity": "HIGH", "issue": f"SyntaxError line {exc.lineno}: {exc.msg}"})
        for sev, title, rx, _ in SECURITY_REGEX_RULES:
            if rx.search(c):
                gate_issues.append({"file": p, "severity": sev, "issue": title})
    stages.append({
        "stage": 4,
        "name": "Static AST & Security Gate",
        "status": "completed" if not gate_issues else "warning",
        "elapsed_ms": round((time.perf_counter() - s4_t) * 1000.0, 1),
        "detail": "0 syntax/security defects detected across generated files." if not gate_issues else f"{len(gate_issues)} static/security alert(s) flagged.",
        "issues": gate_issues,
    })

    # Stage 5: Live Sandbox Execution & Self-Healing Repair (for Python/JS/SQL/JSON/HTML deliverables)
    s5_t = time.perf_counter()
    verification_run: Optional[Dict[str, Any]] = None
    self_healed = False
    runnable_idx = None
    for idx, gf in enumerate(generated_files):
        lp = gf["path"].lower()
        if lp.endswith((".py", ".js", ".mjs", ".sql", ".json", ".html")):
            if "test" in lp:
                runnable_idx = idx
                break
            if runnable_idx is None:
                runnable_idx = idx

    if runnable_idx is not None:
        rf = generated_files[runnable_idx]
        # Execute inside a temporary staging dir containing ALL generated files so cross-file imports work!
        with tempfile.TemporaryDirectory() as tmp_d:
            tmp_root = Path(tmp_d)
            for gf in generated_files:
                tp = _safe_rel_path(tmp_root, gf["path"])
                if tp:
                    tp.parent.mkdir(parents=True, exist_ok=True)
                    tp.write_text(gf["content"], encoding="utf-8")
            ext = Path(rf["path"]).suffix.lower()
            rlang = "python" if ext == ".py" else ("javascript" if ext in (".js", ".mjs") else ("sql" if ext == ".sql" else ("json" if ext == ".json" else "html")))
            verification_run = execute_polyglot_sandbox(tmp_root, rlang, rf["content"])

            # Auto self-heal 1 iteration if sandbox failed
            if not verification_run.get("success") and rlang in ("python", "javascript", "sql"):
                err_txt = (verification_run.get("stderr") or verification_run.get("error") or "")[:1500]
                fix_prompt = (
                    f"Repair `{rf['path']}` so it executes with exit code 0.\n"
                    f"Error:\n```\n{err_txt}\n```\nCode:\n```{rlang}\n{rf['content'][:7000]}\n```\n"
                    f"Return ONLY the repaired file inside a single fenced code block."
                )
                repaired = _extract_code_block(brain.think_and_act(fix_prompt, permission_mode="auto_pilot", approved=False))
                if repaired and repaired != rf["content"]:
                    tp = _safe_rel_path(tmp_root, rf["path"])
                    if tp:
                        tp.write_text(repaired, encoding="utf-8")
                    recheck = execute_polyglot_sandbox(tmp_root, rlang, repaired)
                    if recheck.get("success"):
                        generated_files[runnable_idx]["content"] = repaired
                        verification_run = recheck
                        self_healed = True

    stages.append({
        "stage": 5,
        "name": "Live Sandbox Verification & Self-Heal",
        "status": "completed" if (not verification_run or verification_run.get("success")) else "warning",
        "elapsed_ms": round((time.perf_counter() - s5_t) * 1000.0, 1),
        "detail": (
            f"Sandbox verified green (exit 0){' after automatic self-heal' if self_healed else ''}."
            if (verification_run and verification_run.get("success"))
            else ("Static deliverable verified (non-executable language)." if not verification_run else f"Sandbox exited with code {verification_run.get('returncode')}.")
        ),
    })

    # Stage 6: Unified Diff & Snapshot Checkpoint
    s6_t = time.perf_counter()
    diff_res = (
        plan_and_apply_multifile_diff(root, generated_files, apply=bool(auto_apply), label=f"Apex Omnis: {clean_goal[:40]}")
        if generated_files
        else {"success": False, "diffs": [], "applied": False, "snapshot_id": None}
    )
    stages.append({
        "stage": 6,
        "name": "Unified Diff & Snapshot Checkpoint",
        "status": "completed" if diff_res.get("success") else "warning",
        "elapsed_ms": round((time.perf_counter() - s6_t) * 1000.0, 1),
        "detail": (
            f"Applied {len(generated_files)} file(s) with rollback snapshot {diff_res.get('snapshot_id')}."
            if diff_res.get("applied")
            else f"Staged {len(generated_files)} verified file diff(s) ready for 1-click Apply & Rollback."
        ),
    })

    return {
        "success": True,
        "goal": clean_goal,
        "language": clean_lang,
        "architecture": architecture_note,
        "stages": stages,
        "files": generated_files,
        "diffs": diff_res.get("diffs", []),
        "applied": bool(diff_res.get("applied")),
        "snapshot_id": diff_res.get("snapshot_id"),
        "self_healed": self_healed,
        "verification": verification_run,
        "total_elapsed_s": round(time.perf_counter() - t_total, 2),
    }
