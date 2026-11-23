"""
Automated regression suite for AURA 3-Plan Subscription System, Dynamic Time-Limited
Cryptographic Key Engine (20-day / 30-day auto-expiry, renewal & disable kill-switch),
Exclusive Admin Key Vault (@ig.ahmed.irl), Rolling 24h Quotas (30 / 100 / 300 / Unlimited),
Pro / Apex Omnis Engineering Studio, and Multi-Chat Unlimited History Sync.
"""
from __future__ import annotations

import json
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
    monkeypatch.setenv("AURA_ADMIN_VAULT_PASSWORD", "UnitTestAdminVault!2026")
    aura_db._RUNTIME_SECRETS_CACHE.clear()

    db_file = tmp_path / "aura_mem_test.db"
    ws_root = tmp_path / "ws"
    ws_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(aura_db, "DB_PATH", db_file)
    monkeypatch.setattr(aura_web, "_resolve_workspace_dir", lambda uid=None: (ws_root / f"user_{int(uid)}" if uid is not None else ws_root))
    aura_db.init_database()

    server = ThreadingHTTPServer(("127.0.0.1", 0), aura_web.AuraWebHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        yield {
            "base_url": f"http://127.0.0.1:{port}",
            "admin_pw": "UnitTestAdminVault!2026",
            "tmp_path": tmp_path,
            "ws_root": ws_root,
        }
    finally:
        server.shutdown()
        server.server_close()


def test_3_flagship_plans_zero_plaintext_secrets_and_ui_wiring():
    tiers = aura_membership.list_public_tiers()
    paid = [t for t in tiers if t["rank"] >= 3]
    assert [t["id"] for t in paid] == ["tier_3", "tier_4", "tier_5"]
    # Plan 1: Rs.40, 20 days, 100 chats/day
    assert paid[0]["price_inr"] == 40
    assert paid[0]["duration_days"] == 20
    assert paid[0]["daily_limit"] == 100
    assert paid[0]["unlimited"] is False
    # Plan 2: Rs.99, 30 days, 300 chats/day (expanded over Plan 1)
    assert paid[1]["price_inr"] == 99
    assert paid[1]["duration_days"] == 30
    assert paid[1]["daily_limit"] == 300
    assert paid[1]["unlimited"] is False
    # Plan 3: Rs.199, 30 days, Unlimited
    assert paid[2]["price_inr"] == 199
    assert paid[2]["duration_days"] == 30
    assert paid[2]["unlimited"] is True

    # Legacy 15 big-tier hashes only (10 small tier_1/tier_2 hashes removed)
    assert len(aura_membership.ACTIVATION_KEY_HASHES) == 15
    assert all(m["tier_id"] in ("tier_3", "tier_4", "tier_5") for m in aura_membership.ACTIVATION_KEY_HASHES.values())

    # Zero plaintext activation keys or admin vault password leaked into tracked files
    root = Path(__file__).resolve().parent
    key_rx = re.compile(r"AURA-(?:VEL1|ARC2|SOV3|TTN4|APX5)-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}")
    for fname in ("aura_membership.py", "aura_pro_studio.py", "aura_web.py", "aura_db.py", "index.html"):
        txt = (root / fname).read_text(encoding="utf-8")
        assert not key_rx.search(txt), f"Plaintext activation key found in {fname}!"
        assert "Aa123123asss" not in txt, f"Plaintext admin vault password leaked in {fname}!"

    html = (root / "index.html").read_text(encoding="utf-8")
    assert 'id="membershipSettingsSection"' in html
    assert 'id="adminKeyVaultSection"' in html
    assert 'id="auraSubWelcomeOverlay"' in html
    assert 'id="sidebarSubCard"' in html
    assert "919640875528" in html and "+91 9640875528" in html
    assert "mergeThreadLists" in html and "_mergeVaultPayloads" in html


def test_exclusive_admin_vault_expiry_renewal_disable_and_quotas(membership_server):
    base = membership_server["base_url"]
    admin_pw = membership_server["admin_pw"]

    # Register normal user & exclusive admin user (ig.ahmed.irl)
    st_u, user_reg = _http_json(f"{base}/api/auth/register", "POST", {"username": "buyer_rahul", "password": "BuyerPass!2026"})
    assert st_u == 200 and user_reg["success"]
    u_hdrs = {"Authorization": f"Bearer {user_reg['token']}"}
    uid = user_reg["user"]["id"]

    st_u2, other_reg = _http_json(f"{base}/api/auth/register", "POST", {"username": "other_user", "password": "OtherPass!2026"})
    assert st_u2 == 200
    u2_hdrs = {"Authorization": f"Bearer {other_reg['token']}"}

    st_a, adm_reg = _http_json(f"{base}/api/auth/register", "POST", {"username": "ig.ahmed.irl", "password": "OwnerLogin!2026"})
    assert st_a == 200 and adm_reg["success"]
    a_hdrs = {"Authorization": f"Bearer {adm_reg['token']}"}

    # 1. Non-admin CANNOT unlock Admin Key Vault even with correct password
    st_forb, _ = _http_json(f"{base}/api/admin/keys/unlock", "POST", {"password": admin_pw}, headers=u_hdrs)
    assert st_forb == 403

    # 2. ig.ahmed.irl with wrong password is rejected
    st_badpw, _ = _http_json(f"{base}/api/admin/keys/unlock", "POST", {"password": "WrongPassword!"}, headers=a_hdrs)
    assert st_badpw == 403

    # 3. ig.ahmed.irl with correct password unlocks Admin Key Vault
    st_ok, unlock_res = _http_json(f"{base}/api/admin/keys/unlock", "POST", {"password": admin_pw}, headers=a_hdrs)
    assert st_ok == 200 and unlock_res["success"] and unlock_res["admin_vault_token"].startswith("aura_av1.")
    av_hdrs = {**a_hdrs, "X-Admin-Vault-Token": unlock_res["admin_vault_token"]}

    # 4. Admin generates Plan 1 (20 days), Plan 2 (30 days), Plan 3 (30 days)
    st_g1, g1 = _http_json(f"{base}/api/admin/keys/generate", "POST", {"tier_id": "tier_3", "duration_days": 20, "count": 1, "note": "Rahul ₹40 UPI"}, headers=av_hdrs)
    assert st_g1 == 200 and g1["generated_count"] == 1
    k1 = g1["keys"][0]["key_code"]
    assert k1.startswith("AURA-SOV-20D-")

    st_g2, g2 = _http_json(f"{base}/api/admin/keys/generate", "POST", {"tier_id": "tier_4", "duration_days": 30, "count": 1}, headers=av_hdrs)
    assert st_g2 == 200
    k2 = g2["keys"][0]["key_code"]
    assert k2.startswith("AURA-TTN-30D-")

    st_g3, g3 = _http_json(f"{base}/api/admin/keys/generate", "POST", {"tier_id": "tier_5", "duration_days": 30, "count": 1}, headers=av_hdrs)
    assert st_g3 == 200
    k3 = g3["keys"][0]["key_code"]
    assert k3.startswith("AURA-APX-30D-")

    # 5. Free Standard hits 30/30 daily quota -> 429
    now = time.time()
    for i in range(30):
        aura_db.record_chat_quota_event(uid, created_at=now - (30 - i))
    st_429, body_429 = _http_json(f"{base}/api/chat", "POST", {"prompt": "Hello", "thread_id": user_reg["default_thread_id"]}, headers=u_hdrs)
    assert st_429 == 429 and body_429["quota"]["limit"] == 30

    # Utility /help bypasses quota cleanly
    st_help, body_help = _http_json(f"{base}/api/chat", "POST", {"prompt": "/help", "thread_id": user_reg["default_thread_id"]}, headers=u_hdrs)
    assert st_help == 200 and "AURA" in body_help.get("reply", "")

    # 6. Buyer activates Plan 1 key (₹40 · 20d · 100 chats/day) -> Special Welcome payload + 100/day quota!
    st_act1, act1 = _http_json(f"{base}/api/membership/activate", "POST", {"key": k1}, headers=u_hdrs)
    assert st_act1 == 200 and act1["success"]
    assert act1["membership"]["id"] == "tier_3"
    assert act1["membership"]["days_remaining_int"] == 20
    assert act1["quota"]["limit"] == 100 and act1["quota"]["remaining"] == 70
    assert act1["welcome"]["plan_name"] == "AURA Sovereign"
    assert len(act1["welcome"]["unlocked_features"]) >= 5

    # 7. Another user CANNOT steal/reuse an already bound key
    st_steal, _ = _http_json(f"{base}/api/membership/activate", "POST", {"key": k1}, headers=u2_hdrs)
    assert st_steal == 400

    # 8. Simulate 20 days passing (key expires) -> User automatically drops to Free Standard (30/day)
    aura_db.update_subscription_key(k1, {"expires_at": now - 60})
    st_exp, exp_res = _http_json(f"{base}/api/membership/status", "GET", headers=u_hdrs)
    assert st_exp == 200
    assert exp_res["membership"]["id"] == "tier_0"
    assert exp_res["quota"]["limit"] == 30
    assert "9640875528" in exp_res["membership"]["expired_notice"]

    # Expired key cannot be re-activated by buyer before Admin renews
    st_re_exp, _ = _http_json(f"{base}/api/membership/activate", "POST", {"key": k1}, headers=u_hdrs)
    assert st_re_exp == 400

    # 9. Admin RENEWS the exact same key (and upgrades to Plan 2: 300/day · 30d) after payment arrives!
    st_ren, ren_res = _http_json(f"{base}/api/admin/keys/renew", "POST", {"key_code": k1, "tier_id": "tier_4", "duration_days": 30}, headers=av_hdrs)
    assert st_ren == 200 and ren_res["success"] and ren_res["key"]["renew_count"] == 1

    # Buyer is IMMEDIATELY reactivated at Plan 2 (300/day) without even needing a new key!
    st_back, back_res = _http_json(f"{base}/api/membership/status", "GET", headers=u_hdrs)
    assert st_back == 200 and back_res["membership"]["id"] == "tier_4"
    assert back_res["quota"]["limit"] == 300 and back_res["membership"]["days_remaining_int"] == 30

    # 10. Admin DISABLE kill-switch immediately revokes buyer's access
    st_dis, dis_res = _http_json(f"{base}/api/admin/keys/toggle", "POST", {"key_code": k1, "disable": True}, headers=av_hdrs)
    assert st_dis == 200 and dis_res["key"]["status"] == "disabled"
    st_after_dis, after_dis = _http_json(f"{base}/api/membership/status", "GET", headers=u_hdrs)
    assert st_after_dis == 200 and after_dis["membership"]["id"] == "tier_0"

    # 11. Plan 3 (Apex Omnis Unlimited) + cold-start proof recovery
    st_p3, act3 = _http_json(f"{base}/api/membership/activate", "POST", {"key": k3}, headers=u_hdrs)
    assert st_p3 == 200 and act3["membership"]["unlimited"] is True and act3["quota"]["blocked"] is False
    proof = act3["membership"]["membership_proof"]
    assert proof.startswith("aura_mp1.")
    aura_db.save_user_settings(uid, {})
    st_rec, rec_body = _http_json(f"{base}/api/membership/status", "GET", headers={**u_hdrs, "X-Aura-Membership": proof})
    assert st_rec == 200 and rec_body["membership"]["id"] == "tier_5"

    # 12. Admin list endpoint returns clean KPI summary
    st_lst, lst_body = _http_json(f"{base}/api/admin/keys/list", "GET", headers=av_hdrs)
    assert st_lst == 200 and lst_body["summary"]["total"] >= 3 and lst_body["summary"]["disabled"] >= 1


def test_pro_studio_3_plan_gating_and_guarded_os_popup(membership_server):
    base = membership_server["base_url"]
    admin_pw = membership_server["admin_pw"]

    st_a, adm = _http_json(f"{base}/api/auth/register", "POST", {"username": "ig.ahmed.irl", "password": "OwnerPass!2026"})
    assert st_a == 200
    st_u, un = _http_json(f"{base}/api/admin/keys/unlock", "POST", {"password": admin_pw}, headers={"Authorization": f"Bearer {adm['token']}"})
    assert st_u == 200
    av_hdrs = {"Authorization": f"Bearer {adm['token']}", "X-Admin-Vault-Token": un["admin_vault_token"]}

    _, g_p1 = _http_json(f"{base}/api/admin/keys/generate", "POST", {"tier_id": "tier_3", "duration_days": 20}, headers=av_hdrs)
    _, g_p3 = _http_json(f"{base}/api/admin/keys/generate", "POST", {"tier_id": "tier_5", "duration_days": 30}, headers=av_hdrs)
    key_p1 = g_p1["keys"][0]["key_code"]
    key_p3 = g_p3["keys"][0]["key_code"]

    st, reg = _http_json(f"{base}/api/auth/register", "POST", {"username": "apex_eng", "password": "ApexPass!2026"})
    assert st == 200
    hdrs = {"Authorization": f"Bearer {reg['token']}"}

    # Free Standard is strictly gated out of Pro/Apex endpoints
    assert _http_json(f"{base}/api/pro/index", "GET", headers=hdrs)[0] == 403
    assert _http_json(f"{base}/api/pro/apex_execute", "POST", {"goal": "Build CLI"}, headers=hdrs)[0] == 403

    # Plan 1 (Sovereign ₹40) unlocks HALF of flagship suite (Index, Scaffold, Sandbox, Diffs, Rules) while Plan 2/3 stay locked!
    st_p1, _ = _http_json(f"{base}/api/membership/activate", "POST", {"key": key_p1}, headers=hdrs)
    assert st_p1 == 200
    st_sc, sc = _http_json(f"{base}/api/pro/scaffold", "POST", {"template": "fastapi_service", "project_name": "demo_api"}, headers=hdrs)
    assert st_sc == 200 and sc["success"] and sc["files_count"] >= 3
    st_idx, idx = _http_json(f"{base}/api/pro/index", "GET", headers=hdrs)
    assert st_idx == 200 and idx["workspace_files_count"] >= 3
    st_py, py_res = _http_json(f"{base}/api/pro/run_code", "POST", {"language": "python", "code": "print(sum(range(1, 11)))"}, headers=hdrs)
    assert st_py == 200 and "55" in py_res["stdout"]
    # Plan 2 (Security Audit / OS Action) & Plan 3 (Apex Execute) MUST still be locked on Plan 1!
    assert _http_json(f"{base}/api/pro/security_audit", "POST", {}, headers=hdrs)[0] == 403
    assert _http_json(f"{base}/api/pro/apex_execute", "POST", {"goal": "Build CLI"}, headers=hdrs)[0] == 403

    # Upgrade to Plan 3 (Apex Omnis ₹199) -> unlocks 100% ALL features!
    st_act, act = _http_json(f"{base}/api/membership/activate", "POST", {"key": key_p3}, headers=hdrs)
    assert st_act == 200 and act["membership"]["rank"] == 5

    st_ctx, ctx = _http_json(f"{base}/api/pro/context_files", "POST", {"paths": ["demo_api/app.py"]}, headers=hdrs)
    assert st_ctx == 200 and "compute_health" in ctx["context_block"]

    st_sql, sql_res = _http_json(f"{base}/api/pro/run_code", "POST", {"language": "sql", "code": "CREATE TABLE t (x INT); INSERT INTO t VALUES (10), (20); SELECT SUM(x) AS total FROM t;"}, headers=hdrs)
    assert st_sql == 200 and sql_res["tables"][0]["rows"] == [[30]]

    st_ap, ap = _http_json(f"{base}/api/pro/apply_diff", "POST", {"edits": [{"path": "unsafe_sample.py", "content": "def run(x):\n    try:\n        return eval(x)\n    except:\n        return None\n"}]}, headers=hdrs)
    assert st_ap == 200 and ap["applied"] and ap["snapshot_id"]

    st_sec, sec = _http_json(f"{base}/api/pro/security_audit", "POST", {}, headers=hdrs)
    assert st_sec == 200 and sec["findings_count"] >= 2
    assert any("eval/exec" in f["rule"] for f in sec["findings"])

    st_rb, rb = _http_json(f"{base}/api/pro/rollback", "POST", {"snapshot_id": ap["snapshot_id"]}, headers=hdrs)
    assert st_rb == 200 and "unsafe_sample.py" in rb["removed_new_files"]

    st_rl, rl = _http_json(f"{base}/api/membership/rules", "POST", {"rules": "Always include type annotations and pytest tests."}, headers=hdrs)
    assert st_rl == 200 and "type annotations" in rl["aura_rules"]

    # Guarded OS Automation Proposal -> DENY vs ALLOW
    st_prop, prop = _http_json(f"{base}/api/pro/os_action/propose", "POST", {"action_type": "create_workspace_note", "target": "ops_log.md", "reason": "Save verified report."}, headers=hdrs)
    assert st_prop == 200 and prop["requires_approval"] is True
    ticket = prop["proposal"]["signed_ticket"]
    st_deny, deny_res = _http_json(f"{base}/api/pro/os_action/commit", "POST", {"signed_ticket": ticket, "decision": "DENY"}, headers=hdrs)
    assert st_deny == 200 and deny_res["executed"] is False
    st_ok, ok_res = _http_json(f"{base}/api/pro/os_action/commit", "POST", {"signed_ticket": ticket, "decision": "ALLOW_ONCE"}, headers=hdrs)
    assert st_ok == 200 and ok_res["executed"] is True
    assert _http_json(f"{base}/api/pro/os_action/commit", "POST", {"signed_ticket": ticket[:-4] + "0000", "decision": "ALLOW_ONCE"}, headers=hdrs)[0] == 400


def test_unlimited_multi_chat_history_sync_preserves_all_threads(membership_server):
    """Verifies creating 6+ separate chats and syncing across container cold starts retains EVERY chat (never just 1)."""
    base = membership_server["base_url"]
    st, reg = _http_json(f"{base}/api/auth/register", "POST", {"username": "history_tester", "password": "HistPass!2026"})
    assert st == 200
    hdrs = {"Authorization": f"Bearer {reg['token']}"}
    uid = reg["user"]["id"]

    # Create 6 distinct chats with messages
    for idx in range(1, 7):
        tid = f"th_multi_{idx}"
        aura_db.save_message(uid, tid, "user", f"Conversation topic number {idx}")
        aura_db.save_message(uid, tid, "assistant", f"Detailed reply for topic {idx}")

    st_t, t_body = _http_json(f"{base}/api/threads", "GET", headers=hdrs)
    assert st_t == 200 and len(t_body["threads"]) >= 6

    # Export vault, wipe DB threads to simulate cold Vercel container with only 1 new thread, then sync!
    vault = aura_db.export_user_vault(uid)
    assert len(vault["payload"]["threads"]) >= 6
    conn = aura_db.get_connection()
    conn.execute("DELETE FROM messages WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM threads WHERE user_id = ?", (uid,))
    conn.commit()
    conn.close()
    aura_db.save_message(uid, "th_multi_7", "user", "Brand new chat on cold container 7")
    aura_db.save_message(uid, "th_multi_7", "assistant", "Cold container reply 7")

    st_sync, sync_res = _http_json(
        f"{base}/api/threads/sync",
        "POST",
        {
            "username": "history_tester",
            "threads": vault["payload"]["threads"],
            "messages": vault["payload"]["messages"],
        },
        headers=hdrs,
    )
    assert st_sync == 200 and sync_res["success"]
    all_ids = {t["id"] for t in sync_res["threads"]}
    for idx in range(1, 8):
        assert f"th_multi_{idx}" in all_ids


def test_apex_omnis_6_stage_pipeline_auto_heals_broken_draft(tmp_path: Path):
    """Verifies Plan 3 Apex Omnis 6-stage pipeline detects a broken script, auto-heals it, and verifies green."""
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


def test_admin_command_center_users_timed_keys_gift_renew_ban_and_audit(membership_server):
    """
    End-to-end verification of the Owner Admin Command Center (@ig.ahmed.irl):
    - Real users directory, login_count & device tracking
    - Minute/Hour/Day timed keys & fixed_now auto-expiration (stops working automatically)
    - 1-click Free Gift subscription, direct user renewal, and subscription stop/revoke
    - Instant user Ban (kills live session + blocks login with 403), Owner self-ban protection, and Unban
    - Key deletion & Admin Audit Log + strict 403 isolation for non-admins
    """
    base = membership_server["base_url"]
    admin_pw = membership_server["admin_pw"]

    # Register owner & 2 real users with distinct devices
    st_a, adm = _http_json(
        f"{base}/api/auth/register",
        "POST",
        {"username": "ig.ahmed.irl", "password": "OwnerLogin!2026"},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    assert st_a == 200 and adm["success"]
    a_hdrs = {"Authorization": f"Bearer {adm['token']}"}

    st_u1, u1 = _http_json(
        f"{base}/api/auth/register",
        "POST",
        {"username": "real_user_zayd", "password": "ZaydPass!2026"},
        headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) Mobile"},
    )
    assert st_u1 == 200 and u1["success"]
    u1_hdrs = {"Authorization": f"Bearer {u1['token']}"}

    # Log u1 in a second time to verify login_count increments
    st_u1_login, u1_re = _http_json(
        f"{base}/api/auth/login",
        "POST",
        {"username": "real_user_zayd", "password": "ZaydPass!2026"},
        headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) Mobile"},
    )
    assert st_u1_login == 200 and u1_re["success"]
    u1_hdrs = {"Authorization": f"Bearer {u1_re['token']}"}

    st_u2, u2 = _http_json(
        f"{base}/api/auth/register",
        "POST",
        {"username": "real_user_sara", "password": "SaraPass!2026"},
        headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)"},
    )
    assert st_u2 == 200 and u2["success"]
    u2_hdrs = {"Authorization": f"Bearer {u2['token']}"}

    # Unlock Admin Vault as @ig.ahmed.irl
    st_un, un = _http_json(f"{base}/api/admin/keys/unlock", "POST", {"password": admin_pw}, headers=a_hdrs)
    assert st_un == 200 and un["success"]
    av_hdrs = {**a_hdrs, "X-Admin-Vault-Token": un["admin_vault_token"]}

    # 1. Strict 403 isolation: non-admin cannot access any new Admin Command Center endpoint
    for method, ep, payload in (
        ("GET", "/api/admin/users/list", None),
        ("GET", "/api/admin/audit/list", None),
        ("POST", "/api/admin/users/gift", {"username": "real_user_sara", "tier_id": "tier_5", "duration_value": 30, "duration_unit": "minutes"}),
        ("POST", "/api/admin/users/renew", {"username": "real_user_sara", "tier_id": "tier_4", "duration_value": 2, "duration_unit": "hours"}),
        ("POST", "/api/admin/users/revoke", {"username": "real_user_sara"}),
        ("POST", "/api/admin/users/ban", {"username": "real_user_sara", "banned": True}),
        ("POST", "/api/admin/keys/delete", {"key_code": "AURA-SOV-20D-XXXXXX-12345678"}),
    ):
        st_f, _ = _http_json(f"{base}{ep}", method, payload, headers=u1_hdrs)
        assert st_f == 403, f"Expected 403 for non-admin on {ep}, got {st_f}"

    # 2. Real Users Directory shows exact usernames, device labels, and login counts
    st_ul, ul = _http_json(f"{base}/api/admin/users/list", "GET", headers=av_hdrs)
    assert st_ul == 200 and ul["success"]
    assert ul["summary"]["total_users"] == 3
    by_name = {row["username"]: row for row in ul["users"]}
    assert "real_user_zayd" in by_name and "real_user_sara" in by_name and "ig.ahmed.irl" in by_name
    assert by_name["real_user_zayd"]["login_count"] >= 2
    assert "Android" in by_name["real_user_zayd"]["last_device"]
    assert "iPhone" in by_name["real_user_sara"]["last_device"]

    # 3. Minute & Hour Timed Keys + fixed_now automatic expiration even before redemption
    st_gm, gm = _http_json(
        f"{base}/api/admin/keys/generate",
        "POST",
        {"tier_id": "tier_5", "duration_value": 30, "duration_unit": "minutes", "timer_mode": "fixed_now", "note": "30-min flash trial"},
        headers=av_hdrs,
    )
    assert st_gm == 200 and gm["success"]
    km = gm["keys"][0]["key_code"]
    assert km.startswith("AURA-APX-30M-")
    assert gm["keys"][0]["duration_seconds"] == 1800
    assert gm["keys"][0]["timer_mode"] == "fixed_now"
    assert gm["keys"][0]["expires_at"] is not None

    # Simulate the 30-minute fixed timer ending before anyone redeems -> key automatically stops working!
    aura_db.update_subscription_key(km, {"expires_at": time.time() - 5})
    st_dead, dead_res = _http_json(f"{base}/api/membership/activate", "POST", {"key": km}, headers=u2_hdrs)
    assert st_dead == 400 and "expired" in dead_res["error"].lower()

    # Hour key (6H) works on activation and has ~6h remaining
    st_gh, gh = _http_json(
        f"{base}/api/admin/keys/generate",
        "POST",
        {"tier_id": "tier_4", "duration_value": 6, "duration_unit": "hours", "timer_mode": "on_activation"},
        headers=av_hdrs,
    )
    assert st_gh == 200 and gh["keys"][0]["key_code"].startswith("AURA-TTN-6H-")
    kh = gh["keys"][0]["key_code"]
    st_act_h, act_h = _http_json(f"{base}/api/membership/activate", "POST", {"key": kh}, headers=u2_hdrs)
    assert st_act_h == 200 and act_h["membership"]["id"] == "tier_4"
    assert 5 * 3600 < act_h["membership"]["seconds_remaining"] <= 6 * 3600

    # 4. 1-Click Direct Free Gift Subscription to @real_user_zayd (no key paste needed!)
    st_gift, gift_res = _http_json(
        f"{base}/api/admin/users/gift",
        "POST",
        {"username": "real_user_zayd", "tier_id": "tier_5", "duration_value": 2, "duration_unit": "hours", "note": "Best friend VIP gift"},
        headers=av_hdrs,
    )
    assert st_gift == 200 and gift_res["success"]
    st_z_mem, z_mem = _http_json(f"{base}/api/membership/status", "GET", headers=u1_hdrs)
    assert st_z_mem == 200 and z_mem["membership"]["id"] == "tier_5"
    assert z_mem["membership"]["is_gift"] is True
    assert z_mem["quota"]["unlimited"] is True

    # 5. 1-Click Direct User Renewal (+4 hours) & Stop/Revoke Plan
    st_uren, uren = _http_json(
        f"{base}/api/admin/users/renew",
        "POST",
        {"username": "real_user_zayd", "tier_id": "tier_5", "duration_value": 4, "duration_unit": "hours"},
        headers=av_hdrs,
    )
    assert st_uren == 200 and uren["success"]
    st_z2, z2 = _http_json(f"{base}/api/membership/status", "GET", headers=u1_hdrs)
    assert st_z2 == 200 and z2["membership"]["seconds_remaining"] > 5 * 3600

    st_rev, rev_res = _http_json(f"{base}/api/admin/users/revoke", "POST", {"username": "real_user_zayd"}, headers=av_hdrs)
    assert st_rev == 200 and rev_res["success"]
    st_z3, z3 = _http_json(f"{base}/api/membership/status", "GET", headers=u1_hdrs)
    assert st_z3 == 200 and z3["membership"]["id"] == "tier_0"

    # 6. Ban User -> instant live session kickout + 403 login block + Owner self-ban protection + Unban
    st_selfban, selfban = _http_json(
        f"{base}/api/admin/users/ban",
        "POST",
        {"username": "ig.ahmed.irl", "banned": True, "reason": "test"},
        headers=av_hdrs,
    )
    assert st_selfban == 400 and "cannot be banned" in selfban["error"].lower()

    st_ban, ban_res = _http_json(
        f"{base}/api/admin/users/ban",
        "POST",
        {"username": "real_user_zayd", "banned": True, "reason": "Terms violation"},
        headers=av_hdrs,
    )
    assert st_ban == 200 and ban_res["success"] and ban_res["is_banned"] is True

    # Active session is IMMEDIATELY kicked out (401)
    st_kicked, _ = _http_json(f"{base}/api/membership/status", "GET", headers=u1_hdrs)
    assert st_kicked == 401

    # Fresh login is BLOCKED with 403 and displays ban reason
    st_blocked_login, bl = _http_json(
        f"{base}/api/auth/login",
        "POST",
        {"username": "real_user_zayd", "password": "ZaydPass!2026"},
    )
    assert st_blocked_login == 403 and bl.get("banned") is True and "Terms violation" in bl.get("error", "")

    # Unban restores account access cleanly
    st_unban, unban_res = _http_json(
        f"{base}/api/admin/users/ban",
        "POST",
        {"username": "real_user_zayd", "banned": False},
        headers=av_hdrs,
    )
    assert st_unban == 200 and unban_res["success"] and unban_res["is_banned"] is False
    st_relogin, relogin = _http_json(
        f"{base}/api/auth/login",
        "POST",
        {"username": "real_user_zayd", "password": "ZaydPass!2026"},
    )
    assert st_relogin == 200 and relogin["success"]

    # 7. Delete Key & Audit Logs
    st_del, del_res = _http_json(f"{base}/api/admin/keys/delete", "POST", {"key_code": km}, headers=av_hdrs)
    assert st_del == 200 and del_res["success"]
    assert aura_db.get_subscription_key_by_code(km) is None

    st_aud, aud_res = _http_json(f"{base}/api/admin/audit/list", "GET", headers=av_hdrs)
    assert st_aud == 200 and aud_res["success"] and len(aud_res["logs"]) >= 6
    actions_logged = {l["action"] for l in aud_res["logs"]}
    assert {"key_generated", "gift_key_created", "user_banned", "user_unbanned", "key_deleted"}.issubset(actions_logged)

    # 8. Verify Admin Command Center UI wiring in index.html
    html = (Path(__file__).resolve().parent / "index.html").read_text(encoding="utf-8")
    for marker in (
        'id="auraAdminCenterOverlay"',
        'id="headerAdminBtn"',
        'id="sidebarAdminBtn"',
        "openAdminCommandCenter",
        "adminCenterGenerateKeysFromUI",
        "submitAdminUserPlanAction",
        "submitAdminBanUser",
        "adminDeleteKey",
    ):
        assert marker in html, f"Missing Admin Command Center UI hook: {marker}"
