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
    assert "aura-core-shell-v14" in sw_text

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
