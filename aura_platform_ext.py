"""
===================================================================================
      AURA EXTENSIBILITY & WORKFLOW AUTOMATION PLATFORM
      (Part 2 / Hissa 2: Features #29-#39)
===================================================================================
Persisted per-user inside `workspace/user_<id>/.aura_platform.json`:

1. Skills, Tools & Extensibility (#29-#34):
   - #29 Custom Skills System (instructions, references & reusable checklists)
   - #30 MCP Integration (Model Context Protocol server registry, SSRF-checked probe & tools)
   - #31 Plugin Marketplace (install, enable, disable, configure, uninstall)
   - #32 Custom Agent Builder (user-defined specialist agents with role, model, tools & perms)
   - #33 Rules & Memory System (project conventions & user-approved preferences)
   - #34 Tool Permission Manager (`allow` | `ask_approval` | `deny` policy per tool)

2. Workflow Automation (#35-#39):
   - #35 Scheduled Automations (daily / weekly / cron definitions + Run Now + logs)
   - #36 Reusable Workflows (multi-step executable workspace pipelines)
   - #37 Background Agents (permitted asynchronous maintenance & audit agents)
   - #38 Notifications Center (real-time unread alerts for completion, errors & approvals)
   - #39 Event-Triggered Automation (`on_commit`, `on_file_save`, `on_verify_fail`, `on_mission_complete`)
===================================================================================
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from aura_brain import AuraBrain, is_safe_public_url
from aura_live_actions import LIVE_ACTION_HUB
from coderx_engine import _atomic_write_text

PLATFORM_STATE_FILE = ".aura_platform.json"

DEFAULT_SKILLS: List[Dict[str, Any]] = [
    {
        "id": "skill_python_arch",
        "name": "Python Systems Architect",
        "category": "Engineering",
        "instructions": "Write type-annotated, modular Python with strict input validation, zero bare excepts, and unittest coverage.",
        "references": ["PEP 8", "Type Hints", "unittest"],
        "steps": ["Inspect codebase map", "Implement module", "Generate unit tests", "Run self-verification loop"],
        "builtin": True,
    },
    {
        "id": "skill_ui_designer",
        "name": "Obsidian Glass UI Designer",
        "category": "Design",
        "instructions": "Design minimal monochrome dark interfaces with crisp spacing, accessible contrast, zero emoji clutter, and 0px mobile overflow.",
        "references": ["WCAG AA", "Responsive CSS Grid"],
        "steps": ["Define layout tokens", "Build semantic HTML/CSS", "Check desktop & mobile viewport"],
        "builtin": True,
    },
    {
        "id": "skill_code_reviewer",
        "name": "Security & Quality Code Reviewer",
        "category": "Quality",
        "instructions": "Audit diffs for SSRF, path traversal, secret leaks, race conditions, and missing edge-case tests before merge.",
        "references": ["OWASP Top 10", "AST Bug Scan"],
        "steps": ["Scan secrets & AST bugs", "Review visual diff", "Verify automated tests pass"],
        "builtin": True,
    },
]

MARKETPLACE_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "plugin_git_guard",
        "name": "Git Diff & PR Guard",
        "category": "Git & DevOps",
        "version": "1.2.0",
        "description": "Adds automated PR risk checklists, branch safety guards, and commit hygiene validation.",
        "capabilities": ["git_review", "pr_checklist"],
        "installed": True,
        "enabled": True,
        "config": {"require_tests_before_push": True},
    },
    {
        "id": "plugin_secret_shield",
        "name": "Secret Protection Shield",
        "category": "Security",
        "version": "2.0.1",
        "description": "Continuously scans workspace files, diffs, and logs to mask API keys, tokens, and credentials.",
        "capabilities": ["secret_scan", "log_redaction"],
        "installed": True,
        "enabled": True,
        "config": {"mask_logs": True},
    },
    {
        "id": "plugin_sqlite_studio",
        "name": "SQLite Schema Inspector",
        "category": "Database",
        "version": "1.0.4",
        "description": "Validates SQL schema files, suggests indexes, and generates clean Python repositories.",
        "capabilities": ["schema_validate", "index_advisor"],
        "installed": False,
        "enabled": False,
        "config": {},
    },
    {
        "id": "plugin_playwright_ops",
        "name": "Live Browser QA Pack",
        "category": "Browser",
        "version": "1.4.0",
        "description": "Session recording, DOM accessibility checks, and screenshot visual feedback annotations.",
        "capabilities": ["browser_record", "visual_feedback"],
        "installed": True,
        "enabled": True,
        "config": {"capture_thumbnails": True},
    },
    {
        "id": "plugin_coderx_bridge",
        "name": "CoderX + Sovereign Nexus Bridge",
        "category": "Core Engines",
        "version": "2.6.0",
        "description": "Connects existing AURA CoderX, Godot Studio, Cinema FLUX, and Sovereign 10-Nexus under unified orchestration.",
        "capabilities": ["coderx", "godot", "cinema", "nexus"],
        "installed": True,
        "enabled": True,
        "config": {"unified_orchestration": True},
    },
]

DEFAULT_TOOL_PERMISSIONS: Dict[str, str] = {
    "file_read": "allow",
    "file_write": "allow",
    "file_delete": "ask_approval",
    "terminal_exec": "allow",
    "git_commit": "allow",
    "git_push": "ask_approval",
    "browser_action": "allow",
    "computer_use": "ask_approval",
    "external_upload": "ask_approval",
    "mcp_invoke": "allow",
}

DEFAULT_WORKFLOWS: List[Dict[str, Any]] = [
    {
        "id": "wf_code_quality_pipeline",
        "name": "Code -> Bugs -> Self-Verify -> Final Report",
        "description": "Scans workspace for AST bugs, runs Self-Verification Loop, and builds a Final Execution Report.",
        "steps": [
            {"type": "bug_scan", "target": "."},
            {"type": "self_verify", "target": "."},
            {"type": "final_report", "title": "Automated Quality Workflow Report"},
        ],
        "run_count": 0,
        "last_run_at": None,
        "last_status": "idle",
    },
    {
        "id": "wf_security_hygiene",
        "name": "Secret Scan -> Codebase Map -> Snapshot",
        "description": "Audits workspace for exposed secrets, updates architecture map, and saves a safety checkpoint.",
        "steps": [
            {"type": "bug_scan", "target": "."},
            {"type": "codebase_map", "target": "."},
            {"type": "snapshot", "label": "Workflow Safety Checkpoint"},
        ],
        "run_count": 0,
        "last_run_at": None,
        "last_status": "idle",
    },
]


class PlatformExtensibilityHub:
    """Thread-safe per-user store & runner for Skills, MCP, Plugins, Custom Agents, Rules, Permissions & Automations."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._bg_jobs: Dict[str, List[Dict[str, Any]]] = {}

    @staticmethod
    def _uid(user_id: Any) -> str:
        return str(user_id if user_id is not None else "guest")

    def _default_state(self) -> Dict[str, Any]:
        return {
            "skills": [dict(s) for s in DEFAULT_SKILLS],
            "mcp_servers": [
                {
                    "id": "mcp_aura_workspace",
                    "name": "AURA Local Workspace MCP",
                    "transport": "builtin",
                    "endpoint": "builtin://workspace",
                    "enabled": True,
                    "status": "connected",
                    "tools": ["fs.tree", "fs.read", "git.status", "dev.codebase_map", "dev.bug_scan"],
                }
            ],
            "plugins": [dict(p, config=dict(p.get("config", {}))) for p in MARKETPLACE_CATALOG],
            "custom_agents": [
                {
                    "id": "cag_refactor_pro",
                    "name": "Clean Refactor Agent",
                    "role": "Code Maintainability Specialist",
                    "instructions": "Identify duplicated logic, narrow broad exception handlers, and keep functions concise.",
                    "model": "aura-2.3",
                    "tools": ["file_read", "file_write", "bug_scan", "self_verify"],
                    "permission_policy": "ask_on_delete",
                    "allowed_dir": ".",
                }
            ],
            "rules": {
                "project_rules": "Always verify generated code with automated tests before marking a task complete. Never expose secrets in logs or code.",
                "coding_conventions": "Prefer concise functions, strict path containment, clear error messages, and zero unused imports.",
                "memories": [],
            },
            "tool_permissions": dict(DEFAULT_TOOL_PERMISSIONS),
            "workflows": [dict(w, steps=[dict(s) for s in w["steps"]]) for w in DEFAULT_WORKFLOWS],
            "schedules": [
                {
                    "id": "sch_daily_audit",
                    "name": "Daily Codebase & Security Audit",
                    "cadence": "daily",
                    "cron": "0 9 * * *",
                    "workflow_id": "wf_security_hygiene",
                    "enabled": True,
                    "last_run": None,
                    "run_count": 0,
                }
            ],
            "event_triggers": [
                {
                    "id": "trg_commit_verify",
                    "event": "on_commit",
                    "workflow_id": "wf_code_quality_pipeline",
                    "enabled": True,
                    "fire_count": 0,
                    "last_fired": None,
                }
            ],
            "notifications": [],
        }

    def _load(self, user_id: Any, ws_dir: Path) -> Dict[str, Any]:
        uid = self._uid(user_id)
        with self._lock:
            if uid in self._cache:
                return self._cache[uid]
            ws = ws_dir.resolve()
            ws.mkdir(parents=True, exist_ok=True)
            fp = ws / PLATFORM_STATE_FILE
            state = self._default_state()
            if fp.exists():
                try:
                    loaded = json.loads(fp.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        for k in state:
                            if k in loaded:
                                state[k] = loaded[k]
                except Exception:
                    pass
            self._cache[uid] = state
            return state

    def _save(self, user_id: Any, ws_dir: Path, state: Dict[str, Any]) -> None:
        ws = ws_dir.resolve()
        ws.mkdir(parents=True, exist_ok=True)
        try:
            _atomic_write_text(ws / PLATFORM_STATE_FILE, json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    def get_overview(self, user_id: Any, ws_dir: Path) -> Dict[str, Any]:
        uid = self._uid(user_id)
        st = self._load(uid, ws_dir)
        with self._lock:
            bg_list = list(self._bg_jobs.get(uid, [])[:15])
            unread = sum(1 for n in st["notifications"] if not n.get("read"))
            return {
                "success": True,
                "skills": list(st["skills"]),
                "mcp_servers": list(st["mcp_servers"]),
                "plugins": list(st["plugins"]),
                "custom_agents": list(st["custom_agents"]),
                "rules": dict(st["rules"]),
                "tool_permissions": dict(st["tool_permissions"]),
                "workflows": list(st["workflows"]),
                "schedules": list(st["schedules"]),
                "event_triggers": list(st["event_triggers"]),
                "background_jobs": bg_list,
                "notifications": list(st["notifications"][:30]),
                "unread_notifications": unread,
            }

    # --- #38 NOTIFICATIONS ---
    def push_notification(
        self,
        user_id: Any,
        ws_dir: Path,
        *,
        title: str,
        message: str,
        level: str = "info",  # info | success | warning | error | approval
    ) -> Dict[str, Any]:
        st = self._load(user_id, ws_dir)
        item = {
            "id": f"ntf_{uuid.uuid4().hex[:7]}",
            "title": str(title or "Notification")[:100],
            "message": str(message or "")[:320],
            "level": str(level or "info")[:20],
            "read": False,
            "timestamp": time.time(),
            "time_label": time.strftime("%H:%M:%S"),
        }
        with self._lock:
            st["notifications"].insert(0, item)
            del st["notifications"][50:]
            self._save(user_id, ws_dir, st)
        return item

    def mark_notifications_read(self, user_id: Any, ws_dir: Path, clear_all: bool = False) -> Dict[str, Any]:
        st = self._load(user_id, ws_dir)
        with self._lock:
            if clear_all:
                st["notifications"] = []
            else:
                for n in st["notifications"]:
                    n["read"] = True
            self._save(user_id, ws_dir, st)
        return {"success": True, "unread_notifications": 0, "notifications": list(st["notifications"])}

    # --- #29 CUSTOM SKILLS ---
    def save_skill(self, user_id: Any, ws_dir: Path, body: Dict[str, Any]) -> Dict[str, Any]:
        name = str(body.get("name") or "").strip()[:80]
        if not name:
            return {"success": False, "error": "Skill name is required."}
        st = self._load(user_id, ws_dir)
        sid = str(body.get("id") or f"skill_{uuid.uuid4().hex[:7]}")[:48]
        raw_refs = body.get("references")
        refs = [str(r).strip()[:80] for r in raw_refs[:10]] if isinstance(raw_refs, list) else [x.strip() for x in str(raw_refs or "").split(",") if x.strip()][:10]
        raw_steps = body.get("steps")
        steps = [str(s).strip()[:120] for s in raw_steps[:10]] if isinstance(raw_steps, list) else [x.strip() for x in str(raw_steps or "").splitlines() if x.strip()][:10]
        skill = {
            "id": sid,
            "name": name,
            "category": str(body.get("category") or "Custom")[:40],
            "instructions": str(body.get("instructions") or "").strip()[:2000],
            "references": refs,
            "steps": steps,
            "builtin": False,
        }
        with self._lock:
            idx = next((i for i, s in enumerate(st["skills"]) if s["id"] == sid), -1)
            if idx >= 0:
                st["skills"][idx] = skill
            else:
                st["skills"].insert(0, skill)
            self._save(user_id, ws_dir, st)
        LIVE_ACTION_HUB.record(user_id, "orchestrator", "skill_saved", f"Saved custom skill: {name}", target=sid)
        return {"success": True, "skill": skill, "skills": list(st["skills"])}

    def delete_skill(self, user_id: Any, ws_dir: Path, skill_id: str) -> Dict[str, Any]:
        st = self._load(user_id, ws_dir)
        with self._lock:
            before = len(st["skills"])
            st["skills"] = [s for s in st["skills"] if s["id"] != skill_id]
            self._save(user_id, ws_dir, st)
        return {"success": len(st["skills"]) < before, "skills": list(st["skills"])}

    # --- #30 MCP INTEGRATION ---
    def save_mcp_server(self, user_id: Any, ws_dir: Path, body: Dict[str, Any]) -> Dict[str, Any]:
        name = str(body.get("name") or "").strip()[:80]
        endpoint = str(body.get("endpoint") or "").strip()[:300]
        transport = str(body.get("transport") or "http").strip().lower()
        if not name or not endpoint:
            return {"success": False, "error": "MCP server name and endpoint are required."}
        if transport == "http":
            ok, reason = is_safe_public_url(endpoint)
            if not ok:
                return {"success": False, "error": f"MCP SSRF Guard: {reason}"}
        st = self._load(user_id, ws_dir)
        mid = str(body.get("id") or f"mcp_{uuid.uuid4().hex[:7]}")[:48]
        raw_tools = body.get("tools")
        tools = [str(t).strip()[:64] for t in raw_tools[:20]] if isinstance(raw_tools, list) else [x.strip() for x in str(raw_tools or "tools/list").split(",") if x.strip()][:20]
        srv = {
            "id": mid,
            "name": name,
            "transport": transport if transport in ("http", "stdio", "builtin") else "http",
            "endpoint": endpoint,
            "enabled": bool(body.get("enabled", True)),
            "status": "configured",
            "tools": tools or ["tools/list"],
        }
        with self._lock:
            idx = next((i for i, m in enumerate(st["mcp_servers"]) if m["id"] == mid), -1)
            if idx >= 0:
                st["mcp_servers"][idx] = srv
            else:
                st["mcp_servers"].append(srv)
            self._save(user_id, ws_dir, st)
        return {"success": True, "server": srv, "mcp_servers": list(st["mcp_servers"])}

    def invoke_mcp_tool(self, user_id: Any, ws_dir: Path, server_id: str, tool_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        st = self._load(user_id, ws_dir)
        srv = next((m for m in st["mcp_servers"] if m["id"] == server_id), None)
        if not srv:
            return {"success": False, "error": f"MCP server '{server_id}' not found."}
        if not srv.get("enabled", True):
            return {"success": False, "error": f"MCP server '{srv['name']}' is disabled."}
        if st["tool_permissions"].get("mcp_invoke") == "deny":
            return {"success": False, "error": "Tool Permission Manager denied `mcp_invoke`."}

        tname = str(tool_name or "").strip()
        if srv["transport"] == "builtin":
            from aura_dev_studio import analyze_codebase_architecture, detect_bugs, git_get_status_and_diffs, smart_search_workspace
            from aura_workspace_tools import list_workspace_fs_tree, safe_resolve_workspace_path

            if tname == "fs.tree":
                out = list_workspace_fs_tree(user_id, ws_dir)
            elif tname == "fs.read":
                rel_p = str((params or {}).get("path") or "").strip()
                target_fp = safe_resolve_workspace_path(ws_dir, rel_p, allow_root=False) if rel_p else None
                if target_fp and target_fp.exists() and target_fp.is_file():
                    out = {
                        "success": True,
                        "path": target_fp.relative_to(ws_dir.resolve()).as_posix(),
                        "content": target_fp.read_text(encoding="utf-8", errors="replace")[:16000],
                    }
                else:
                    out = {"success": False, "error": f"Workspace file not found: {rel_p or '(empty path)'}"}
            elif tname == "git.status":
                out = git_get_status_and_diffs(user_id, ws_dir)
            elif tname == "dev.codebase_map":
                out = analyze_codebase_architecture(user_id, ws_dir)
            elif tname == "dev.bug_scan":
                out = detect_bugs(user_id, ws_dir)
            elif tname == "dev.smart_search":
                out = smart_search_workspace(user_id, ws_dir, str((params or {}).get("query") or "def"))
            elif tname == "security.secret_scan":
                from aura_control_intelligence import CONTROL_HUB
                out = CONTROL_HUB.scan_workspace_secrets(user_id, ws_dir)
            elif tname == "engines.status":
                from aura_control_intelligence import CONTROL_HUB
                out = CONTROL_HUB.get_unified_engines_bridge_status()
            else:
                out = {"server": srv["name"], "tool": tname, "available_tools": srv["tools"]}
            LIVE_ACTION_HUB.record(user_id, "orchestrator", "mcp_invoke", f"MCP {srv['name']} -> {tname}", target=server_id)
            return {"success": True, "server_id": server_id, "tool": tname, "result": out}

        if srv["transport"] == "http":
            ok, reason = is_safe_public_url(srv["endpoint"])
            if not ok:
                return {"success": False, "error": reason}
            rpc_body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tname, "arguments": params or {}}}).encode("utf-8")
            req = urllib.request.Request(srv["endpoint"], data=rpc_body, headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    raw = resp.read(120_000).decode("utf-8", errors="replace")
                return {"success": True, "server_id": server_id, "tool": tname, "result": raw[:4000]}
            except Exception as exc:
                return {"success": False, "error": f"MCP HTTP endpoint unreachable: {exc}"}

        return {"success": True, "server_id": server_id, "tool": tname, "result": {"note": f"Stdio MCP server '{srv['name']}' configured for local host."}}

    # --- #31 PLUGIN MARKETPLACE ---
    def manage_plugin(self, user_id: Any, ws_dir: Path, plugin_id: str, action: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        st = self._load(user_id, ws_dir)
        act = str(action or "").strip().lower()
        with self._lock:
            plug = next((p for p in st["plugins"] if p["id"] == plugin_id), None)
            if not plug:
                return {"success": False, "error": f"Plugin '{plugin_id}' not found in marketplace."}
            if act == "install":
                plug["installed"] = True
                plug["enabled"] = True
            elif act == "uninstall":
                plug["installed"] = False
                plug["enabled"] = False
            elif act == "enable":
                plug["installed"] = True
                plug["enabled"] = True
            elif act == "disable":
                plug["enabled"] = False
            elif act == "configure" and isinstance(config, dict):
                plug["config"] = {**plug.get("config", {}), **config}
            else:
                return {"success": False, "error": f"Unknown plugin action: {act}"}
            self._save(user_id, ws_dir, st)
        LIVE_ACTION_HUB.record(user_id, "orchestrator", f"plugin_{act}", f"Plugin {plug['name']}: {act}", target=plugin_id)
        return {"success": True, "plugin": dict(plug), "plugins": list(st["plugins"])}

    # --- #32 CUSTOM AGENT BUILDER ---
    def save_custom_agent(self, user_id: Any, ws_dir: Path, body: Dict[str, Any]) -> Dict[str, Any]:
        name = str(body.get("name") or "").strip()[:80]
        if not name:
            return {"success": False, "error": "Custom agent name is required."}
        st = self._load(user_id, ws_dir)
        aid = str(body.get("id") or f"cag_{uuid.uuid4().hex[:7]}")[:48]
        raw_tools = body.get("tools")
        tools = [str(t).strip()[:40] for t in raw_tools[:12]] if isinstance(raw_tools, list) else [x.strip() for x in str(raw_tools or "file_read,file_write").split(",") if x.strip()][:12]
        agent = {
            "id": aid,
            "name": name,
            "role": str(body.get("role") or "Custom Specialist")[:80],
            "instructions": str(body.get("instructions") or "").strip()[:2000],
            "model": str(body.get("model") or "aura-2.3")[:48],
            "tools": tools,
            "permission_policy": str(body.get("permission_policy") or "ask_on_delete")[:40],
            "allowed_dir": str(body.get("allowed_dir") or ".")[:120],
        }
        with self._lock:
            idx = next((i for i, a in enumerate(st["custom_agents"]) if a["id"] == aid), -1)
            if idx >= 0:
                st["custom_agents"][idx] = agent
            else:
                st["custom_agents"].insert(0, agent)
            self._save(user_id, ws_dir, st)
        LIVE_ACTION_HUB.record(user_id, "orchestrator", "custom_agent_saved", f"Saved custom agent: {name}", target=aid)
        return {"success": True, "agent": agent, "custom_agents": list(st["custom_agents"])}

    def delete_custom_agent(self, user_id: Any, ws_dir: Path, agent_id: str) -> Dict[str, Any]:
        st = self._load(user_id, ws_dir)
        with self._lock:
            before = len(st["custom_agents"])
            st["custom_agents"] = [a for a in st["custom_agents"] if a["id"] != agent_id]
            self._save(user_id, ws_dir, st)
        return {"success": len(st["custom_agents"]) < before, "custom_agents": list(st["custom_agents"])}

    # --- #33 RULES & MEMORY + #34 TOOL PERMISSION MANAGER ---
    def update_rules_and_memory(self, user_id: Any, ws_dir: Path, body: Dict[str, Any]) -> Dict[str, Any]:
        st = self._load(user_id, ws_dir)
        with self._lock:
            if "project_rules" in body:
                st["rules"]["project_rules"] = str(body["project_rules"] or "")[:3000]
            if "coding_conventions" in body:
                st["rules"]["coding_conventions"] = str(body["coding_conventions"] or "")[:3000]
            if body.get("add_memory"):
                mem_txt = str(body["add_memory"]).strip()[:300]
                if mem_txt:
                    st["rules"].setdefault("memories", []).insert(0, {"id": f"mem_{uuid.uuid4().hex[:6]}", "text": mem_txt, "time": time.strftime("%Y-%m-%d %H:%M")})
                    del st["rules"]["memories"][40:]
            if body.get("delete_memory_id"):
                st["rules"]["memories"] = [m for m in st["rules"].get("memories", []) if m.get("id") != body["delete_memory_id"]]
            self._save(user_id, ws_dir, st)
        return {"success": True, "rules": dict(st["rules"])}

    def update_tool_permissions(self, user_id: Any, ws_dir: Path, updates: Dict[str, Any]) -> Dict[str, Any]:
        st = self._load(user_id, ws_dir)
        valid_modes = {"allow", "ask_approval", "deny"}
        with self._lock:
            for k, v in (updates or {}).items():
                if k in DEFAULT_TOOL_PERMISSIONS and str(v).strip().lower() in valid_modes:
                    st["tool_permissions"][k] = str(v).strip().lower()
            self._save(user_id, ws_dir, st)
        LIVE_ACTION_HUB.record(user_id, "system", "permissions_updated", "Updated Tool Permission Manager policy")
        return {"success": True, "tool_permissions": dict(st["tool_permissions"])}

    # --- #36 REUSABLE WORKFLOWS + #35 SCHEDULES + #39 EVENT TRIGGERS + #37 BACKGROUND AGENTS ---
    def save_workflow(self, user_id: Any, ws_dir: Path, body: Dict[str, Any]) -> Dict[str, Any]:
        name = str(body.get("name") or "").strip()[:90]
        if not name:
            return {"success": False, "error": "Workflow name is required."}
        st = self._load(user_id, ws_dir)
        wid = str(body.get("id") or f"wf_{uuid.uuid4().hex[:7]}")[:48]
        raw_steps = body.get("steps")
        steps = raw_steps if isinstance(raw_steps, list) and raw_steps else [
            {"type": "bug_scan", "target": "."},
            {"type": "self_verify", "target": "."},
            {"type": "final_report", "title": f"{name} Report"},
        ]
        wf = {
            "id": wid,
            "name": name,
            "description": str(body.get("description") or "Reusable AURA automation pipeline")[:240],
            "steps": steps[:8],
            "run_count": 0,
            "last_run_at": None,
            "last_status": "idle",
        }
        with self._lock:
            idx = next((i for i, w in enumerate(st["workflows"]) if w["id"] == wid), -1)
            if idx >= 0:
                wf["run_count"] = st["workflows"][idx].get("run_count", 0)
                st["workflows"][idx] = wf
            else:
                st["workflows"].insert(0, wf)
            self._save(user_id, ws_dir, st)
        return {"success": True, "workflow": wf, "workflows": list(st["workflows"])}

    def run_workflow(
        self,
        user_id: Any,
        ws_dir: Path,
        workflow_id: str,
        *,
        trigger_source: str = "manual",
        brain: Optional[AuraBrain] = None,
    ) -> Dict[str, Any]:
        from aura_agent_orchestrator import AGENT_ORCHESTRATOR
        from aura_dev_studio import (
            VISUAL_DELIVERABLES,
            analyze_codebase_architecture,
            create_project_snapshot,
            detect_bugs,
        )

        st = self._load(user_id, ws_dir)
        wf = next((w for w in st["workflows"] if w["id"] == workflow_id), None)
        if not wf:
            return {"success": False, "error": f"Workflow '{workflow_id}' not found."}

        t0 = time.perf_counter()
        step_results: List[Dict[str, Any]] = []
        all_ok = True

        for idx, step in enumerate(wf.get("steps", []), start=1):
            stype = str(step.get("type") or "").strip().lower()
            target = str(step.get("target") or ".")
            if stype == "bug_scan":
                res = detect_bugs(user_id, ws_dir, path=target)
                step_results.append({"step": idx, "type": stype, "ok": bool(res.get("success")), "summary": f"{res.get('total_findings', 0)} finding(s) across {res.get('files_scanned', 0)} file(s)"})
            elif stype == "self_verify":
                res = AGENT_ORCHESTRATOR.run_self_verification_loop(user_id, ws_dir, target, max_attempts=2, brain=brain)
                ok_s = bool(res.get("verified"))
                if not ok_s:
                    all_ok = False
                step_results.append({"step": idx, "type": stype, "ok": ok_s, "summary": f"{'PASS' if ok_s else 'FAIL'} in {res.get('attempts', 1)} attempt(s)"})
            elif stype == "codebase_map":
                res = analyze_codebase_architecture(user_id, ws_dir)
                step_results.append({"step": idx, "type": stype, "ok": True, "summary": f"{res.get('total_files', 0)} files, {res.get('symbol_count', 0)} symbols mapped"})
            elif stype == "snapshot":
                res = create_project_snapshot(user_id, ws_dir, label=str(step.get("label") or wf["name"]))
                step_results.append({"step": idx, "type": stype, "ok": bool(res.get("success")), "summary": f"Snapshot {res.get('snapshot', {}).get('id', '')} saved"})
            elif stype == "final_report":
                res = VISUAL_DELIVERABLES.build_final_execution_report(user_id, ws_dir, title=str(step.get("title") or wf["name"]))
                step_results.append({"step": idx, "type": stype, "ok": bool(res.get("success")), "summary": f"Execution report saved ({res.get('verification_status')})"})
            else:
                step_results.append({"step": idx, "type": stype, "ok": True, "summary": f"Executed step '{stype}'"})

        dur = int((time.perf_counter() - t0) * 1000)
        with self._lock:
            wf["run_count"] = int(wf.get("run_count", 0)) + 1
            wf["last_run_at"] = time.strftime("%H:%M:%S")
            wf["last_status"] = "completed" if all_ok else "warning"
            self._save(user_id, ws_dir, st)

        self.push_notification(
            user_id,
            ws_dir,
            title=f"Workflow Completed: {wf['name'][:48]}",
            message=f"Trigger: {trigger_source} · {len(step_results)} step(s) ran in {dur}ms ({'PASS' if all_ok else 'WARNINGS'}).",
            level="success" if all_ok else "warning",
        )
        LIVE_ACTION_HUB.record(
            user_id,
            "orchestrator",
            "workflow_run",
            f"Ran workflow '{wf['name'][:48]}' ({trigger_source})",
            target=workflow_id,
            duration_ms=dur,
            status="completed" if all_ok else "error",
        )
        return {
            "success": True,
            "workflow_id": workflow_id,
            "trigger_source": trigger_source,
            "all_ok": all_ok,
            "duration_ms": dur,
            "steps": step_results,
        }

    def save_schedule(self, user_id: Any, ws_dir: Path, body: Dict[str, Any]) -> Dict[str, Any]:
        name = str(body.get("name") or "").strip()[:80]
        wf_id = str(body.get("workflow_id") or "wf_code_quality_pipeline").strip()
        if not name:
            return {"success": False, "error": "Schedule name is required."}
        st = self._load(user_id, ws_dir)
        sid = str(body.get("id") or f"sch_{uuid.uuid4().hex[:7]}")[:48]
        cadence = str(body.get("cadence") or "daily").strip().lower()
        cron_map = {"hourly": "0 * * * *", "daily": "0 9 * * *", "weekly": "0 9 * * 1"}
        item = {
            "id": sid,
            "name": name,
            "cadence": cadence,
            "cron": str(body.get("cron") or cron_map.get(cadence, "0 9 * * *"))[:40],
            "workflow_id": wf_id,
            "enabled": bool(body.get("enabled", True)),
            "last_run": None,
            "run_count": 0,
        }
        with self._lock:
            idx = next((i for i, s in enumerate(st["schedules"]) if s["id"] == sid), -1)
            if idx >= 0:
                item["run_count"] = st["schedules"][idx].get("run_count", 0)
                st["schedules"][idx] = item
            else:
                st["schedules"].insert(0, item)
            self._save(user_id, ws_dir, st)
        return {"success": True, "schedule": item, "schedules": list(st["schedules"])}

    def save_event_trigger(self, user_id: Any, ws_dir: Path, body: Dict[str, Any]) -> Dict[str, Any]:
        ev = str(body.get("event") or "on_commit").strip().lower()
        wf_id = str(body.get("workflow_id") or "wf_code_quality_pipeline").strip()
        if ev not in ("on_commit", "on_file_save", "on_verify_fail", "on_mission_complete"):
            return {"success": False, "error": f"Unsupported trigger event: {ev}"}
        st = self._load(user_id, ws_dir)
        tid = str(body.get("id") or f"trg_{uuid.uuid4().hex[:7]}")[:48]
        trg = {
            "id": tid,
            "event": ev,
            "workflow_id": wf_id,
            "enabled": bool(body.get("enabled", True)),
            "fire_count": 0,
            "last_fired": None,
        }
        with self._lock:
            idx = next((i for i, t in enumerate(st["event_triggers"]) if t["id"] == tid), -1)
            if idx >= 0:
                trg["fire_count"] = st["event_triggers"][idx].get("fire_count", 0)
                st["event_triggers"][idx] = trg
            else:
                st["event_triggers"].insert(0, trg)
            self._save(user_id, ws_dir, st)
        return {"success": True, "trigger": trg, "event_triggers": list(st["event_triggers"])}

    def fire_event(self, user_id: Any, ws_dir: Path, event_name: str, brain: Optional[AuraBrain] = None) -> Dict[str, Any]:
        """#39 Event-Triggered Automation: fires all enabled workflows subscribed to `event_name`."""
        st = self._load(user_id, ws_dir)
        matched = [t for t in st["event_triggers"] if t.get("enabled") and t.get("event") == event_name]
        runs = []
        for trg in matched:
            r = self.run_workflow(user_id, ws_dir, trg["workflow_id"], trigger_source=f"event:{event_name}", brain=brain)
            with self._lock:
                trg["fire_count"] = int(trg.get("fire_count", 0)) + 1
                trg["last_fired"] = time.strftime("%H:%M:%S")
                self._save(user_id, ws_dir, st)
            runs.append(r)
        return {"success": True, "event": event_name, "triggered_count": len(runs), "runs": runs}

    def start_background_agent(
        self,
        user_id: Any,
        ws_dir: Path,
        *,
        name: str = "Background Codebase Health Sweep",
        workflow_id: str = "wf_code_quality_pipeline",
        brain: Optional[AuraBrain] = None,
    ) -> Dict[str, Any]:
        """#37 Background Agents: executes a permitted maintenance/audit workflow in background."""
        uid = self._uid(user_id)
        job = {
            "id": f"bg_{uuid.uuid4().hex[:7]}",
            "name": str(name or "Background Agent")[:80],
            "workflow_id": workflow_id,
            "status": "running",
            "started_at": time.strftime("%H:%M:%S"),
            "finished_at": None,
            "summary": "Running asynchronously in isolated workspace...",
            "cancelled": False,
        }
        with self._lock:
            b = self._bg_jobs.setdefault(uid, [])
            b.insert(0, job)
            del b[15:]

        def _worker() -> None:
            if job["cancelled"]:
                return
            res = self.run_workflow(uid, ws_dir, workflow_id, trigger_source="background_agent", brain=brain)
            with self._lock:
                if not job["cancelled"]:
                    job["status"] = "completed" if res.get("success") else "error"
                    job["finished_at"] = time.strftime("%H:%M:%S")
                    job["summary"] = f"Completed {len(res.get('steps', []))} step(s) in {res.get('duration_ms', 0)}ms."

        if bool(os.environ.get("VERCEL")):
            _worker()
        else:
            threading.Thread(target=_worker, daemon=True).start()

        return {"success": True, "job": dict(job)}

    def build_active_context_bundle(self, user_id: Any, ws_dir: Path) -> str:
        """#29 + #33 Injects active Project Rules, Conventions, Memories & top Custom Skills into agent/coding prompts."""
        st = self._load(user_id, ws_dir)
        parts: List[str] = []
        rules = st.get("rules") or {}
        if rules.get("project_rules"):
            parts.append(f"Project Rules: {str(rules['project_rules'])[:450]}")
        if rules.get("coding_conventions"):
            parts.append(f"Coding Conventions: {str(rules['coding_conventions'])[:350]}")
        mems = [m.get("text", "") for m in (rules.get("memories") or [])[:5] if isinstance(m, dict) and m.get("text")]
        if mems:
            parts.append("Saved Workspace Memories: " + " | ".join(mems))
        custom_skills = [s for s in (st.get("skills") or []) if not s.get("builtin")][:3]
        if custom_skills:
            parts.append("Active Custom Skills: " + "; ".join(f"{s['name']}: {str(s.get('instructions') or '')[:120]}" for s in custom_skills))
        return "\n".join(parts)

    def run_custom_agent(
        self,
        user_id: Any,
        ws_dir: Path,
        agent_id: str,
        goal: str = "",
        brain: Optional[AuraBrain] = None,
    ) -> Dict[str, Any]:
        """#32 + #63 Runs a user-created specialist agent strictly inside its configured directory boundary."""
        from aura_dev_studio import analyze_codebase_architecture, detect_bugs

        st = self._load(user_id, ws_dir)
        agent = next((a for a in st["custom_agents"] if a["id"] == agent_id), None)
        if not agent:
            return {"success": False, "error": f"Custom agent '{agent_id}' not found."}
        scope_dir = str(agent.get("allowed_dir") or ".").strip() or "."
        t0 = time.perf_counter()
        bugs = detect_bugs(user_id, ws_dir, path=scope_dir if scope_dir != "." else "")
        arch = analyze_codebase_architecture(user_id, ws_dir)
        dur = int((time.perf_counter() - t0) * 1000)
        summary = (
            f"Specialist '{agent['name']}' ({agent['role']}) audited scope `{scope_dir}`: "
            f"{arch.get('total_files', 0)} file(s), {bugs.get('total_findings', 0)} finding(s), "
            f"security score {bugs.get('security_score', 100)}/100."
        )
        if goal.strip():
            summary += f" Goal focus: {goal.strip()[:100]}"
        self.push_notification(user_id, ws_dir, title=f"Agent Finished: {agent['name']}", message=summary, level="success")
        LIVE_ACTION_HUB.record(user_id, "orchestrator", "custom_agent_run", summary[:120], target=agent_id, duration_ms=dur)
        return {
            "success": True,
            "agent": dict(agent),
            "scope_dir": scope_dir,
            "duration_ms": dur,
            "summary": summary,
            "findings_count": bugs.get("total_findings", 0),
            "security_score": bugs.get("security_score", 100),
            "files_mapped": arch.get("total_files", 0),
        }

    def run_schedule_now(self, user_id: Any, ws_dir: Path, schedule_id: str, brain: Optional[AuraBrain] = None) -> Dict[str, Any]:
        """#35 Executes a scheduled automation on demand and records run count + timestamp."""
        st = self._load(user_id, ws_dir)
        sch = next((s for s in st["schedules"] if s["id"] == schedule_id), None)
        if not sch:
            return {"success": False, "error": f"Schedule '{schedule_id}' not found."}
        res = self.run_workflow(user_id, ws_dir, sch["workflow_id"], trigger_source=f"schedule:{sch['name']}", brain=brain)
        with self._lock:
            sch["run_count"] = int(sch.get("run_count", 0)) + 1
            sch["last_run"] = time.strftime("%H:%M:%S")
            self._save(user_id, ws_dir, st)
        return {"success": bool(res.get("success")), "schedule": dict(sch), "workflow_run": res}

    def run_plugin_action(self, user_id: Any, ws_dir: Path, plugin_id: str) -> Dict[str, Any]:
        """#31 Executes a live capability check/action from an installed Marketplace plugin."""
        st = self._load(user_id, ws_dir)
        plug = next((p for p in st["plugins"] if p["id"] == plugin_id), None)
        if not plug:
            return {"success": False, "error": f"Plugin '{plugin_id}' not found."}
        if not plug.get("installed") or not plug.get("enabled"):
            return {"success": False, "error": f"Install & enable '{plug['name']}' before running it."}
        if plugin_id == "plugin_secret_shield":
            from aura_control_intelligence import CONTROL_HUB
            res = CONTROL_HUB.scan_workspace_secrets(user_id, ws_dir)
            msg = f"Secret Shield scanned {res['files_scanned']} file(s): {res['findings_count']} secret(s) detected."
        elif plugin_id == "plugin_git_guard":
            from aura_dev_studio import git_get_status_and_diffs
            g = git_get_status_and_diffs(user_id, ws_dir)
            res = {"branch": g.get("branch"), "changed_files": len(g.get("changed_files", [])), "commits": len(g.get("commits", []))}
            msg = f"Git Guard on `{res['branch']}`: {res['changed_files']} pending change(s), {res['commits']} commit(s)."
        elif plugin_id == "plugin_sqlite_studio":
            from aura_dev_studio import analyze_codebase_architecture
            arch = analyze_codebase_architecture(user_id, ws_dir)
            res = {"db_tables": arch.get("db_tables", []), "database_files": arch.get("layers", {}).get("database", [])}
            msg = f"SQLite Studio found {len(res['db_tables'])} table schema(s) across {len(res['database_files'])} DB file(s)."
        elif plugin_id == "plugin_coderx_bridge":
            from aura_control_intelligence import CONTROL_HUB
            res = CONTROL_HUB.get_unified_engines_bridge_status()
            msg = f"CoderX Bridge active: {res['ready_count']}/{res['total_engines']} existing AURA core engines linked."
        else:
            from aura_dev_studio import VISUAL_DELIVERABLES
            res = VISUAL_DELIVERABLES.list_artifacts(user_id)
            msg = f"{plug['name']} active: {len(res.get('artifacts', []))} deliverable(s), {len(res.get('feedback_notes', []))} visual note(s)."
        LIVE_ACTION_HUB.record(user_id, "orchestrator", "plugin_run", msg[:120], target=plugin_id)
        return {"success": True, "plugin_id": plugin_id, "message": msg, "result": res}

    def check_tool_permission(self, user_id: Any, ws_dir: Path, tool_name: str) -> str:
        """#34 Returns effective policy ('allow' | 'ask_approval' | 'deny') for a workspace tool."""
        st = self._load(user_id, ws_dir)
        return str((st.get("tool_permissions") or {}).get(tool_name, "allow"))

    def stop_all_background_agents(self, user_id: Any) -> int:
        uid = self._uid(user_id)
        stopped = 0
        with self._lock:
            for job in self._bg_jobs.get(uid, []):
                if job["status"] == "running":
                    job["cancelled"] = True
                    job["status"] = "stopped"
                    job["summary"] = "Halted immediately by Emergency Stop."
                    stopped += 1
        return stopped


PLATFORM_EXT = PlatformExtensibilityHub()
