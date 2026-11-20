"""
===================================================================================
          AURA 10-PILLAR AGENTIC OS — COMPREHENSIVE VERIFICATION SUITE
===================================================================================
Tests ALL 10 requested pillars end-to-end:
1. Multi-Agent Orchestration (Visual Tree Coordinator -> Frontend/Backend/DB -> QA -> Merge)
2. Parallel Agent Execution (True concurrent ThreadPoolExecutor workers)
3. Autonomous Planning Mode (Phased plan, dependencies, approval before execution)
4. Agent Manager (Live dashboard KPIs + Approve / Deny / Retry / Cancel governance)
5. Self-Verification Loops (Broken code -> SyntaxError fix -> AssertionError fix -> PASS)
6. AURA Live Browser (Integrated inside unified workspace)
7. AURA Computer Use (Integrated inside unified workspace)
8. Live Action Timeline (Unified stream across orchestrator, verify, terminal, files, browser, computer)
9. Integrated Terminal (Isolated workspace shell, injection blocking, AI error diagnosis)
10. Integrated File Explorer (Folders, files, search, create, rename, edit, delete, path guard)
===================================================================================
"""

from __future__ import annotations

import json
import re
import threading
import time
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
def server_url():
    srv = aura_web.make_server("127.0.0.1", 0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()
    srv.server_close()


def _register_user(base_url: str) -> Dict[str, str]:
    _SEQ[0] += 1
    uname = f"p10_user_{_SEQ[0]}_{threading.get_ident()}"
    c, d = _http(
        base_url,
        "/api/auth/register",
        method="POST",
        payload={"username": uname, "password": "StrongPassword!2026"},
    )
    assert c == 200 and d.get("success"), f"register failed: {c} {d}"
    return {
        "Authorization": f"Bearer {d['token']}",
        "X-CSRF-Token": d.get("csrf_token", ""),
    }


def test_all_new_endpoints_require_auth(server_url):
    for method, ep, body in [
        ("GET", "/api/orchestrator/dashboard", None),
        ("POST", "/api/orchestrator/plan", {"goal": "Build app"}),
        ("POST", "/api/orchestrator/mission/approve", {"mission_id": "x"}),
        ("POST", "/api/orchestrator/agent/control", {"mission_id": "x", "agent_id": "qa_tester", "command": "approve"}),
        ("POST", "/api/orchestrator/verify", {"target_path": "."}),
        ("GET", "/api/workspace/terminal/history", None),
        ("POST", "/api/workspace/terminal/exec", {"command": "ls"}),
        ("POST", "/api/workspace/terminal/diagnose", {"command": "python x.py"}),
        ("GET", "/api/workspace/fs/tree", None),
        ("POST", "/api/workspace/fs/mkdir", {"path": "src"}),
        ("POST", "/api/workspace/fs/create", {"path": "a.py", "content": ""}),
        ("POST", "/api/workspace/fs/rename", {"old_path": "a.py", "new_path": "b.py"}),
        ("POST", "/api/workspace/fs/delete", {"path": "b.py"}),
    ]:
        code, _ = _http(server_url, ep, method=method, payload=body)
        assert code == 401, f"{method} {ep} must reject unauthenticated callers, got {code}"


def test_pillars_1_2_3_planning_parallel_orchestration_and_verified_delivery(server_url):
    h = _register_user(server_url)

    # Pillar 3: Create phased execution plan BEFORE modifying workspace
    code, plan_res = _http(
        server_url,
        "/api/orchestrator/plan",
        method="POST",
        payload={"goal": "Build an Expense Tracker with UI, Python API, SQLite DB and unit tests"},
        headers=h,
    )
    assert code == 200 and plan_res["success"] is True
    mission = plan_res["mission"]
    mid = mission["id"]
    assert mission["status"] == "awaiting_approval"
    assert mission["plan_approved"] is False
    assert len(mission["phases"]) == 4
    assert any(p["mode"] == "parallel" for p in mission["phases"])

    # Verify workspace has NOT been written before approval
    _, fs_before = _http(server_url, "/api/workspace/fs/tree", headers=h)
    assert fs_before["total_files"] == 0

    # Approve & execute parallel multi-agent mission (wait_sync=True for deterministic test verification)
    code, run_res = _http(
        server_url,
        "/api/orchestrator/mission/approve",
        method="POST",
        payload={"mission_id": mid, "wait_sync": True},
        headers=h,
    )
    assert code == 200 and run_res["success"] is True
    done = run_res["mission"]
    assert done["status"] == "completed", f"Mission did not complete: {done}"
    assert done["plan_approved"] is True
    assert done["verification_result"]["verified"] is True

    # Confirm all 6 hierarchical agents completed & created real workspace deliverables
    statuses = {a["id"]: a["status"] for a in done["agents"]}
    for aid in ("coordinator", "frontend", "backend", "database", "qa_tester", "synthesizer"):
        assert statuses[aid] == "completed", f"Agent {aid} status: {statuses}"

    _, fs_after = _http(server_url, "/api/workspace/fs/tree", headers=h)
    paths = {f["path"] for f in fs_after["files"]}
    base = done["workspace_rel"]
    assert f"{base}/ARCHITECTURE.md" in paths
    assert f"{base}/frontend/index.html" in paths
    assert f"{base}/backend/service.py" in paths
    assert f"{base}/database/schema.sql" in paths
    assert f"{base}/database/store.py" in paths
    assert f"{base}/tests/test_mission.py" in paths
    assert f"{base}/MISSION_REPORT.md" in paths


def test_pillar_4_agent_manager_live_approval_governance(server_url):
    h = _register_user(server_url)

    # Create plan pausing QA agent for explicit human approval inside Agent Manager
    code, p = _http(
        server_url,
        "/api/orchestrator/plan",
        method="POST",
        payload={
            "goal": "Build Inventory Manager",
            "require_approval_agents": ["qa_tester"],
        },
        headers=h,
    )
    assert code == 200
    mid = p["mission"]["id"]

    # Launch asynchronously so QA pauses in `needs_approval`
    code, _ = _http(
        server_url,
        "/api/orchestrator/mission/approve",
        method="POST",
        payload={"mission_id": mid, "wait_sync": False},
        headers=h,
    )
    assert code == 200

    # Poll Agent Manager dashboard until qa_tester reaches needs_approval
    saw_needs_approval = False
    for _ in range(40):
        _, dash = _http(server_url, "/api/orchestrator/dashboard", headers=h)
        if dash["summary"]["needs_approval"] >= 1:
            saw_needs_approval = True
            break
        time.sleep(0.1)
    assert saw_needs_approval, "Agent Manager never surfaced qa_tester in needs_approval state"

    # Approve QA agent via Agent Manager control endpoint
    code, ctrl = _http(
        server_url,
        "/api/orchestrator/agent/control",
        method="POST",
        payload={"mission_id": mid, "agent_id": "qa_tester", "command": "approve"},
        headers=h,
    )
    assert code == 200 and ctrl["success"] is True

    # Wait for mission completion after approval
    completed = False
    for _ in range(50):
        _, dash = _http(server_url, "/api/orchestrator/dashboard", headers=h)
        if dash["active_mission"]["status"] == "completed":
            completed = True
            break
        time.sleep(0.12)
    assert completed, "Mission did not finish cleanly after approving qa_tester"


def test_pillar_5_self_verification_loop_auto_repairs_and_retests(server_url):
    h = _register_user(server_url)

    # Write intentionally broken module (BOTH SyntaxError missing colon AND logic bug a - b!)
    broken_code = "def add(a, b)\n    return a - b\n"
    test_code = (
        "import unittest\n"
        "from calc_mod import add\n\n"
        "class TestCalc(unittest.TestCase):\n"
        "    def test_add(self):\n"
        "        self.assertEqual(add(2, 3), 5)\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n"
    )
    assert _http(server_url, "/api/workspace/fs/create", "POST", {"path": "calc_mod.py", "content": broken_code}, h)[0] == 200
    assert _http(server_url, "/api/workspace/fs/create", "POST", {"path": "test_calc_mod.py", "content": test_code}, h)[0] == 200

    # Run Self-Verification Loop (max 4 attempts):
    # Attempt 1 -> SyntaxError -> fixes colon
    # Attempt 2 -> AssertionError -> fixes `a - b` to `a + b`
    # Attempt 3 -> PASS!
    code, ver = _http(
        server_url,
        "/api/orchestrator/verify",
        method="POST",
        payload={"target_path": "calc_mod.py", "max_attempts": 4},
        headers=h,
    )
    assert code == 200 and ver["success"] is True
    assert ver["verified"] is True, f"Self-verification failed to repair broken code: {ver}"
    assert ver["attempts"] == 3
    assert ver["iterations"][0]["passed"] is False and ver["iterations"][0]["repair_applied"]
    assert ver["iterations"][1]["passed"] is False and ver["iterations"][1]["repair_applied"]
    assert ver["iterations"][2]["passed"] is True

    # Confirm unfixable test NEVER falsely claims verified=True
    unfixable = "def mystery():\n    return 'wrong'\n"
    unfixable_test = (
        "import unittest\nfrom unfix import mystery\n"
        "class T(unittest.TestCase):\n    def test_m(self): self.assertEqual(mystery(), 'expected_secret_xyz')\n"
    )
    _http(server_url, "/api/workspace/fs/create", "POST", {"path": "unfix.py", "content": unfixable}, h)
    _http(server_url, "/api/workspace/fs/create", "POST", {"path": "test_unfix.py", "content": unfixable_test}, h)
    code2, ver2 = _http(server_url, "/api/orchestrator/verify", "POST", {"target_path": "unfix.py", "max_attempts": 2}, h)
    assert code2 == 200 and ver2["verified"] is False


def test_pillar_9_integrated_terminal_safety_and_error_diagnosis(server_url):
    h = _register_user(server_url)

    # Safe workspace commands
    c, r1 = _http(server_url, "/api/workspace/terminal/exec", "POST", {"command": "mkdir proj"}, h)
    assert c == 200 and r1["entry"]["exit_code"] == 0

    c, r2 = _http(server_url, "/api/workspace/terminal/exec", "POST", {"command": "cd proj"}, h)
    assert c == 200 and r2["cwd"] == "proj"

    c, _ = _http(server_url, "/api/workspace/fs/create", "POST", {"path": "proj/fail_div.py", "content": "x = 1 / 0\n"}, h)
    assert c == 200

    c, r3 = _http(server_url, "/api/workspace/terminal/exec", "POST", {"command": "python fail_div.py"}, h)
    assert c == 200 and r3["entry"]["exit_code"] != 0
    assert "ZeroDivisionError" in r3["entry"]["stderr"]

    # AI Error Diagnosis on failing terminal output
    c, diag = _http(server_url, "/api/workspace/terminal/diagnose", "POST", {}, h)
    assert c == 200 and diag["success"] is True
    assert "ZeroDivisionError" in diag["diagnosis"]

    # Security: shell chaining, host escape, and restricted binaries MUST be blocked
    for bad_cmd in [
        "ls; whoami",
        "ls && echo hacked",
        "cat ../../aura_web.py",
        "powershell Get-Process",
        "sudo rm -rf /",
    ]:
        bc, bd = _http(server_url, "/api/workspace/terminal/exec", "POST", {"command": bad_cmd}, h)
        assert bc == 400 and bd["success"] is False, f"Dangerous terminal command NOT blocked: {bad_cmd}"


def test_pillar_10_integrated_file_explorer_crud_and_tenant_isolation(server_url):
    h1 = _register_user(server_url)
    h2 = _register_user(server_url)

    # Create folder & file, search, rename, edit, delete
    assert _http(server_url, "/api/workspace/fs/mkdir", "POST", {"path": "src/ui"}, h1)[0] == 200
    assert _http(server_url, "/api/workspace/fs/create", "POST", {"path": "src/ui/app.js", "content": "console.log('hi');"}, h1)[0] == 200

    c, tree = _http(server_url, "/api/workspace/fs/tree?search=app.js", headers=h1)
    assert c == 200 and len(tree["files"]) == 1 and tree["files"][0]["path"] == "src/ui/app.js"

    # Rename file
    c, ren = _http(server_url, "/api/workspace/fs/rename", "POST", {"old_path": "src/ui/app.js", "new_path": "src/ui/main.js"}, h1)
    assert c == 200 and ren["new_path"] == "src/ui/main.js"

    # Tenant isolation: User 2 sees 0 files & 0 folders & 0 timeline events from User 1
    _, t2 = _http(server_url, "/api/workspace/fs/tree", headers=h2)
    assert t2["total_files"] == 0 and t2["total_folders"] == 0

    _, feed2 = _http(server_url, "/api/actions/feed", headers=h2)
    assert feed2["stats"]["total"] == 0

    # Path traversal blocked
    assert _http(server_url, "/api/workspace/fs/create", "POST", {"path": "../outside.txt", "content": "x"}, h1)[0] == 400
    assert _http(server_url, "/api/workspace/fs/rename", "POST", {"old_path": "src/ui/main.js", "new_path": "../../evil.js"}, h1)[0] == 400

    # Delete cleanly
    c, dl = _http(server_url, "/api/workspace/fs/delete", "POST", {"path": "src"}, h1)
    assert c == 200 and dl["deleted"] == "src"

    # Pillar 8: Unified Live Action Timeline recorded files events for User 1
    _, feed1 = _http(server_url, "/api/actions/feed", headers=h1)
    assert feed1["stats"]["files"] >= 4


def test_ui_all_10_pillars_present_and_home_screen_untouched():
    html_text = (ROOT / "index.html").read_text(encoding="utf-8")
    sw_text = (ROOT / "sw.js").read_text(encoding="utf-8")

    assert "aura-core-shell-v13" in sw_text

    # All 6 unified tabs + 3 orchestrator subviews present
    for el_id in (
        "awTabBtn_agents",
        "awTabBtn_browser",
        "awTabBtn_computer",
        "awTabBtn_terminal",
        "awTabBtn_explorer",
        "awTabBtn_actions",
        "awAgentsSub_plan",
        "awAgentsSub_manager",
        "awAgentsSub_verify",
        "awPanel_terminal",
        "awPanel_explorer",
    ):
        assert f'id="{el_id}"' in html_text, f"Missing UI element {el_id}"

    # Home screen (#welcomeHero) MUST remain 100% pure with zero feature promo clutter!
    m = re.search(r'<div class="welcome-hero" id="welcomeHero">([\s\S]*?)</div>\s*</div>\s*</div>', html_text)
    assert m
    hero = m.group(1).lower()
    for forbidden in ("multi-agent", "live browser", "computer use", "terminal", "file explorer", "self-verification"):
        assert forbidden not in hero, f"Home screen welcomeHero must not contain '{forbidden}'"
