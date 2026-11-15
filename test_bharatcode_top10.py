"""
End-to-End Verification Suite for AURA BharatCode Build League Top-10 Super-Suite,
Deep-Space Scroll-Driven Animation UI, and Active Engine Mesh.
"""

from pathlib import Path
from aura_bharatcode_top10 import BHARATCODE_TOP10_SUITE
from aura_brain import (
    AVAILABLE_TOOLS,
    tool_bharatcode_top10_execute,
    tool_bharatcode_top10_superpipeline,
)
from aura_engine_mesh import AURA_ENGINE_MESH


def test_bharatcode_top10_registry_complete():
    overview = BHARATCODE_TOP10_SUITE.get_suite_overview()
    assert overview["success"] is True
    assert overview["total_integrated"] == 10
    assert overview["all_active"] is True
    ranks = [item["rank"] for item in overview["engines"]]
    assert ranks == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def test_all_10_bharatcode_winner_engines_execute_100_percent():
    keys = [
        "trinetra",
        "bharatcode_ide",
        "gitkitty",
        "ashby_job_radar",
        "learnos",
        "form2fact",
        "orvyn_interview",
        "spare_gpu",
        "payguard_upi",
        "anonymous_campus",
    ]
    for idx, key in enumerate(keys, start=1):
        res = BHARATCODE_TOP10_SUITE.execute_engine(key, {"prompt": f"Verify winner #{idx} {key}"})
        assert res.get("success") is True, f"Engine {key} failed: {res}"
        assert res.get("rank") == idx


def test_bharatcode_superpipeline_runs_all_10():
    res = BHARATCODE_TOP10_SUITE.run_all_10_superpipeline("Verify all 10 BharatCode winners inside AURA")
    assert res["success"] is True
    assert res["engines_executed"] == 10
    assert res["engines_succeeded"] == 10
    assert len(res["stages"]) == 10


def test_aura_brain_bharatcode_tools_registered_and_working():
    assert "tool_bharatcode_top10_execute" in AVAILABLE_TOOLS
    assert "tool_bharatcode_top10_superpipeline" in AVAILABLE_TOOLS

    r1 = tool_bharatcode_top10_execute("trinetra", "Deepfake voice clone and UPI phishing attack")
    assert r1["success"] is True
    assert r1["rank"] == 1
    assert len(r1["statutory_citations"]) >= 1

    r2 = tool_bharatcode_top10_superpipeline("Autonomous security and engineering sweep")
    assert r2["success"] is True
    assert r2["engines_succeeded"] == 10


def test_deep_space_scroll_animation_and_bharatcode_ui_present():
    html = (Path(__file__).resolve().parent / "index.html").read_text(encoding="utf-8")
    assert 'id="spaceCanvas"' in html
    assert 'id="spaceOrbitalRingOverlay"' in html
    assert 'id="spaceScrollProgressBar"' in html
    assert 'id="spaceWarpBadge"' in html
    assert "initDeepSpaceScrollEngine" in html
    assert 'id="fTab_bharatcode10"' in html
    assert 'id="fSection_bharatcode10"' in html
    assert "runBharatCodeSingleEngine" in html
    assert "runBharatCodeSuperPipeline" in html


def test_engine_mesh_all_63_mounted():
    status = AURA_ENGINE_MESH.get_mesh_status()
    assert status["status"] == "ALL_DECLARED_ENGINES_MOUNTED"
    assert status["awakened_engines"] == status["total_engines"]
    assert status["total_engines"] == 63


def test_bharatcode_top10_http_endpoints_end_to_end():
    import json
    import threading
    import urllib.request
    import aura_db
    from aura_web import make_server

    server = make_server("127.0.0.1", 0)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        reg = aura_db.register_user("bc10_http_tester", "PassBC10_123!")
        if not reg.get("success"):
            reg = aura_db.login_user("bc10_http_tester", "PassBC10_123!")
        token = reg["token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        req_ov = urllib.request.Request(f"http://127.0.0.1:{port}/api/bharatcode10/overview", headers=headers, method="GET")
        with urllib.request.urlopen(req_ov, timeout=5) as resp:
            ov_data = json.loads(resp.read().decode("utf-8"))
            assert ov_data["success"] is True
            assert ov_data["total_engines"] == 10

        req_ex = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/bharatcode10/execute",
            data=json.dumps({"engine": "payguard_upi", "payload": {"upi_uri": "upi://pay?pa=refund-scam@ybl&am=25000&mode=02"}}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req_ex, timeout=5) as resp:
            ex_data = json.loads(resp.read().decode("utf-8"))
            assert ex_data["success"] is True
            assert ex_data["rank"] == 9
            assert ex_data["explainable_safety_audit"]["risk_level"] == "HIGH_RISK_BLOCK"

        req_sp = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/bharatcode10/superpipeline",
            data=json.dumps({"goal": "End-to-end HTTP verification of all 10 Sovereign engines"}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req_sp, timeout=10) as resp:
            sp_data = json.loads(resp.read().decode("utf-8"))
            assert sp_data["success"] is True
            assert sp_data["engines_executed"] == 10
            assert sp_data["all_succeeded"] is True

        req_ag_ov = urllib.request.Request(f"http://127.0.0.1:{port}/api/antigravity/overview", headers=headers, method="GET")
        with urllib.request.urlopen(req_ag_ov, timeout=5) as resp:
            ag_ov = json.loads(resp.read().decode("utf-8"))
            assert ag_ov["success"] is True
            assert len(ag_ov["slash_commands"]) == 9

        req_ag_slash = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/antigravity/slash",
            data=json.dumps({"command": "/goal", "prompt": "Verify Antigravity slash command"}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req_ag_slash, timeout=5) as resp:
            ag_slash = json.loads(resp.read().decode("utf-8"))
            assert ag_slash["success"] is True
            assert ag_slash["slash_command"] == "/goal"

        req_ag_desk = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/antigravity/desktop",
            data=json.dumps({"action": "set_brightness", "value": 55}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req_ag_desk, timeout=5) as resp:
            ag_desk = json.loads(resp.read().decode("utf-8"))
            assert ag_desk["success"] is True
            assert ag_desk["level"] == 55
            assert ag_desk["client_bridge_command"]["level"] == 55
    finally:
        server.shutdown()
        server.server_close()


def test_zero_visible_bharatcode_branding_and_antigravity_core_active():
    import re
    from aura_antigravity_core import AURA_ANTIGRAVITY_CORE

    html = (Path(__file__).resolve().parent / "index.html").read_text(encoding="utf-8")
    no_scripts = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S | re.I)
    no_styles = re.sub(r"<style\b[^>]*>.*?</style>", "", no_scripts, flags=re.S | re.I)
    visible_text = re.sub(r"<[^>]+>", " ", no_styles)
    assert len(re.findall(r"BharatCode|Build League", visible_text, flags=re.I)) == 0
    assert 'id="fTab_antigravity"' in html
    assert 'id="fSection_antigravity"' in html
    assert "executeClientBridgeCommand" in html

    for cmd in ["/goal", "/plan", "/boost", "/teamwork", "/browser", "/schedule", "/compact", "/learn", "/grill-me"]:
        res = AURA_ANTIGRAVITY_CORE.execute_slash_command(cmd, "Test mission")
        assert res["success"] is True
