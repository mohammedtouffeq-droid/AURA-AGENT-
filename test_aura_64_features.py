"""
===================================================================================
      AURA 64-FEATURE PLATFORM VERIFICATION SUITE (PARTS 1, 2, 3 & 4)
===================================================================================
End-to-end functional, security, and tenant-isolation verification covering:
- Part 1: Pro Coding (#13-#21), Git Visual Review/Worktrees/Branches/PR/Snapshots (#23-#28), Deliverables (#40-#45)
- Part 2: Custom Skills, MCP, Plugins, Custom Agents, Rules, Tool Perms (#29-#34) & Workflows/Schedules/Events/BG/Notifs (#35-#39)
- Part 3: Remote Control (#12), Advanced Intelligence (#46-#55), Security/Approvals/Secrets/Audit/E-Stop/Resources/Recovery (#56-#64)
- Part 4: 5-Center UI Architecture + Multi-Tab Workspace (#11) + Home Screen Purity
===================================================================================
"""

from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest

import aura_web

ROOT = Path(__file__).resolve().parent
_SEQ = [0]


def _http(
    base_url: str,
    path: str,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(f"{base_url}{path}", data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"raw": raw}
        return exc.code, body


@pytest.fixture(scope="module")
def srv_url():
    srv = aura_web.make_server("127.0.0.1", 0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()
    srv.server_close()


def _user(base_url: str) -> Dict[str, str]:
    _SEQ[0] += 1
    uname = f"p64_u{_SEQ[0]}_{threading.get_ident()}"
    c, d = _http(base_url, "/api/auth/register", "POST", {"username": uname, "password": "SafePassword!2026"})
    assert c == 200 and d.get("success")
    return {"Authorization": f"Bearer {d['token']}", "X-CSRF-Token": d.get("csrf_token", "")}


def test_part1_pro_coding_intelligence_and_codebase_map(srv_url):
    h = _user(srv_url)

    # Seed multi-layer workspace files (Frontend + Backend + DB)
    sample_py = (
        "def risky(items=[]):\n"
        "    try:\n"
        "        return eval('1+1')\n"
        "    except:\n"
        "        return 0\n"
    )
    assert _http(srv_url, "/api/workspace/fs/create", "POST", {"path": "backend/auth.py", "content": sample_py}, h)[0] == 200
    assert _http(srv_url, "/api/workspace/fs/create", "POST", {"path": "frontend/login.html", "content": "<h1>Login</h1>"}, h)[0] == 200
    assert _http(srv_url, "/api/workspace/fs/create", "POST", {"path": "database/users.sql", "content": "CREATE TABLE users (id INT);"}, h)[0] == 200

    # #13 Autocomplete
    c, ac = _http(srv_url, "/api/dev/autocomplete", "POST", {"path": "backend/auth.py", "prefix": "def verify_token(tok):\n"}, h)
    assert c == 200 and len(ac["suggestion"]) > 5

    # #14 Inline AI Edit
    c, ie = _http(srv_url, "/api/dev/inline_edit", "POST", {"path": "backend/auth.py", "selected_code": "def risky(items=[]):", "instruction": "Add docstring", "apply": False}, h)
    assert c == 200 and ie["diff"]

    # #15 Code Explanation
    c, ex = _http(srv_url, "/api/dev/explain", "POST", {"path": "backend/auth.py"}, h)
    assert c == 200 and "risky" in ex["explanation"]

    # #16 Bug Detection (catches mutable default, bare except, eval!)
    c, bugs = _http(srv_url, "/api/dev/bugs", "POST", {"path": "backend/auth.py"}, h)
    assert c == 200 and bugs["total_findings"] >= 3
    cats = {f["category"] for f in bugs["findings"]}
    assert "BareExcept" in cats and "MutableDefaultArg" in cats and "CodeInjectionRisk" in cats

    # #17 Refactoring (fixes bare except)
    c, ref = _http(srv_url, "/api/dev/refactor", "POST", {"path": "backend/auth.py", "apply": True}, h)
    assert c == 200 and ref["changed"] is True

    # #18 Multi-File Editing with automatic snapshot
    c, mf = _http(
        srv_url,
        "/api/dev/multifile_edit",
        "POST",
        {
            "label": "Update login stack",
            "edits": [
                {"path": "backend/service.py", "content": "def greet(name):\n    return f'Hello {name}'\n"},
                {"path": "frontend/login.html", "content": "<h1>AURA Login v2</h1>\n"},
            ],
        },
        h,
    )
    assert c == 200 and mf["files_count"] == 2 and mf["snapshot_id"]

    # #19 Codebase Architecture Map + #20 Smart Search
    c, cmap = _http(srv_url, "/api/dev/codebase_map", headers=h)
    assert c == 200 and len(cmap["layers"]["frontend"]) >= 1 and len(cmap["layers"]["backend"]) >= 1 and len(cmap["layers"]["database"]) >= 1

    c, ss = _http(srv_url, "/api/dev/smart_search", "POST", {"query": "greet"}, h)
    assert c == 200 and any(s["name"] == "greet" for s in ss["symbols"])

    # #21 Test Generation
    c, tg = _http(srv_url, "/api/dev/generate_tests", "POST", {"path": "backend/service.py", "save": True}, h)
    assert c == 200 and tg["saved"] is True and tg["test_path"].endswith("test_service.py")


def test_part1_git_visual_review_worktrees_branches_pr_snapshots_and_deliverables(srv_url):
    h = _user(srv_url)
    assert _http(srv_url, "/api/workspace/fs/create", "POST", {"path": "app.py", "content": "VERSION = 1\n"}, h)[0] == 200

    # #23 Git Status & Visual Diff Review
    c, st = _http(srv_url, "/api/git/status", headers=h)
    assert c == 200 and st["success"] is True
    if st.get("git_available"):
        assert any(f["path"] == "app.py" for f in st["changed_files"])
        # Approve / Stage file
        c, rv = _http(srv_url, "/api/git/review", "POST", {"path": "app.py", "decision": "approve"}, h)
        assert c == 200

        # #26 Push without explicit approval blocked
        c_blk, d_blk = _http(srv_url, "/api/git/commit", "POST", {"message": "Initial app", "push": True, "push_approved": False}, h)
        assert c_blk == 400 and d_blk.get("approval_required") is True

        # #26 Commit cleanly (also triggers on_commit event!)
        c, cm = _http(srv_url, "/api/git/commit", "POST", {"message": "Add app.py v1", "push": False}, h)
        assert c == 200 and cm["success"] is True and cm["event_triggers_fired"] >= 1

        # #25 Branch Management
        c, br = _http(srv_url, "/api/git/branch", "POST", {"action": "create", "branch": "feat/auth"}, h)
        assert c == 200 and br["git"]["branch"] == "feat/auth"

        # #24 Git Worktree Isolation
        c, wt = _http(srv_url, "/api/git/worktree", "POST", {"action": "create", "name": "agent_fe"}, h)
        assert c == 200 and len(wt["worktrees"]) >= 2
        c, wtr = _http(srv_url, "/api/git/worktree", "POST", {"action": "remove", "name": "agent_fe"}, h)
        assert c == 200

        # #27 Pull Request Assistant
        c, pr = _http(srv_url, "/api/git/pr", "POST", {"title": "Improve Auth"}, h)
        assert c == 200 and "## PR: Improve Auth" in pr["pr_markdown"]

    # #28 Project Snapshots & Rollback (works with or without git)
    c, snap = _http(srv_url, "/api/snapshots/create", "POST", {"label": "v1_good"}, h)
    assert c == 200
    snap_id = snap["snapshot"]["id"]
    _http(srv_url, "/api/workspace/fs/create", "POST", {"path": "app.py", "content": "VERSION = 999_BROKEN\n"}, h)
    c, rb = _http(srv_url, "/api/snapshots/rollback", "POST", {"snapshot_id": snap_id}, h)
    assert c == 200 and rb["restored_count"] >= 1
    _, f_after = _http(srv_url, "/api/workspace/file?path=app.py", headers=h)
    assert "VERSION = 1" in f_after["content"]

    # #40, #42, #43, #45 Deliverables, Browser Recording, Visual Feedback & Final Report
    assert _http(srv_url, "/api/browser/record", "POST", {"command": "start"}, h)[0] == 200
    assert _http(srv_url, "/api/browser/record", "POST", {"command": "stop"}, h)[0] == 200
    assert _http(srv_url, "/api/browser/feedback", "POST", {"url": "https://example.com", "note": "Align header cleanly"}, h)[0] == 200
    c, rep = _http(srv_url, "/api/deliverables/report", "POST", {"title": "Release Report"}, h)
    assert c == 200 and "# Release Report" in rep["report_markdown"]


def test_part2_extensibility_mcp_plugins_agents_and_workflow_automation(srv_url):
    h = _user(srv_url)

    # #29 Custom Skills
    c, sk = _http(srv_url, "/api/platform/skills/save", "POST", {"name": "Go Microservices", "instructions": "Use context.Context everywhere"}, h)
    assert c == 200 and sk["skill"]["name"] == "Go Microservices"

    # #30 MCP SSRF guard + builtin tool invoke
    c_ssrf, _ = _http(srv_url, "/api/platform/mcp/save", "POST", {"name": "EvilLocal", "endpoint": "http://127.0.0.1:9000", "transport": "http"}, h)
    assert c_ssrf == 400
    c, mcp_out = _http(srv_url, "/api/platform/mcp/invoke", "POST", {"server_id": "mcp_aura_workspace", "tool": "fs.tree"}, h)
    assert c == 200 and mcp_out["result"]["success"] is True

    # #31 Plugin Marketplace
    c, pl = _http(srv_url, "/api/platform/plugins/manage", "POST", {"plugin_id": "plugin_sqlite_studio", "action": "install"}, h)
    assert c == 200 and pl["plugin"]["installed"] is True and pl["plugin"]["enabled"] is True

    # #32 Custom Agent Builder
    c, ag = _http(srv_url, "/api/platform/agents/save", "POST", {"name": "Perf Auditor", "role": "Latency Specialist", "model": "aura-2.6"}, h)
    assert c == 200 and ag["agent"]["name"] == "Perf Auditor"

    # #33 Rules & Memory + #34 Tool Permissions
    c, rl = _http(srv_url, "/api/platform/rules", "POST", {"project_rules": "Zero mocks in prod", "add_memory": "Prefer SQLite WAL mode"}, h)
    assert c == 200 and len(rl["rules"]["memories"]) == 1
    c, pm = _http(srv_url, "/api/platform/permissions", "POST", {"permissions": {"file_delete": "deny"}}, h)
    assert c == 200 and pm["tool_permissions"]["file_delete"] == "deny"

    # #35 Schedules, #36 Reusable Workflows, #37 Background Agents, #38 Notifications, #39 Event Triggers
    assert _http(srv_url, "/api/platform/schedules/save", "POST", {"name": "Weekly Audit", "cadence": "weekly", "workflow_id": "wf_security_hygiene"}, h)[0] == 200
    c, wf = _http(srv_url, "/api/platform/workflows/run", "POST", {"workflow_id": "wf_code_quality_pipeline"}, h)
    assert c == 200 and len(wf["steps"]) == 3
    c, bg = _http(srv_url, "/api/platform/background/start", "POST", {"name": "Nightly Sweep"}, h)
    assert c == 200 and bg["job"]["id"].startswith("bg_")
    c, ov = _http(srv_url, "/api/platform/overview", headers=h)
    assert c == 200 and ov["unread_notifications"] >= 1
    assert _http(srv_url, "/api/platform/notifications/read", "POST", {"clear_all": False}, h)[0] == 200


def test_part3_remote_control_intelligence_security_and_emergency_stop(srv_url):
    h = _user(srv_url)
    h_other = _user(srv_url)

    # #46, #48, #50-#55 Routing, Cost, Handoff, Projects, Evaluation
    assert _http(srv_url, "/api/control/routing", "POST", {"deep_reasoning": True, "execution_mode": "worktree"}, h)[0] == 200
    assert _http(srv_url, "/api/control/cost/log", "POST", {"task": "Auth Refactor", "input_tokens": 1200, "output_tokens": 600}, h)[0] == 200
    assert _http(srv_url, "/api/control/handoff", "POST", {"from_agent": "frontend", "to_agent": "backend", "summary": "API contract ready"}, h)[0] == 200
    assert _http(srv_url, "/api/control/projects", "POST", {"action": "create", "name": "Lyceum Portal"}, h)[0] == 200
    c, ev = _http(srv_url, "/api/control/evaluate", headers=h)
    assert c == 200 and 0 <= ev["overall_score"] <= 100

    # #58 Secret Protection (scanner + redactor)
    fake_secret = "AIzaSyD" + "A" * 32
    _http(srv_url, "/api/workspace/fs/create", "POST", {"path": "leak_test.py", "content": f"KEY = '{fake_secret}'\n"}, h)
    c, sc = _http(srv_url, "/api/control/secrets/scan", "POST", {}, h)
    assert c == 200 and sc["findings_count"] >= 1
    assert fake_secret not in sc["findings"][0]["masked_excerpt"]
    c, rd = _http(srv_url, "/api/control/secrets/redact", "POST", {"text": f"token={fake_secret}"}, h)
    assert c == 200 and "[REDACTED:" in rd["redacted"]

    # #56, #64 Centralized Human Approval Queue + #12 Remote Agent Control!
    c, ap_req = _http(srv_url, "/api/control/approvals/request", "POST", {"action_type": "git_push", "target": "origin/main", "reason": "Push release"}, h)
    assert c == 200
    apr_id = ap_req["approval"]["id"]

    # Unauthenticated remote endpoint rejected
    assert _http(srv_url, "/api/remote/status")[0] == 401

    # Pair remote device -> query status -> approve remotely!
    c, pair = _http(srv_url, "/api/control/remote/pair", "POST", {"label": "My Phone"}, h)
    assert c == 200
    rem_tok = pair["pairing"]["token"]
    c, rem_st = _http(srv_url, "/api/remote/status", headers={"X-Remote-Token": rem_tok})
    assert c == 200 and rem_st["remote_authorized"] is True and rem_st["control"]["pending_approvals"] == 1
    c, rem_ok = _http(srv_url, "/api/remote/action", "POST", {"action": "approve", "approval_id": apr_id}, headers={"X-Remote-Token": rem_tok})
    assert c == 200 and rem_ok["approval"]["status"] == "approved"

    # Revoke remote token -> immediately fails with 401
    assert _http(srv_url, "/api/control/remote/revoke", "POST", {}, h)[0] == 200
    assert _http(srv_url, "/api/remote/status", headers={"X-Remote-Token": rem_tok})[0] == 401

    # #62 Crash Recovery Checkpoint & Restore + #63 Agent Boundaries
    assert _http(srv_url, "/api/control/recovery/save", "POST", {"label": "Pre-release"}, h)[0] == 200
    c, rest = _http(srv_url, "/api/control/recovery/restore", "POST", {}, h)
    assert c == 200 and rest["restored"]["label"] == "Pre-release"
    assert _http(srv_url, "/api/control/boundaries/update", "POST", {"agent_id": "frontend", "allowed_dir": "frontend", "allowed_tools": ["file_read"]}, h)[0] == 200

    # #60 Emergency Stop + #59 Audit Logs + #61 Resource Monitoring + Tenant Isolation
    c, es = _http(srv_url, "/api/control/emergency_stop", "POST", {"reason": "Test E-Stop"}, h)
    assert c == 200 and es["halted"] is True and es["jarvis_halted"] is True
    c, ov = _http(srv_url, "/api/control/overview", headers=h)
    assert c == 200 and len(ov["audit_logs"]) >= 4 and "active_threads" in ov["resources"]

    # Other user sees ZERO audit logs / approvals / projects from User 1
    _, ov_other = _http(srv_url, "/api/control/overview", headers=h_other)
    assert len(ov_other["audit_logs"]) == 0 and len(ov_other["approval_queue"]) == 0


def test_part4_five_center_ui_and_home_screen_sacred():
    html_text = (ROOT / "index.html").read_text(encoding="utf-8")
    sw_text = (ROOT / "sw.js").read_text(encoding="utf-8")
    assert "aura-core-shell-v1" in sw_text

    for el_id in (
        "awTabBtn_agents",
        "awCenterBtn_computer",
        "awCenterBtn_studio",
        "awCenterBtn_automation",
        "awCenterBtn_security",
        "awMultiTabStrip",
        "awPanel_codebase",
        "awPanel_git",
        "awPanel_deliverables",
        "awPanel_automation",
        "awPanel_security",
        "awBtnMasterEmergencyStop",
    ):
        assert f'id="{el_id}"' in html_text, f"Missing 5-Center UI element: {el_id}"

    # Home screen (#welcomeHero) MUST remain 100% pure!
    m = re.search(r'<div class="welcome-hero" id="welcomeHero">([\s\S]*?)</div>\s*</div>\s*</div>', html_text)
    assert m
    hero = m.group(1).lower()
    for forbidden in ("agent center", "dev studio", "automation hub", "emergency stop", "git worktree", "plugin marketplace"):
        assert forbidden not in hero, f"Home screen welcomeHero polluted with '{forbidden}'"


def test_max_4_divisions_deep_upgrades_and_100_scroll_wallpapers(srv_url):
    """End-to-end verification of all 4 Max-Upgraded Divisions + Unified 5-Engine Bridge + /remote + 100 Scroll Wallpapers."""
    h = _user(srv_url)

    # 1. Seed a file with real SQL/Shell/None issues + API route + SQL table
    code = (
        "import sqlite3, subprocess\n"
        "def run_q(cur, uid, cmd, items=[]):\n"
        "    if uid == None:\n"
        "        return None\n"
        "    cur.execute(f'SELECT * FROM accounts WHERE id={uid}')\n"
        "    subprocess.run(cmd, shell=True)\n"
        "    return items\n"
        "# CREATE TABLE accounts (id INT);\n"
        "# @app.route('/api/accounts')\n"
    )
    assert _http(srv_url, "/api/workspace/fs/create", "POST", {"path": "srv/db_api.py", "content": code}, h)[0] == 200
    assert _http(srv_url, "/api/workspace/fs/create", "POST", {"path": "ui/app.js", "content": "fetch('/api/accounts');\n"}, h)[0] == 200

    # Division 1: Deeper Security/Bug Detection (SQLi, Shell, None, security_score)
    c, bugs = _http(srv_url, "/api/dev/bugs", "POST", {"path": "srv/db_api.py"}, h)
    assert c == 200 and bugs["success"] is True
    bug_types = {f["category"] for f in bugs["findings"]}
    assert "SQLInjectionRisk" in bug_types
    assert "ShellInjectionRisk" in bug_types
    assert "NoneIdentityCheck" in bug_types
    assert "security_score" in bugs and bugs["security_score"] < 100

    # Division 1: Real AST-verified Refactoring (mutable default + == None)
    c, ref = _http(srv_url, "/api/dev/refactor", "POST", {"path": "srv/db_api.py"}, h)
    assert c == 200 and ref["success"] is True
    assert "is None" in ref["refactored_content"]
    assert "items=None" in ref["refactored_content"]

    # Division 1: Cross-layer Codebase Architecture (API routes + DB tables + UI->API edge)
    c, arch = _http(srv_url, "/api/dev/codebase_map", "GET", None, h)
    assert c == 200 and arch["success"] is True
    assert any(r["route"] == "/api/accounts" for r in arch["api_routes"])
    assert any(t["table"] == "accounts" for t in arch["db_tables"])

    # Division 1: Inline Diff Review Comment (#41) attached to git status
    c, cm = _http(
        srv_url,
        "/api/git/comment",
        "POST",
        {"path": "srv/db_api.py", "line": 4, "comment": "Use parameterized SQL query"},
        h,
    )
    assert c == 200 and cm["success"] is True and cm["entry"]["line"] == 4
    c, gst = _http(srv_url, "/api/git/status", "GET", None, h)
    assert c == 200 and gst["success"] is True
    assert any(
        f["path"] == "srv/db_api.py" and any("parameterized SQL" in x["comment"] for x in f.get("comments", []))
        for f in gst["changed_files"]
    )

    # Division 2: Custom Agent Execution + Plugin Action + Schedule Run-Now + MCP fs.read + Permission Deny
    c, ag_create = _http(
        srv_url,
        "/api/platform/agents/save",
        "POST",
        {"name": "SecBot", "role": "Security auditor", "allowed_dir": "srv"},
        h,
    )
    assert c == 200 and ag_create["success"] is True
    c, ag_run = _http(
        srv_url,
        "/api/platform/agents/run",
        "POST",
        {"agent_id": ag_create["agent"]["id"], "goal": "Audit srv directory"},
        h,
    )
    assert c == 200 and ag_run["success"] is True and ag_run["files_mapped"] >= 1

    assert _http(srv_url, "/api/platform/plugins/manage", "POST", {"plugin_id": "plugin_secret_shield", "action": "install"}, h)[0] == 200
    c, pl_run = _http(srv_url, "/api/platform/plugins/run", "POST", {"plugin_id": "plugin_secret_shield"}, h)
    assert c == 200 and pl_run["success"] is True

    c, sch = _http(
        srv_url,
        "/api/platform/schedules/save",
        "POST",
        {"name": "Manual Audit", "cron": "0 8 * * *", "workflow_id": "wf_code_quality_pipeline"},
        h,
    )
    assert c == 200 and sch["success"] is True
    c, sch_run = _http(srv_url, "/api/platform/schedules/run", "POST", {"schedule_id": sch["schedule"]["id"]}, h)
    assert c == 200 and sch_run["success"] is True

    c, mcp_read = _http(
        srv_url,
        "/api/platform/mcp/invoke",
        "POST",
        {"server_id": "mcp_aura_workspace", "tool": "fs.read", "params": {"path": "ui/app.js"}},
        h,
    )
    assert c == 200 and mcp_read["success"] is True and "/api/accounts" in mcp_read["result"]["content"]

    # Tool permission deny enforcement on file_delete
    assert _http(srv_url, "/api/platform/permissions", "POST", {"permissions": {"file_delete": "deny"}}, h)[0] == 200
    deny_code, _ = _http(srv_url, "/api/workspace/fs/delete", "POST", {"path": "ui/app.js"}, h)
    assert deny_code == 403
    assert _http(srv_url, "/api/platform/permissions", "POST", {"permissions": {"file_delete": "allow"}}, h)[0] == 200

    # Division 3: Unified 5-Engine Bridge + Isolated Job + 8GB RAM Guard + Live /remote Companion
    c, ov = _http(srv_url, "/api/control/overview", "GET", None, h)
    assert c == 200 and ov["success"] is True
    assert len(ov["unified_engines"]["engines"]) == 5
    assert "low_ram_guard" in ov["resources"]

    c, disp = _http(
        srv_url,
        "/api/control/engines/dispatch",
        "POST",
        {"engine_id": "coderx", "goal": "Audit API surface"},
        h,
    )
    assert c == 200 and disp["success"] is True

    c, iso = _http(
        srv_url,
        "/api/control/execute_isolated",
        "POST",
        {"command": "echo isolated_ok_42"},
        h,
    )
    assert c == 200 and iso["success"] is True and "isolated_ok_42" in iso["stdout"]

    with urllib.request.urlopen(f"{srv_url}/remote", timeout=15) as r_rem:
        assert r_rem.status == 200
        assert "AURA Remote Agent Control" in r_rem.read().decode("utf-8", errors="replace")

    # Division 4: 100 Scroll-Driven Realistic Wallpapers (50 Hacker + 50 BMW/Auto) served via /aura_wallpapers.js
    with urllib.request.urlopen(f"{srv_url}/aura_wallpapers.js", timeout=15) as r_wp:
        assert r_wp.status == 200
        wp_text = r_wp.read().decode("utf-8", errors="replace")
    assert "AURA_WALLPAPERS_100" in wp_text
    assert "AuraWallpaperEngine" in wp_text
    assert "bmw_laser_drl" in wp_text
    assert "aero_windtunnel" in wp_text
    assert "threat_globe" in wp_text


def test_device_intelligence_conversational_coder_tools_and_jarvis_v2(srv_url):
    """Verifies automatic Phone/iPad/MacBook/Desktop detection, conversational Git/Coder/Terminal/Browser/Desktop/Swarm tools, and all 8 JARVIS routines."""
    from aura_brain import (
        AVAILABLE_TOOLS,
        HOST_PRIVILEGED_TOOLS,
        AuraBrain,
        tool_desktop_computer_use,
        tool_dev_code_intelligence,
        tool_git_operations,
        tool_jarvis_execute,
        tool_live_browser_control,
        tool_multi_agent_orchestrate,
        tool_unified_engine_dispatch,
        tool_workspace_terminal,
    )
    from aura_device_context import detect_client_device

    # 1. Verify Device Intelligence accurately identifies iPhone, Android Phone, iPad, MacBook, and Windows Desktop
    iphone = detect_client_device(headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)"})
    assert iphone["device_class"] == "mobile" and iphone["os_name"] == "iOS" and iphone["is_mobile"] is True
    assert iphone["capabilities"]["full_desktop_os_automation"] is False
    assert iphone["capabilities"]["cloud_coder_ide_git_terminal"] is True

    android = detect_client_device(headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Mobile Safari/537.36"})
    assert android["device_class"] == "mobile" and android["os_name"] == "Android"

    ipad = detect_client_device(
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
        body={"client_device": {"platform": "MacIntel", "max_touch_points": 5, "viewport_w": 1024, "viewport_h": 1366}},
    )
    assert ipad["device_class"] == "tablet" and ipad["os_name"] == "iPadOS"

    macbook = detect_client_device(
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)"},
        body={"client_device": {"platform": "MacIntel", "max_touch_points": 0, "viewport_w": 1440, "viewport_h": 900, "likely_laptop": True}},
    )
    assert macbook["device_class"] == "laptop" and macbook["os_name"] == "macOS"

    win_desk = detect_client_device(
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        body={"client_device": {"platform": "Win32", "viewport_w": 1920, "viewport_h": 1080}},
    )
    assert win_desk["device_class"] == "desktop" and win_desk["os_name"] == "Windows"

    # 2. Verify all 8 Antigravity-grade conversational tools are registered & NOT blocked for standard coders
    for tname in (
        "tool_git_operations",
        "tool_workspace_terminal",
        "tool_dev_code_intelligence",
        "tool_live_browser_control",
        "tool_desktop_computer_use",
        "tool_multi_agent_orchestrate",
        "tool_jarvis_execute",
        "tool_unified_engine_dispatch",
    ):
        assert tname in AVAILABLE_TOOLS
        assert tname not in HOST_PRIVILEGED_TOOLS

    # Verify tool inclusion trigger matches Hinglish + English coder/git/jarvis/browser intents
    for prompt in (
        "bhai git commit aur push karde",
        "jarvis coder workspace audit chalao",
        "mere code mein bugs scan karke refactor kar",
        "pytest run karke error diagnose kar",
        "browser open karke screenshot le",
    ):
        assert AuraBrain._should_include_tools_for_contents(
            [{"role": "user", "parts": [{"text": prompt}]}],
            [{"functionDeclarations": [{"name": "tool_git_operations"}]}],
        ) is True

    # 3. End-to-end HTTP verification via /api/chat + /api/jarvis/status + /api/jarvis/run
    h = _user(srv_url)
    h_mobile = dict(h)
    h_mobile["User-Agent"] = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)"

    # Seed workspace code
    assert _http(
        srv_url,
        "/api/workspace/fs/create",
        "POST",
        {"path": "app/service.py", "content": "def calc(a, items=[]):\n    if a == None:\n        return 0\n    return a * 2\n"},
        h,
    )[0] == 200

    # Chat slash commands: /device (mobile detected!), /git commit, /bugs, /refactor, /test, /jarvis coder, /remote
    c, r_dev = _http(srv_url, "/api/chat", "POST", {"prompt": "/device"}, h_mobile)
    assert c == 200 and r_dev["device"]["device_class"] == "mobile" and "iPhone" in r_dev["reply"]

    c, r_git = _http(srv_url, "/api/chat", "POST", {"prompt": "/git commit Initial service module"}, h)
    assert c == 200 and "Git Commit Complete" in r_git["reply"]

    c, r_bugs = _http(srv_url, "/api/chat", "POST", {"prompt": "/bugs app/service.py"}, h)
    assert c == 200 and "Security & Bug Scan" in r_bugs["reply"]

    c, r_ref = _http(srv_url, "/api/chat", "POST", {"prompt": "/refactor app/service.py"}, h)
    assert c == 200 and "AST-Verified Refactor" in r_ref["reply"]

    c, r_run = _http(srv_url, "/api/chat", "POST", {"prompt": "/run echo coder_sandbox_ok"}, h)
    assert c == 200 and "coder_sandbox_ok" in r_run["reply"]

    c, r_rem = _http(srv_url, "/api/chat", "POST", {"prompt": "/remote"}, h_mobile)
    assert c == 200 and "/remote?token=" in r_rem["reply"]

    # Desktop tool called from mobile smartly returns Remote Companion link instead of failing!
    mob_desk = tool_desktop_computer_use("click", x=100, y=100, device_context=iphone)
    assert mob_desk["success"] is True and mob_desk["device_aware_route"] == "mobile_remote_companion"
    assert "/remote?token=" in mob_desk["remote_url"]

    # JARVIS v2: status includes device + all 8 routines; run all 4 new routines cleanly!
    c, jst = _http(srv_url, "/api/jarvis/status", "GET", None, h_mobile)
    assert c == 200 and len(jst["routines"]) == 8 and jst["device"]["device_class"] == "mobile"

    for routine_key in ("coder_workspace_audit", "git_auto_checkpoint", "full_system_diagnostics", "autonomous_mission_dispatch"):
        c, jres = _http(srv_url, "/api/jarvis/run", "POST", {"routine": routine_key}, h)
        assert c == 200 and jres["success"] is True, f"JARVIS routine {routine_key} failed: {jres}"


