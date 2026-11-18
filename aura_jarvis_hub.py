"""Unified JARVIS Automation Hub, Workspace Self-Audit & Hardware Kill-Switch Guardrails."""
from __future__ import annotations

import ast
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent
SECRET_PATTERN = re.compile(
    r"(?:AIza[0-9A-Za-z\-_]{30,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,})"
)
SKIP_DIRS = frozenset({
    ".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv", "engines",
    "workspace", "site-packages", "dist-packages", ".vercel", "dist", "build",
})
WORKSPACE_PY_SUBDIRS = frozenset({"api", "aura_adapters", "generated_benchmarks", "tests"})
_HEALTH_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
_BRIEFING_IO_CACHE: Dict[str, tuple[float, Any]] = {}


def _audit_workspace_health(root_dir: Path = ROOT_DIR) -> Dict[str, Any]:
    """Synthesizes real Python AST, secret hygiene, and test inventory telemetry."""
    cache_key = str(root_dir.resolve())
    now = time.monotonic()
    cached = _HEALTH_CACHE.get(cache_key)
    if cached and (now - cached[0]) < 90.0:
        return dict(cached[1])

    py_files: List[Path] = []
    syntax_errors: List[Dict[str, Any]] = []
    secret_hits: List[str] = []
    test_files: List[str] = []
    is_vercel = bool(os.environ.get("VERCEL"))
    root_resolved = str(root_dir)

    for dirpath, dirnames, filenames in os.walk(root_dir):
        if dirpath == root_resolved and is_vercel:
            dirnames[:] = [d for d in dirnames if d in WORKSPACE_PY_SUBDIRS]
        else:
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            p = Path(dirpath) / fname
            if fname.startswith("test_") and fname.endswith(".py"):
                test_files.append(fname)
            if fname.endswith(".py"):
                py_files.append(p)
                try:
                    src = p.read_text(encoding="utf-8", errors="ignore")
                    ast.parse(src, filename=str(p))
                    if SECRET_PATTERN.search(src):
                        secret_hits.append(p.name)
                except SyntaxError as exc:
                    syntax_errors.append({"file": p.name, "line": exc.lineno, "msg": exc.msg})

    gitignore_ok = False
    gi = root_dir / ".gitignore"
    if gi.exists():
        gitignore_ok = ".env" in gi.read_text(encoding="utf-8", errors="ignore")

    result = {
        "python_modules_checked": len(py_files),
        "syntax_errors": syntax_errors,
        "syntax_clean": len(syntax_errors) == 0,
        "test_suites_detected": sorted(test_files),
        "test_suite_count": len(test_files),
        "hardcoded_secret_hits": secret_hits,
        "secret_hygiene_clean": len(secret_hits) == 0 and gitignore_ok,
        "gitignore_protects_env": gitignore_ok,
    }
    _HEALTH_CACHE[cache_key] = (now, dict(result))
    return result


def _audit_code_ast(target: str = "", root_dir: Path = ROOT_DIR) -> Dict[str, Any]:
    """Inspects a repository Python module via native AST for functions, docstrings, and risk calls."""
    raw_target = (target or "").strip()
    if not raw_target or "://" in raw_target or ("." not in raw_target and "/" not in raw_target and "\\" not in raw_target):
        raw_target = "aura_jarvis_hub.py"
    rel = raw_target.lstrip("/\\")
    candidate = (root_dir / rel).resolve()
    try:
        candidate.relative_to(root_dir.resolve())
    except ValueError:
        return {"success": False, "error": "Target path escapes repository root."}
    if not candidate.exists() or not candidate.is_file() or candidate.suffix != ".py":
        return {"success": False, "error": f"Python target not found: {rel}"}

    src = candidate.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(src, filename=str(candidate))
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    missing_docs = [n.name for n in funcs + classes if not ast.get_docstring(n)]
    risk_calls: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                risk_calls.append(f"{node.func.id}() at line {node.lineno}")
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "system":
                risk_calls.append(f"os.system() at line {node.lineno}")

    return {
        "success": True,
        "file": rel,
        "lines": len(src.splitlines()),
        "classes": len(classes),
        "functions": len(funcs),
        "documented_ratio_pct": round(100.0 * (1.0 - len(missing_docs) / max(1, len(funcs) + len(classes))), 1),
        "missing_docstrings_sample": missing_docs[:8],
        "risky_calls": risk_calls,
    }


class AuraJarvisCoordinator:
    """Thread-safe, per-tenant JARVIS automation dispatcher with Emergency Kill Switch."""

    ROUTINE_SPECS: List[Dict[str, str]] = [
        {
            "key": "repo_health_audit",
            "title": "Workspace Self-Audit & Secret Hygiene",
            "category": "Engineering Guard",
            "description": "AST-parses Python modules, counts test suites, and verifies zero leaked keys.",
        },
        {
            "key": "security_threat_scan",
            "title": "TRINETRA + PayGuard Cyber Threat Scan",
            "category": "Security Forensics",
            "description": "Runs MITRE ATT&CK / CERT-In / UPI collect scam analysis on a payload or URL.",
        },
        {
            "key": "code_ast_review",
            "title": "AST Quality & Risk Inspector",
            "category": "Code Review",
            "description": "Audits class/function density, docstring coverage, and unsafe eval/exec calls.",
        },
        {
            "key": "executive_briefing",
            "title": "JARVIS Executive Morning Briefing",
            "category": "Intelligence",
            "description": "Synthesizes workspace health, live tech headlines RSS, and weather telemetry.",
        },
    ]

    def __init__(self, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = Path(root_dir)
        self._lock = threading.Lock()
        self._tenant_states: Dict[str, Dict[str, Any]] = {}

    def _state_for(self, user_key: str) -> Dict[str, Any]:
        st = self._tenant_states.get(user_key)
        if st is None:
            st = {
                "halted": False,
                "halt_reason": "",
                "halted_at": None,
                "runs_completed": 0,
                "audit_log": [],
            }
            self._tenant_states[user_key] = st
        return st

    def _append_log(self, state: Dict[str, Any], event_type: str, detail: str, status: str) -> None:
        log = state["audit_log"]
        log.insert(0, {
            "timestamp": round(time.time(), 3),
            "event": event_type,
            "status": status,
            "detail": detail[:280],
        })
        if len(log) > 40:
            del log[40:]

    def get_status(self, user_id: Any) -> Dict[str, Any]:
        """Returns current Kill Switch arm/halt state, catalog, and recent audit log."""
        ukey = str(user_id if user_id is not None else "anonymous")
        with self._lock:
            st = self._state_for(ukey)
            return {
                "success": True,
                "halted": bool(st["halted"]),
                "system_state": "HALTED_BY_KILL_SWITCH" if st["halted"] else "ARMED_AND_READY",
                "halt_reason": st["halt_reason"],
                "runs_completed": st["runs_completed"],
                "routines": self.ROUTINE_SPECS,
                "audit_log": list(st["audit_log"][:15]),
            }

    def set_kill_switch(self, user_id: Any, halted: bool, reason: str = "") -> Dict[str, Any]:
        """Engages or disarms the global execution Kill Switch for the scoped tenant."""
        ukey = str(user_id if user_id is not None else "anonymous")
        clean_reason = (reason or ("Emergency Kill Switch activated by operator" if halted else "Operator re-armed JARVIS routines")).strip()
        with self._lock:
            st = self._state_for(ukey)
            st["halted"] = bool(halted)
            st["halt_reason"] = clean_reason if halted else ""
            st["halted_at"] = round(time.time(), 3) if halted else None
            self._append_log(
                st,
                "KILL_SWITCH_ENGAGED" if halted else "SYSTEM_REARMED",
                clean_reason,
                "HALTED" if halted else "ARMED",
            )
            return self.get_status_unlocked(st)

    def get_status_unlocked(self, st: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": True,
            "halted": bool(st["halted"]),
            "system_state": "HALTED_BY_KILL_SWITCH" if st["halted"] else "ARMED_AND_READY",
            "halt_reason": st["halt_reason"],
            "runs_completed": st["runs_completed"],
            "routines": self.ROUTINE_SPECS,
            "audit_log": list(st["audit_log"][:15]),
        }

    def run_routine(self, user_id: Any, routine_key: str, target: str = "") -> Dict[str, Any]:
        """Executes a verified JARVIS automation routine unless Kill Switch is engaged."""
        ukey = str(user_id if user_id is not None else "anonymous")
        rkey = (routine_key or "").strip().lower()
        with self._lock:
            st = self._state_for(ukey)
            if st["halted"]:
                self._append_log(st, f"BLOCKED:{rkey}", "Blocked execution while Kill Switch engaged", "BLOCKED")
                return {
                    "success": False,
                    "halted": True,
                    "error": "Kill Switch is ENGAGED. Re-arm AURA Core before executing routines.",
                }

        handlers: Dict[str, Callable[[str], Dict[str, Any]]] = {
            "repo_health_audit": lambda _t: {"success": True, "routine": "repo_health_audit", "telemetry": _audit_workspace_health(self.root_dir)},
            "security_threat_scan": self._exec_security_scan,
            "code_ast_review": lambda t: _audit_code_ast(t, self.root_dir),
            "executive_briefing": self._exec_briefing,
        }
        fn = handlers.get(rkey)
        if fn is None:
            return {"success": False, "error": f"Unknown JARVIS routine '{rkey}'."}

        t0 = time.time()
        result = fn(target)
        elapsed_ms = round((time.time() - t0) * 1000, 1)

        with self._lock:
            st = self._state_for(ukey)
            st["runs_completed"] += 1
            self._append_log(
                st,
                f"RUN:{rkey}",
                f"target={target or 'workspace'} ({elapsed_ms}ms)",
                "OK" if result.get("success", True) else "ERROR",
            )
            result["elapsed_ms"] = elapsed_ms
            result["audit_log"] = list(st["audit_log"][:12])
            return result

    def _exec_security_scan(self, payload: str) -> Dict[str, Any]:
        sample = (payload or "upi://pay?pa=helpdesk-kyc@okexample&pn=KYC+Refund&am=19999").strip()
        from aura_bharatcode_top10 import BHARATCODE_TOP10_SUITE
        cyber = BHARATCODE_TOP10_SUITE.execute_engine("trinetra", {"prompt": sample})
        upi = BHARATCODE_TOP10_SUITE.execute_engine("payguard_upi", {"prompt": sample})
        return {
            "success": True,
            "routine": "security_threat_scan",
            "payload_scanned": sample[:220],
            "cyber_forensics": cyber,
            "upi_guard": upi,
        }

    def _exec_briefing(self, city: str) -> Dict[str, Any]:
        from concurrent.futures import ThreadPoolExecutor
        from aura_brain import tool_get_news, tool_get_weather

        loc = (city or "Hyderabad").strip()
        now = time.monotonic()

        def _get_cached_weather() -> Dict[str, Any]:
            ck = f"w:{loc.lower()}"
            hit = _BRIEFING_IO_CACHE.get(ck)
            if hit and (now - hit[0]) < 180.0:
                return dict(hit[1])
            val = tool_get_weather(loc)
            _BRIEFING_IO_CACHE[ck] = (time.monotonic(), dict(val))
            return val

        def _get_cached_news() -> Dict[str, Any]:
            ck = "n:ai_india"
            hit = _BRIEFING_IO_CACHE.get(ck)
            if hit and (now - hit[0]) < 180.0:
                return dict(hit[1])
            val = tool_get_news("Artificial Intelligence India")
            _BRIEFING_IO_CACHE[ck] = (time.monotonic(), dict(val))
            return val

        with ThreadPoolExecutor(max_workers=3) as pool:
            f_health = pool.submit(_audit_workspace_health, self.root_dir)
            f_weather = pool.submit(_get_cached_weather)
            f_news = pool.submit(_get_cached_news)
            health = f_health.result(timeout=4.0)
            weather = f_weather.result(timeout=3.5)
            news = f_news.result(timeout=3.5)

        headlines = [a.get("title", "") for a in (news.get("articles") or [])[:4]]
        return {
            "success": True,
            "routine": "executive_briefing",
            "location": loc,
            "weather_summary": weather,
            "top_headlines": headlines,
            "workspace_health": health,
        }


JARVIS_HUB = AuraJarvisCoordinator()
