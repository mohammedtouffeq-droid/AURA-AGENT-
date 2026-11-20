"""
Comprehensive End-to-End & Security Verification Suite for:
1. AURA Live Browser (multi-tab, SSRF guard, navigate, click/type/scroll, vision understanding, agent loop)
2. AURA Computer Use (Start/Pause/Resume/Stop/Take Control HITL, kill-switch & hotkey guard, dry-run safety, screenshot/UI tree/vision)
3. AURA Live Action View (real-time telemetry feed, tenant isolation, cursor tracking, stats & clear)
4. UI Integrity (Home screen welcomeHero untouched, all 3 capabilities present, sw.js v12)
"""

from __future__ import annotations

import base64
import io
import json
import re
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest

import aura_db
import aura_web
from aura_jarvis_hub import JARVIS_HUB
from aura_live_actions import LIVE_ACTION_HUB
from aura_live_browser import LIVE_BROWSER

ROOT = Path(__file__).resolve().parent


def _http_req(
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
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"raw": raw}
        return exc.code, body


@pytest.fixture(scope="module")
def live_server():
    srv = aura_web.make_server("127.0.0.1", 0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()
    srv.server_close()


_USER_SEQ = [0]


def _create_auth_headers(base_url: str) -> Dict[str, str]:
    _USER_SEQ[0] += 1
    uname = f"aw_test_{_USER_SEQ[0]}_{threading.get_ident()}"
    status, data = _http_req(
        base_url,
        "/api/auth/register",
        method="POST",
        payload={"username": uname, "password": "TestPassword!2026"},
    )
    assert status == 200 and data.get("success"), f"Register failed: {status} {data}"
    return {
        "Authorization": f"Bearer {data['token']}",
        "X-CSRF-Token": data.get("csrf_token", ""),
    }


def test_unauthenticated_endpoints_rejected(live_server):
    for method, ep, body in [
        ("GET", "/api/browser/state", None),
        ("POST", "/api/browser/navigate", {"url": "https://example.com"}),
        ("GET", "/api/computer/status", None),
        ("GET", "/api/computer/screenshot", None),
        ("GET", "/api/computer/ui_tree", None),
        ("POST", "/api/computer/control", {"command": "start"}),
        ("POST", "/api/computer/action", {"action": "click", "x": 100, "y": 100}),
        ("GET", "/api/actions/feed", None),
        ("POST", "/api/actions/clear", {}),
    ]:
        code, data = _http_req(live_server, ep, method=method, payload=body)
        assert code == 401, f"{method} {ep} must require auth, got {code}: {data}"


def test_browser_ssrf_strictly_blocked(live_server):
    h = _create_auth_headers(live_server)
    unsafe_urls = [
        "http://127.0.0.1:5050/api/health",
        "http://localhost/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/internal",
        "http://192.168.1.1/",
        "file:///C:/Windows/win.ini",
        "javascript:alert(1)",
    ]
    for bad in unsafe_urls:
        code, data = _http_req(live_server, "/api/browser/navigate", method="POST", payload={"url": bad}, headers=h)
        assert code == 400 and data.get("success") is False, f"SSRF URL was NOT blocked: {bad} -> {code} {data}"

    # Verify blocked events logged into Live Action View
    code, feed = _http_req(live_server, "/api/actions/feed?source=browser", method="GET", headers=h)
    assert code == 200 and feed.get("success") is True
    assert any(ev.get("status") == "blocked" for ev in feed.get("actions", []))


def test_browser_multitab_actions_understanding_and_agent(live_server, monkeypatch):
    h = _create_auth_headers(live_server)

    # Deterministic mock remote fetch so unit tests run offline & instantaneously
    def _mock_fetch(self, url: str, scroll_y: int = 0) -> Dict[str, Any]:
        return {
            "url": url,
            "title": f"Mock Page for {url}",
            "page_text": "Quantum computing harnesses superposition and entanglement for high-speed computation.",
            "meta_desc": "Mock test description",
            "headings": ["Overview", "Applications"],
            "elements": [
                {"index": 1, "tag": "a", "text": "Learn More", "href": "https://example.org/docs", "x": 220, "y": 190, "w": 120, "h": 30},
                {"index": 2, "tag": "input", "type": "search", "text": "Search", "href": "", "x": 420, "y": 120, "w": 240, "h": 34},
            ],
            "scroll": {"x": 0, "y": scroll_y, "max_y": 1200},
            "viewport": {"width": 1280, "height": 760},
            "screenshot_b64": base64.b64encode(b"\xff\xd8\xff\xe0MOCKJPEG").decode("ascii"),
            "engine": "cloud_dom",
        }

    monkeypatch.setattr(LIVE_BROWSER, "_fetch_cloud_page", _mock_fetch.__get__(LIVE_BROWSER, type(LIVE_BROWSER)))
    monkeypatch.setattr("aura_live_browser.is_safe_public_url", lambda u: (u.startswith("https://example."), "" if u.startswith("https://example.") else "blocked"))

    # 1. Initial state
    code, st = _http_req(live_server, "/api/browser/state", headers=h)
    assert code == 200 and st["success"] is True
    assert len(st["tabs"]) == 1

    # 2. Navigate tab_1
    code, nav1 = _http_req(live_server, "/api/browser/navigate", method="POST", payload={"url": "https://example.com"}, headers=h)
    assert code == 200 and nav1["success"] is True
    assert nav1["active_tab"]["url"] == "https://example.com"
    assert len(nav1["active_tab"]["elements"]) == 2

    # 3. Open second tab & verify multi-tab state
    code, t2 = _http_req(live_server, "/api/browser/tab/new", method="POST", payload={"url": "https://example.org"}, headers=h)
    assert code == 200 and len(t2["tabs"]) == 2
    tab2_id = t2["active_tab_id"]
    assert t2["active_tab"]["url"] == "https://example.org"

    # 4. Switch back to tab_1
    code, sw = _http_req(live_server, "/api/browser/tab/switch", method="POST", payload={"tab_id": "tab_1"}, headers=h)
    assert code == 200 and sw["active_tab_id"] == "tab_1"
    assert sw["active_tab"]["url"] == "https://example.com"

    # 5. Browser actions: scroll, click, screenshot
    code, scr = _http_req(live_server, "/api/browser/action", method="POST", payload={"action": "scroll", "delta_y": 400}, headers=h)
    assert code == 200 and scr["active_tab"]["scroll"]["y"] == 400

    code, clk = _http_req(live_server, "/api/browser/action", method="POST", payload={"action": "click", "element_index": 1}, headers=h)
    assert code == 200 and clk["active_tab"]["url"] == "https://example.org/docs"

    # 6. Page understanding (Vision + DOM)
    code, und = _http_req(live_server, "/api/browser/understand", method="POST", payload={"question": "Summarize this page"}, headers=h)
    assert code == 200 and und["success"] is True
    assert "Quantum computing" in und["analysis"] or "Mock Page" in und["analysis"]

    # 7. AI Agent Goal Loop
    code, ag = _http_req(live_server, "/api/browser/agent", method="POST", payload={"goal": "Open https://example.com and scroll down"}, headers=h)
    assert code == 200 and ag["success"] is True
    assert len(ag["steps"]) >= 2

    # 8. Close tab_2 cleanly
    code, cl = _http_req(live_server, "/api/browser/tab/close", method="POST", payload={"tab_id": tab2_id}, headers=h)
    assert code == 200 and len(cl["tabs"]) == 1


def test_computer_use_hitl_controls_guardrails_and_vision(live_server):
    h = _create_auth_headers(live_server)

    # 1. Initial status
    code, st = _http_req(live_server, "/api/computer/status", headers=h)
    assert code == 200 and st["success"] is True
    assert st["state"] == "idle"
    assert len(st["supported_apps"]) >= 6

    # 2. Start -> Pause -> Resume -> Take Control -> Stop
    code, c1 = _http_req(live_server, "/api/computer/control", method="POST", payload={"command": "start", "goal": "Inspect active desktop"}, headers=h)
    assert code == 200 and c1["status"]["state"] == "running"

    # 3. Direct action works safely in test dry-run while running
    code, act1 = _http_req(live_server, "/api/computer/action", method="POST", payload={"action": "click", "x": 640, "y": 360}, headers=h)
    assert code == 200 and act1["success"] is True

    # 4. High-risk OS hotkey strictly blocked
    code, bad_hk = _http_req(live_server, "/api/computer/action", method="POST", payload={"action": "hotkey", "keys": ["alt", "f4"]}, headers=h)
    assert code == 400 and bad_hk["success"] is False

    # 5. Pause blocks further AI desktop actions until resumed
    code, c2 = _http_req(live_server, "/api/computer/control", method="POST", payload={"command": "pause"}, headers=h)
    assert code == 200 and c2["status"]["state"] == "paused"

    code, blocked_while_paused = _http_req(live_server, "/api/computer/action", method="POST", payload={"action": "type", "text": "hello"}, headers=h)
    assert code == 400 and blocked_while_paused["success"] is False

    # 6. Resume -> Take Control immediately blocks AI actions
    code, c3 = _http_req(live_server, "/api/computer/control", method="POST", payload={"command": "resume"}, headers=h)
    assert code == 200 and c3["status"]["state"] == "running"

    code, c4 = _http_req(live_server, "/api/computer/control", method="POST", payload={"command": "take_control"}, headers=h)
    assert code == 200 and c4["status"]["state"] == "human_control"

    code, blocked_takeover = _http_req(live_server, "/api/computer/action", method="POST", payload={"action": "click", "x": 200, "y": 200}, headers=h)
    assert code == 400 and blocked_takeover["success"] is False

    # 7. Stop
    code, c5 = _http_req(live_server, "/api/computer/control", method="POST", payload={"command": "stop"}, headers=h)
    assert code == 200 and c5["status"]["state"] == "stopped"

    # 8. Live screenshot, UI tree, and client-uploaded frame Vision analysis
    code, shot = _http_req(live_server, "/api/computer/screenshot", headers=h)
    assert code == 200 and shot["success"] is True and len(shot.get("frame_b64", "")) > 100

    code, tree = _http_req(live_server, "/api/computer/ui_tree", headers=h)
    assert code == 200 and tree["success"] is True and isinstance(tree.get("controls"), list)

    code, vis = _http_req(
        live_server,
        "/api/computer/analyze_frame",
        method="POST",
        payload={"goal": "Describe active desktop", "frame_b64": shot["frame_b64"]},
        headers=h,
    )
    assert code == 200 and vis["success"] is True and len(vis.get("analysis", "")) > 10


def test_tenant_isolation_and_live_action_view_clear(live_server):
    h_a = _create_auth_headers(live_server)
    h_b = _create_auth_headers(live_server)

    # User A creates a tab and starts Computer Use
    _http_req(live_server, "/api/browser/tab/new", method="POST", payload={}, headers=h_a)
    _http_req(live_server, "/api/computer/control", method="POST", payload={"command": "start", "goal": "User A Secret Task"}, headers=h_a)

    # User B must NOT see User A's tabs, Computer Use goal, or Live Action feed
    _, b_browser = _http_req(live_server, "/api/browser/state", headers=h_b)
    assert len(b_browser["tabs"]) == 1

    _, b_comp = _http_req(live_server, "/api/computer/status", headers=h_b)
    assert b_comp["state"] == "idle"
    assert "Secret Task" not in (b_comp.get("goal") or "")

    _, b_feed = _http_req(live_server, "/api/actions/feed", headers=h_b)
    assert b_feed["stats"]["total"] == 0

    _, a_feed = _http_req(live_server, "/api/actions/feed", headers=h_a)
    assert a_feed["stats"]["total"] >= 2

    # User A clears feed cleanly
    code, clr = _http_req(live_server, "/api/actions/clear", method="POST", payload={}, headers=h_a)
    assert code == 200 and clr["cleared"] is True
    _, a_feed_after = _http_req(live_server, "/api/actions/feed", headers=h_a)
    assert a_feed_after["stats"]["total"] == 0


def test_ui_home_screen_sacred_and_three_capabilities_present():
    html_text = (ROOT / "index.html").read_text(encoding="utf-8")
    sw_text = (ROOT / "sw.js").read_text(encoding="utf-8")

    assert "aura-core-shell-v12" in sw_text

    # All 3 separate capabilities exist inside right-side #agentWorkspacePane
    assert 'id="agentWorkspacePane"' in html_text
    assert 'id="awPanel_browser"' in html_text
    assert 'id="awPanel_computer"' in html_text
    assert 'id="awPanel_actions"' in html_text
    assert 'id="awCompBtnStart"' in html_text
    assert 'id="awCompBtnPause"' in html_text
    assert 'id="awCompBtnStop"' in html_text
    assert 'id="awCompBtnTakeover"' in html_text

    # CRITICAL USER RULE: Home screen (#welcomeHero) MUST NOT contain feature clutter text!
    m = re.search(r'<div class="welcome-hero" id="welcomeHero">([\s\S]*?)</div>\s*</div>\s*</div>', html_text)
    assert m, "Could not locate #welcomeHero block"
    hero_block = m.group(1)
    for forbidden in ("Live Browser", "Computer Use", "Live Action View", "Desktop Automation", "Playwright", "PyAutoGUI"):
        assert forbidden.lower() not in hero_block.lower(), f"Home screen welcomeHero must remain clean! Found '{forbidden}'"
