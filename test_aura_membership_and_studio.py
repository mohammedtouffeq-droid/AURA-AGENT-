"""
Automated regression suite for AURA 5-Tier Membership System, 25-Key Cryptographic Registry,
Rolling 24-Hour Daily Quotas (30 / 60 / Unlimited), Cross-Container Serverless Proof,
and Pro / Apex Omnis Engineering Studio (Tiers 1–5).
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

import aura_db
import aura_membership
import aura_pro_studio
import aura_web


def _http_json(
    url: str,
    method: str = "GET",
    payload: Dict[str, Any] | None = None,
    headers: Dict[str, str] | None = None,
    timeout: float = 15.0,
) -> Tuple[int, Dict[str, Any]]:
    hdrs = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}


@pytest.fixture()
def membership_server(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AURA_SESSION_SECRET", "unit-test-membership-session-secret-0123456789abcdef")
    monkeypatch.setenv("AURA_VAULT_SECRET", "unit-test-membership-vault-secret-0123456789abcdef")
    monkeypatch.setenv("AURA_CSRF_SECRET", "unit-test-membership-csrf-secret-0123456789abcdef")
    aura_db._RUNTIME_SECRETS_CACHE.clear()

    db_file = tmp_path / "aura_mem_test.db"
    ws_root = tmp_path / "ws"
    ws_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(aura_db, "DB_PATH", db_file)
    monkeypatch.setattr(aura_web, "_resolve_workspace_dir", lambda uid=None: (ws_root / f"user_{int(uid)}" if uid is not None else ws_root))
    aura_db.init_database()

    # Register synthetic unit-test activation keys (one per tier) via monkeypatch — never hardcodes real keys
    test_keys = {
        f"tier_{i}": f"AURA-TST{i}-UNIT-TEST-000{i}" for i in range(1, 6)
    }
    patched_hashes = dict(aura_membership.ACTIVATION_KEY_HASHES)
    for tid, k in test_keys.items():
        patched_hashes[aura_membership.hash_activation_key(k)] = {"tier_id": tid, "slot": f"{tid}_unit"}
    monkeypatch.setattr(aura_membership, "ACTIVATION_KEY_HASHES", patched_hashes)

    server = ThreadingHTTPServer(("127.0.0.1", 0), aura_web.AuraWebHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        yield {
            "base_url": f"http://127.0.0.1:{port}",
            "test_keys": test_keys,
            "tmp_path": tmp_path,
            "ws_root": ws_root,
        }
    finally:
        server.shutdown()
        server.server_close()


def test_25_hashed_keys_registered_and_zero_plaintext_keys_or_pricing_in_repo():
    assert len(aura_membership.ACTIVATION_KEY_HASHES) == 25
    by_tier: Dict[str, int] = {}
    for meta in aura_membership.ACTIVATION_KEY_HASHES.values():
        by_tier[meta["tier_id"]] = by_tier.get(meta["tier_id"], 0) + 1
    assert by_tier == {"tier_1": 5, "tier_2": 5, "tier_3": 5, "tier_4": 5, "tier_5": 5}

    # Ensure zero plaintext production keys leaked into tracked source files
    root = Path(__file__).resolve().parent
    key_rx = re.compile(r"AURA-(?:VEL1|ARC2|SOV3|TTN4|APX5)-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}")
    for fname in ("aura_membership.py", "aura_pro_studio.py", "aura_web.py", "index.html"):
        txt = (root / fname).read_text(encoding="utf-8")
        assert not key_rx.search(txt), f"Plaintext activation key found in {fname}!"

    # Ensure zero pricing/payment UI or 'Codex' branding inside Membership & Studio markup
    html = (root / "index.html").read_text(encoding="utf-8")
    assert 'id="membershipSettingsSection"' in html
    assert 'id="apexStudioOverlay"' in html
    assert 'id="permissionRiskBadge"' in html
    mem_chunk = html[html.find('id="membershipSettingsSection"'):html.find('id="voiceStudioSection"')]
    assert not re.search(r"(?:\bprice\b|\bcheckout\b|\bstripe\b|\bbuy now\b|₹)", mem_chunk, re.I)


def test_rolling_24h_daily_chat_limits_and_serverless_membership_recovery(membership_server, monkeypatch):
    base = membership_server["base_url"]
    keys = membership_server["test_keys"]

    st, reg = _http_json(f"{base}/api/auth/register", "POST", {"username": "quota_student", "password": "QuotaPass!2026"})
    assert st == 200 and reg["success"]
    uid = reg["user"]["id"]
    hdrs = {"Authorization": f"Bearer {reg['token']}"}

    # Simulate 30 prior chat events inside the last 24h on Standard (tier_0)
    now = time.time()
    for i in range(30):
        aura_db.record_chat_quota_event(uid, created_at=now - (30 - i))

    # Chat #31 MUST be rejected cleanly with HTTP 429 + daily_limit_reached
    st_429, body_429 = _http_json(
        f"{base}/api/chat",
        "POST",
        {"prompt": "Hello AURA", "thread_id": reg["default_thread_id"]},
        headers=hdrs,
    )
    assert st_429 == 429
    assert body_429.get("error") == "daily_limit_reached"
    assert body_429["quota"]["limit"] == 30
    assert body_429["quota"]["remaining"] == 0

    # Utility /help command MUST still work even at 30/30
    st_help, body_help = _http_json(
        f"{base}/api/chat",
        "POST",
        {"prompt": "/help", "thread_id": reg["default_thread_id"]},
        headers=hdrs,
    )
    assert st_help == 200 and "AURA" in body_help.get("reply", "")

    # Activate Tier 1 (60/24h): now 30 used / 60 limit -> 30 remaining!
    st_t1, res_t1 = _http_json(f"{base}/api/membership/activate", "POST", {"key": keys["tier_1"]}, headers=hdrs)
    assert st_t1 == 200 and res_t1["success"]
    assert res_t1["membership"]["id"] == "tier_1"
    assert res_t1["quota"]["limit"] == 60
    assert res_t1["quota"]["remaining"] == 30

    # Fill up to 60 -> #61 blocked on Tier 1
    for i in range(30):
        aura_db.record_chat_quota_event(uid, created_at=now - i)
    st_t1_61, body_t1_61 = _http_json(
        f"{base}/api/chat",
        "POST",
        {"prompt": "Another message", "thread_id": reg["default_thread_id"]},
        headers=hdrs,
    )
    assert st_t1_61 == 429 and body_t1_61["quota"]["limit"] == 60

    # Upgrade to Tier 3 (Sovereign · Unlimited): immediately unblocked even at 60 events!
    st_t3, res_t3 = _http_json(f"{base}/api/membership/activate", "POST", {"key": keys["tier_3"]}, headers=hdrs)
    assert st_t3 == 200 and res_t3["membership"]["unlimited"] is True
    assert res_t3["quota"]["blocked"] is False

    # Activate Tier 5 and verify signed membership_proof survives cold start (cleared settings_json)
    st_t5, res_t5 = _http_json(f"{base}/api/membership/activate", "POST", {"key": keys["tier_5"]}, headers=hdrs)
    assert st_t5 == 200 and res_t5["membership"]["id"] == "tier_5"
    proof = res_t5["membership"]["membership_proof"]
    assert proof.startswith("aura_mp1.")

    # Simulate cold container wipe of membership field in DB
    aura_db.save_user_settings(uid, {})
    st_rec, rec_body = _http_json(
        f"{base}/api/membership/status",
        "GET",
        headers={**hdrs, "X-Aura-Membership": proof},
    )
    assert st_rec == 200 and rec_body["membership"]["id"] == "tier_5"

    # Verify events older than 24h roll off automatically
    aura_db.save_user_settings(uid, {})
    conn = aura_db.get_connection()
    conn.execute("UPDATE chat_quota_events SET created_at = ? WHERE user_id = ?", (now - 90000, uid))
    conn.commit()
    conn.close()
    refreshed = aura_membership.get_user_quota_status(reg["user"])
    assert refreshed["used"] == 0 and refreshed["remaining"] == 30 and refreshed["blocked"] is False


def test_pro_studio_tiers_1_to_5_real_tools_and_guarded_os_popup(membership_server):
    base = membership_server["base_url"]
    keys = membership_server["test_keys"]

    st, reg = _http_json(f"{base}/api/auth/register", "POST", {"username": "apex_eng", "password": "ApexPass!2026"})
    assert st == 200
    hdrs = {"Authorization": f"Bearer {reg['token']}"}

    # Tier 0 is strictly gated out of Pro/Apex endpoints
    st_g1, _ = _http_json(f"{base}/api/pro/index", "GET", headers=hdrs)
    assert st_g1 == 403
    st_g5, _ = _http_json(f"{base}/api/pro/apex_execute", "POST", {"goal": "Build CLI"}, headers=hdrs)
    assert st_g5 == 403

    # Activate Tier 5 (unlocks Tiers 1–5)
    st_act, act = _http_json(f"{base}/api/membership/activate", "POST", {"key": keys["tier_5"]}, headers=hdrs)
    assert st_act == 200 and act["membership"]["rank"] == 5

    # Tier 3: Scaffolder creates real multi-file project + rollback snapshot
    st_sc, sc = _http_json(
        f"{base}/api/pro/scaffold",
        "POST",
        {"template": "fastapi_service", "project_name": "demo_api"},
        headers=hdrs,
    )
    assert st_sc == 200 and sc["success"] and sc["files_count"] >= 3 and sc["snapshot_id"]

    # Tier 1: AST & Symbol Indexer finds compute_health & ApiHandler + @file reader works
    st_idx, idx = _http_json(f"{base}/api/pro/index", "GET", headers=hdrs)
    assert st_idx == 200 and idx["workspace_files_count"] >= 3 and idx["total_symbols"] >= 2
    st_ctx, ctx = _http_json(f"{base}/api/pro/context_files", "POST", {"paths": ["demo_api/app.py"]}, headers=hdrs)
    assert st_ctx == 200 and "compute_health" in ctx["context_block"]

    # Tier 2: Polyglot Sandbox executes Python + SQL + JSON cleanly
    st_py, py_res = _http_json(
        f"{base}/api/pro/run_code",
        "POST",
        {"language": "python", "code": "print(sum(range(1, 11)))"},
        headers=hdrs,
    )
    assert st_py == 200 and py_res["success"] and "55" in py_res["stdout"]

    st_sql, sql_res = _http_json(
        f"{base}/api/pro/run_code",
        "POST",
        {"language": "sql", "code": "CREATE TABLE t (x INT); INSERT INTO t VALUES (10), (20); SELECT SUM(x) AS total FROM t;"},
        headers=hdrs,
    )
    assert st_sql == 200 and sql_res["success"] and sql_res["tables"][0]["rows"] == [[30]]

    # Tier 2: Multi-file Diff Apply + Rollback restores workspace cleanly
    st_ap, ap = _http_json(
        f"{base}/api/pro/apply_diff",
        "POST",
        {"edits": [{"path": "unsafe_sample.py", "content": "def run(x):\n    try:\n        return eval(x)\n    except:\n        return None\n"}]},
        headers=hdrs,
    )
    assert st_ap == 200 and ap["applied"] and ap["snapshot_id"]

    # Tier 4: Security AST Audit catches eval() and bare except in unsafe_sample.py
    st_sec, sec = _http_json(f"{base}/api/pro/security_audit", "POST", {}, headers=hdrs)
    assert st_sec == 200 and sec["findings_count"] >= 2
    assert any("eval/exec" in f["rule"] for f in sec["findings"])

    # Rollback removes unsafe_sample.py cleanly
    st_rb, rb = _http_json(f"{base}/api/pro/rollback", "POST", {"snapshot_id": ap["snapshot_id"]}, headers=hdrs)
    assert st_rb == 200 and "unsafe_sample.py" in rb["removed_new_files"]

    # Tier 3: Persistent .aura-rules saves cleanly
    st_rl, rl = _http_json(f"{base}/api/membership/rules", "POST", {"rules": "Always include type annotations and pytest tests."}, headers=hdrs)
    assert st_rl == 200 and "type annotations" in rl["aura_rules"]

    # Tier 4: Guarded Desktop/Laptop OS Automation — Mandatory Proposal -> DENY vs ALLOW
    st_prop, prop = _http_json(
        f"{base}/api/pro/os_action/propose",
        "POST",
        {
            "action_type": "create_workspace_note",
            "target": "ops_log.md",
            "reason": "Save a verified automation report into the workspace.",
        },
        headers=hdrs,
    )
    assert st_prop == 200 and prop["requires_approval"] is True
    ticket = prop["proposal"]["signed_ticket"]
    assert prop["proposal"]["reason"] == "Save a verified automation report into the workspace."
    assert prop["proposal"]["command"].startswith("workspace.write_file")

    # Clicking DENY executes nothing
    st_deny, deny_res = _http_json(
        f"{base}/api/pro/os_action/commit",
        "POST",
        {"signed_ticket": ticket, "decision": "DENY", "deny_note": "Not right now"},
        headers=hdrs,
    )
    assert st_deny == 200 and deny_res["executed"] is False and deny_res["decision"] == "DENIED"

    # Clicking ALLOW_ONCE executes cleanly
    st_ok, ok_res = _http_json(
        f"{base}/api/pro/os_action/commit",
        "POST",
        {"signed_ticket": ticket, "decision": "ALLOW_ONCE"},
        headers=hdrs,
    )
    assert st_ok == 200 and ok_res["executed"] is True and ok_res["decision"] == "ALLOWED"

    # Tampered approval ticket is rejected
    st_bad, _ = _http_json(
        f"{base}/api/pro/os_action/commit",
        "POST",
        {"signed_ticket": ticket[:-4] + "0000", "decision": "ALLOW_ONCE"},
        headers=hdrs,
    )
    assert st_bad == 400


def test_apex_omnis_6_stage_pipeline_auto_heals_broken_draft(tmp_path: Path):
    """Verifies Tier 5 Apex Omnis 6-stage pipeline detects a broken script, auto-heals it, and verifies green."""
    calls = {"n": 0}

    class _StubBrain:
        thinking_level = "minimal"
        def think_and_act(self, prompt, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return (
                    "```json\n"
                    + json.dumps({
                        "architecture": "Modular token bucket module with unit verification.",
                        "files": [
                            {"path": "bucket.py", "summary": "Token bucket logic", "content": "def add_tokens(a, b):\n    return a + b\n"},
                            {"path": "test_bucket.py", "summary": "Verification test", "content": "from bucket import add_tokens\nassert add_tokens(2, 3) == 999\n"},
                        ],
                    })
                    + "\n```"
                )
            return "```python\nfrom bucket import add_tokens\nassert add_tokens(2, 3) == 5\nprint('APEX_VERIFIED_OK')\n```"

    res = aura_pro_studio.run_apex_autonomous_pipeline(
        goal="Build a token bucket helper with unit tests",
        language="python",
        workspace_dir=tmp_path,
        brain=_StubBrain(),
        auto_apply=True,
    )
    assert res["success"] is True
    assert len(res["stages"]) == 6
    assert res["self_healed"] is True
    assert res["verification"]["success"] is True
    assert "APEX_VERIFIED_OK" in res["verification"]["stdout"]
    assert res["applied"] is True and res["snapshot_id"]
    assert (tmp_path / "bucket.py").exists() and (tmp_path / "test_bucket.py").exists()
