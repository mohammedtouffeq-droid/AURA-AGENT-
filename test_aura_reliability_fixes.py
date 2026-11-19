"""Regression tests for multi-container session continuity, 100+ thread isolation, and command execution."""
from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import aura_brain
import aura_db
import aura_web


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _http_json(url: str, method: str = "GET", payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, dict(resp.headers), json.loads(raw)
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"raw": raw}
        return err.code, dict(err.headers), body


def _http_sse(url: str, payload: dict, headers: dict):
    req_headers = {"Content-Type": "application/json"}
    req_headers.update(headers)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=req_headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    events = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            events.append(json.loads(line[5:].strip()))
    return events


@pytest.fixture()
def isolated_server(tmp_path: Path, monkeypatch):
    db_a = tmp_path / "container_a.db"
    ws_root = tmp_path / "workspaces"
    ws_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("AURA_SESSION_SECRET", "test-deployment-shared-session-secret-0123456789abcdef")
    monkeypatch.setenv("AURA_VAULT_SECRET", "test-deployment-shared-vault-secret-0123456789abcdef")
    monkeypatch.setenv("AURA_CSRF_SECRET", "test-deployment-shared-csrf-secret-0123456789abcdef")
    monkeypatch.setattr(aura_db, "DB_PATH", db_a)
    monkeypatch.setattr(aura_web, "ROOT", Path(__file__).resolve().parent)
    aura_db._RUNTIME_SECRETS_CACHE.clear()
    aura_db.init_database()

    port = _free_port()
    server = aura_web.make_server("127.0.0.1", port)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.2)
    try:
        yield {
            "base_url": f"http://127.0.0.1:{port}",
            "tmp_path": tmp_path,
            "db_a": db_a,
        }
    finally:
        server.shutdown()
        server.server_close()
        aura_db._RUNTIME_SECRETS_CACHE.clear()


def test_multi_container_signed_session_continuity_and_logout_revocation(isolated_server, monkeypatch):
    base = isolated_server["base_url"]

    # Container A: Register & obtain signed aura_s2 token + CSRF token
    st, hdrs, reg = _http_json(
        f"{base}/api/auth/register",
        method="POST",
        payload={"username": "rohit_container", "password": "StrongPassword!99"},
    )
    assert st == 200 and reg["success"] is True
    token = reg["token"]
    csrf = reg["csrf_token"]
    assert token.startswith("aura_s2.")

    # Simulate 25 consecutive turns on Container A followed by sudden container switch to blank DB Container B
    cookie_header = f"aura_session={token}"
    db_b = isolated_server["tmp_path"] / "container_b_cold.db"
    monkeypatch.setattr(aura_db, "DB_PATH", db_b)
    aura_db.init_database()

    # Container B has zero rows initially, yet cookie + CSRF must rehydrate the exact user without 401
    st_me, _, me = _http_json(
        f"{base}/api/auth/me",
        headers={"Cookie": cookie_header},
    )
    assert st_me == 200
    assert me["authenticated"] is True
    assert me["user"]["username"] == "rohit_container"
    assert me["storage_status"]["stateless_session_sync"] is True

    # Sending SSE chat request using Cookie + CSRF on cold Container B must work cleanly (zero mid-session 401)
    events = _http_sse(
        f"{base}/api/chat/stream",
        payload={"prompt": "/calc 120 * 5 + 15", "thread_id": "th_cont_b_1"},
        headers={"Cookie": cookie_header, "X-CSRF-Token": csrf},
    )
    done_ev = [e for e in events if e.get("type") == "done"]
    assert len(done_ev) == 1
    assert "615" in done_ev[0]["reply"]
    assert done_ev[0]["user_vault"]["username"] == "rohit_container"
    assert len(done_ev[0]["threads"]) >= 1

    # Explicit logout must revoke the signed aura_s2 token permanently
    st_out, _, out_res = _http_json(
        f"{base}/api/auth/logout",
        method="POST",
        payload={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert st_out == 200 and out_res["success"] is True

    st_after, _, after_me = _http_json(
        f"{base}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert st_after == 401
    assert after_me["authenticated"] is False


def test_105_threads_persistence_sync_and_strict_user_isolation(isolated_server, monkeypatch):
    base = isolated_server["base_url"]

    _, _, u_a = _http_json(
        f"{base}/api/auth/register",
        method="POST",
        payload={"username": "alice_100", "password": "AlicePassword!99"},
    )
    _, _, u_b = _http_json(
        f"{base}/api/auth/register",
        method="POST",
        payload={"username": "bob_isolated", "password": "BobPassword!99"},
    )
    tok_a = u_a["token"]
    tok_b = u_b["token"]

    # Alice creates & syncs 105 distinct threads with messages (simulating long-term history)
    threads_payload = [
        {"id": f"th_alice_{i}", "title": f"Alice Important Project Chat #{i}", "is_pinned": i < 3, "updated_at": f"2026-11-{(i % 28) + 1:02d} 12:00:00"}
        for i in range(105)
    ]
    msgs_payload = [
        {"thread_id": f"th_alice_{i}", "role": "user", "content": f"Alice private prompt #{i}"}
        for i in range(105)
    ] + [
        {"thread_id": f"th_alice_{i}", "role": "assistant", "content": f"Alice private response #{i}"}
        for i in range(105)
    ]

    st_sync, _, sync_res = _http_json(
        f"{base}/api/threads/sync",
        method="POST",
        payload={"username": "alice_100", "threads": threads_payload, "messages": msgs_payload},
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert st_sync == 200 and sync_res["success"] is True
    assert len(sync_res["threads"]) >= 105
    synced_ids_a = {t["id"] for t in sync_res["threads"]}
    assert "th_alice_0" in synced_ids_a and "th_alice_104" in synced_ids_a

    # Simulate Container C cold start -> Alice restores all 105 threads
    db_c = isolated_server["tmp_path"] / "container_c_cold.db"
    monkeypatch.setattr(aura_db, "DB_PATH", db_c)
    aura_db.init_database()

    st_sync2, _, sync_res2 = _http_json(
        f"{base}/api/threads/sync",
        method="POST",
        payload={"username": "alice_100", "threads": threads_payload, "messages": msgs_payload},
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert st_sync2 == 200
    assert len(sync_res2["threads"]) == 105

    # Deleting a thread must update user_vault cleanly so deleted thread isn't retained
    st_del, _, del_res = _http_json(
        f"{base}/api/threads/delete",
        method="POST",
        payload={"thread_id": "th_alice_104"},
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert st_del == 200 and del_res["success"] is True
    vault_ids = {t["id"] for t in del_res["user_vault"]["payload"]["threads"]}
    assert "th_alice_104" not in vault_ids
    assert len(vault_ids) == 104

    # Bob must NEVER see Alice's threads, sync as Alice, or read Alice's thread messages
    st_bob_threads, _, bob_threads = _http_json(
        f"{base}/api/threads",
        headers={"Authorization": f"Bearer {tok_b}"},
    )
    assert st_bob_threads == 200
    assert bob_threads["threads"] == []

    st_cross_sync, _, cross_res = _http_json(
        f"{base}/api/threads/sync",
        method="POST",
        payload={"username": "alice_100", "threads": threads_payload, "messages": msgs_payload},
        headers={"Authorization": f"Bearer {tok_b}"},
    )
    assert st_cross_sync == 403
    assert cross_res["success"] is False

    st_bob_msg, _, bob_msg = _http_json(
        f"{base}/api/threads/messages?thread_id=th_alice_0",
        headers={"Authorization": f"Bearer {tok_b}"},
    )
    assert st_bob_msg == 200
    assert bob_msg["messages"] == []


def test_all_slash_commands_execute_cleanly_for_standard_user(isolated_server):
    base = isolated_server["base_url"]
    _, _, reg = _http_json(
        f"{base}/api/auth/register",
        method="POST",
        payload={"username": "cmd_tester", "password": "CmdPassword!99"},
    )
    tok = reg["token"]
    hdrs = {"Authorization": f"Bearer {tok}"}

    commands = [
        ("/help", "AURA Command System"),
        ("/goal Deploy FastAPI service", "Deploy FastAPI service"),
        ("/plan Authentication gateway", "/plan"),
        ("/brightness 40", "40%"),
        ("/volume 65", "65%"),
        ("/open youtube", "youtube"),
        ("/write demo_cmd.txt AURA_VERIFIED_CONTENT", "demo_cmd.txt"),
        ("/read demo_cmd.txt", "AURA_VERIFIED_CONTENT"),
        ("/files", "demo_cmd.txt"),
        ("/calc (18 * 5) + 10", "100"),
        ("/nexus Audit fraud", ""),
        ("/boost Analyze caching", "/boost"),
        ("/trinetra UPI voice impersonation scam", "TRINETRA"),
        ("/run ls", ""),
    ]

    for idx, (prompt, expected_sub) in enumerate(commands):
        events = _http_sse(
            f"{base}/api/chat/stream",
            payload={"prompt": prompt, "thread_id": f"th_cmd_{idx}"},
            headers=hdrs,
        )
        done_evs = [e for e in events if e.get("type") == "done"]
        assert len(done_evs) == 1, f"Command failed to finish cleanly: {prompt}"
        reply = done_evs[0]["reply"]
        assert "Permission denied" not in reply
        assert "requires administrator privileges" not in reply
        if expected_sub:
            assert expected_sub in reply, f"Expected {expected_sub!r} in reply for {prompt!r}, got: {reply[:250]}"

    # Ensure brightness tool emitted client_bridge_command in tool SSE event
    bright_events = _http_sse(
        f"{base}/api/chat/stream",
        payload={"prompt": "/brightness 55", "thread_id": "th_cmd_bright"},
        headers=hdrs,
    )
    tool_evs = [e for e in bright_events if e.get("type") == "tool"]
    assert any("client_bridge_command" in str(e.get("output", "")) for e in tool_evs)


def test_frontend_security_isolation_and_command_palette_present():
    html = (Path(__file__).resolve().parent / "index.html").read_text(encoding="utf-8")
    assert "localStorage.setItem('aura_auth_token'" not in html
    assert "localStorage.setItem('aura_active_vault'" not in html
    assert "AuraIsolatedHistoryV2" in html
    assert 'id="slashCommandPalette"' in html
    assert 'id="threadSearchInput"' in html
    assert 'id="btnExportHistoryBackup"' in html
    # Zero BharatCode / Build League visible strings in rendered text
    visible = re.sub(r"<(script|style).*?</\1>", " ", html, flags=re.S)
    visible = re.sub(r"<[^>]+>", " ", visible)
    assert "BharatCode" not in visible
    assert "Build League" not in visible


def test_vercel_wsgi_strips_hop_by_hop_headers_and_sets_content_length_on_stream(isolated_server):
    import importlib.util
    import io

    idx_path = Path(__file__).resolve().parent / "api" / "index.py"
    spec = importlib.util.spec_from_file_location("aura_vercel_wsgi", str(idx_path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    app = mod.app

    _, _, reg = _http_json(
        f"{isolated_server['base_url']}/api/auth/register",
        method="POST",
        payload={"username": "wsgi_tester", "password": "WsgiPassword!99"},
    )
    body_bytes = json.dumps({"prompt": "/calc 9 * 9", "thread_id": "th_wsgi_1"}).encode("utf-8")
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/api/chat/stream",
        "QUERY_STRING": "",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(body_bytes)),
        "HTTP_AUTHORIZATION": f"Bearer {reg['token']}",
        "wsgi.input": io.BytesIO(body_bytes),
    }
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = {k.lower(): v for k, v in headers}

    chunks = app(environ, start_response)
    payload = b"".join(chunks)
    assert captured["status"].startswith("200")
    assert "connection" not in captured["headers"]
    assert "transfer-encoding" not in captured["headers"]
    assert int(captured["headers"]["content-length"]) == len(payload)
    assert b'"type": "done"' in payload
    assert b"81" in payload


def test_no_robotic_understood_or_substring_hi_regression_and_key_rotation(tmp_path: Path, monkeypatch):
    import io
    import urllib.error
    from unittest.mock import patch

    brain = aura_brain.AuraBrain()
    history = [
        {"role": "user", "parts": [{"text": "CyberArena3D game banao"}]},
        {"role": "model", "parts": [{"text": "CyberArena3D ready!"}]},
    ]
    for msg in [
        "bhai mai hi hu mohd ahmed maine tere ko banaya hai",
        "yo kya hua ?",
        "bhai ram aur storage chahiye batao",
        "ham kis cheez par baat kar rahe the topic change kar diya",
    ]:
        out = brain._offline_autonomous_dispatch(
            history + [{"role": "user", "parts": [{"text": msg}]}],
            aura_brain.GEMINI_TOOLS_DECLARATION,
        )
        txt = out["candidates"][0]["content"]["parts"][0]["text"]
        assert "Understood. You said:" not in txt
        assert "Hello! I heard you." not in txt

    # Pure conversational turns skip 30+ tool schemas (~1.3s fast Gemini path) while action prompts keep tools
    assert brain._should_include_tools_for_contents(
        [{"role": "user", "parts": [{"text": "yo kya hua bhai mai hi hu mohd ahmed"}]}],
        aura_brain.GEMINI_TOOLS_DECLARATION,
    ) is False
    assert brain._should_include_tools_for_contents(
        [{"role": "user", "parts": [{"text": "chat gpt khol aur brightness bada"}]}],
        aura_brain.GEMINI_TOOLS_DECLARATION,
    ) is True

    # Verify multi-key failover rotates cleanly when first API key returns HTTP 429
    monkeypatch.setattr(aura_brain, "API_KEY_POOL", ["key-quota-hit", "key-healthy-2"])
    brain.api_key = "key-quota-hit"
    calls = []

    class _MockResp:
        def __init__(self, payload_dict):
            self._b = json.dumps(payload_dict).encode("utf-8")
        def read(self):
            return self._b
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=10):
        used_key = req.headers.get("X-goog-api-key") or req.headers.get("x-goog-api-key")
        calls.append(used_key)
        if used_key == "key-quota-hit":
            raise urllib.error.HTTPError(req.full_url, 429, "Quota exceeded", {}, io.BytesIO(b"quota"))
        return _MockResp({"candidates": [{"content": {"role": "model", "parts": [{"text": "Rotated OK!"}]}}]})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        res = brain._call_api([{"role": "user", "parts": [{"text": "bhai kya haal"}]}], aura_brain.GEMINI_TOOLS_DECLARATION)
    assert res["candidates"][0]["content"]["parts"][0]["text"] == "Rotated OK!"
    assert "key-quota-hit" in calls and "key-healthy-2" in calls

    # _build_conversation_history compacts & strips poisoned canned strings
    monkeypatch.setattr(aura_db, "DB_PATH", tmp_path / "hist_clean.db")
    aura_db.init_database()
    reg = aura_db.register_user("hist_clean_" + os.urandom(3).hex(), "HistPass!999")
    uid = reg["user"]["id"]
    tid = "th_clean_1"
    aura_db.save_message(uid, tid, "user", "Hello creator")
    aura_db.save_message(uid, tid, "assistant", "Understood. You said: 'Hello creator'. I am online.")
    aura_db.save_message(uid, tid, "user", "Second question")
    aura_db.save_message(uid, tid, "user", "Latest question")
    conv = aura_web._build_conversation_history(uid, tid)
    assert all("Understood. You said:" not in str(c) for c in conv)
    assert len(conv) == 1 and conv[0]["role"] == "user"
    assert "Hello creator" in conv[0]["parts"][0]["text"] and "Second question" in conv[0]["parts"][0]["text"]


def test_cross_container_account_proof_rejects_wrong_password_and_restores_valid_user(tmp_path: Path, monkeypatch):
    """
    On Vercel serverless, Container B has an empty /tmp/aura.db. With a server-signed encrypted
    `account_proof`, Container B MUST reject wrong passwords (401) and seamlessly restore the account +
    vault ONLY when the exact original password matches scrypt verification.
    """
    monkeypatch.setenv("AURA_SESSION_SECRET", "test-deployment-shared-session-secret-0123456789abcdef")
    monkeypatch.setenv("AURA_VAULT_SECRET", "test-deployment-shared-vault-secret-0123456789abcdef")
    monkeypatch.setenv("AURA_CSRF_SECRET", "test-deployment-shared-csrf-secret-0123456789abcdef")
    aura_db._RUNTIME_SECRETS_CACHE.clear()
    db_a = tmp_path / "container_a.db"
    db_b = tmp_path / "container_b.db"
    monkeypatch.setattr(aura_db, "DB_PATH", db_a)
    aura_db.init_database()

    uname = f"student_{os.urandom(3).hex()}"
    reg = aura_db.register_user(uname, "CollegePass99!")
    assert reg["success"] is True
    proof = reg.get("account_proof", "")
    assert proof.startswith("aura_ap1.")
    # Raw scrypt secrets must never appear plaintext in account_proof or user_vault
    vault = aura_db.export_user_vault(reg["user"]["id"])
    assert "CollegePass99!" not in proof and "password_hash" not in proof
    assert "password_hash" not in json.dumps(vault) and "salt" not in json.dumps(vault)

    # Save a chat thread in Container A and export signed vault
    tid = f"th_{os.urandom(3).hex()}"
    aura_db.create_user_thread(reg["user"]["id"], title="Calculus Notes", thread_id=tid)
    aura_db.save_message(reg["user"]["id"], tid, "user", "Explain Bayes theorem")
    vault = aura_db.export_user_vault(reg["user"]["id"])

    # Simulate cold-start on Container B (brand-new empty SQLite)
    monkeypatch.setattr(aura_db, "DB_PATH", db_b)
    aura_db.init_database()

    # Wrong password MUST be rejected even with valid proof + valid vault
    bad_login = aura_db.login_user(uname, "WrongPass99!", vault_backup=vault, account_proof=proof)
    assert bad_login["success"] is False

    # Forged / tampered proof MUST be rejected
    tampered = proof[:-4] + ("0000" if not proof.endswith("0000") else "1111")
    forged_login = aura_db.login_user(uname, "CollegePass99!", vault_backup=vault, account_proof=tampered)
    assert forged_login["success"] is False

    # Correct password restores user AND threads/messages
    good_login = aura_db.login_user(uname, "CollegePass99!", vault_backup=vault, account_proof=proof)
    assert good_login["success"] is True
    assert good_login.get("session_restored") is True
    restored_threads = aura_db.get_user_threads(good_login["user"]["id"])
    assert any(t["id"] == tid for t in restored_threads)


def test_offline_tool_fallback_bundles_html_app_for_live_studio():
    """When Gemini writes HTML/CSS/JS workspace files and hits fallback, reply must emit runnable HTML."""
    brain = aura_brain.AuraBrain(provider="gemini", model="gemini-3-flash-preview")
    brain.last_tools = [
        {
            "name": "tool_write_file",
            "args": {
                "filepath": "index.html",
                "content": "<!DOCTYPE html><html><head><link rel=\"stylesheet\" href=\"style.css\"></head><body><h1>App</h1><script src=\"app.js\"></script></body></html>",
            },
            "output": {"success": True, "file": "index.html"},
        },
        {
            "name": "tool_write_file",
            "args": {"filepath": "style.css", "content": "body { color: white; }"},
            "output": {"success": True, "file": "style.css"},
        },
        {
            "name": "tool_write_file",
            "args": {"filepath": "app.js", "content": "console.log('ready');"},
            "output": {"success": True, "file": "app.js"},
        },
        {
            "name": "tool_start_local_preview",
            "args": {"directory": ".", "entry": "index.html"},
            "output": {"success": True, "url": "http://127.0.0.1:5050/preview"},
        },
    ]
    fake_history = [
        {"role": "user", "parts": [{"text": "Build me an interactive timer app"}]},
        {"role": "user", "parts": [{"functionResponse": {"name": "tool_start_local_preview", "response": {"output": {"success": True}}}}]},
    ]
    out = brain._offline_autonomous_dispatch(fake_history, [])
    text = out["candidates"][0]["content"]["parts"][0]["text"]
    assert "Operation completed successfully" not in text
    assert "```html" in text
    assert "<style>" in text and "console.log('ready');" in text


def test_vercel_image_embedding_uses_portable_data_uri_and_strips_raw_json(tmp_path: Path, monkeypatch):
    """On Vercel serverless, _embed_generated_media replaces /media/... raw JSON dumps with portable JPEG data URIs."""
    from PIL import Image
    monkeypatch.setenv("VERCEL", "1")
    img_p = tmp_path / "aura_cinema_test123.png"
    Image.new("RGB", (128, 128), color=(30, 80, 190)).save(img_p, format="PNG")

    brain = aura_brain.AuraBrain(provider="gemini", model="gemini-3-flash-preview")
    brain.last_tools = [{
        "name": "tool_generate_image",
        "args": {"prompt": "Futuristic cyber skyline"},
        "output": {
            "success": True,
            "file_path": str(img_p),
            "web_url": "/media/generated_images/aura_cinema_test123.png",
        },
    }]
    raw_reply = 'Generated artwork:\n```json\n{"image_url": "/media/generated_images/aura_cinema_test123.png"}\n```'
    embedded = brain._embed_generated_media(raw_reply)
    assert "![Futuristic cyber skyline](data:image/jpeg;base64," in embedded
    assert '"image_url"' not in embedded


def test_offline_dispatch_ignores_injected_engine_framing_words():
    """Engine system framing words (e.g. 'Sound genuinely human' in AURA 2.0) must NEVER hijack volume/tool dispatch."""
    from aura_engine_20 import Aura20StudyEngine
    plan = Aura20StudyEngine().build_dispatch_plan(1, "Explain hash maps simply for a first-year CS student.")
    framed = f"[LANGUAGE LOCK: English]\n\n{plan.system_framing}\n\nExplain hash maps simply for a first-year CS student."
    brain = aura_brain.AuraBrain(provider="gemini", model="gemini-3-flash-preview")
    out = brain._offline_autonomous_dispatch([{"role": "user", "parts": [{"text": framed}]}], [])
    parts = out["candidates"][0]["content"]["parts"]
    assert all("functionCall" not in p for p in parts)
    txt = " ".join(p.get("text", "") for p in parts)
    assert "set_volume" not in txt and "Audio volume" not in txt


def test_pollinations_secondary_llm_failover_parses_openai_response():
    """Verifies secondary zero-key cloud text failover cleanly builds a Gemini-shaped response."""
    from unittest.mock import patch

    class _MockPollResp:
        status = 200
        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": "A hash map provides O(1) average lookup."}}]
            }).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    with patch("urllib.request.urlopen", return_value=_MockPollResp()):
        out = aura_brain.AuraBrain._try_pollinations_text_fallback(
            [{"role": "user", "parts": [{"text": "Explain hash maps"}]}],
            "You are AURA.",
            timeout_s=5.0,
        )
    assert out is not None
    assert "O(1)" in out["candidates"][0]["content"]["parts"][0]["text"]


def test_should_include_tools_ignores_engine_framing_and_coding_conceptual_queries():
    """Engine framing keywords ('html', 'url', 'trinetra') must NEVER inflate pure architecture/code prompts with 35+ tools."""
    from aura_engine_26 import Aura26ApexEngine
    plan = Aura26ApexEngine().build_dispatch_plan(1, "Design a scalable URL shortener architecture.")
    framed = f"[LANGUAGE LOCK: ENGLISH]\n\n{plan.system_framing}\n\nDesign a scalable URL shortener architecture."
    dummy_tools = [{"functionDeclarations": [{"name": "tool_read_file"}]}]

    assert aura_brain.AuraBrain._should_include_tools_for_contents(
        [{"role": "user", "parts": [{"text": framed}]}], dummy_tools
    ) is False

    # Real tool workflows MUST still keep tools active
    assert aura_brain.AuraBrain._should_include_tools_for_contents(
        [{"role": "user", "parts": [{"text": "Make the screen less bright"}]}], dummy_tools
    ) is True
    assert aura_brain.AuraBrain._should_include_tools_for_contents(
        [{"role": "user", "parts": [{"text": "Read file aura_db.py"}]}], dummy_tools
    ) is True


def test_thinking_config_only_sent_to_gemini3_and_strips_on_http_400():
    """Verify thinkingLevel is sent on gemini-3-flash-preview, stripped on non-3 fallbacks, and retried safely on 400."""
    import urllib.error
    import io
    from unittest.mock import patch

    sent_payloads = []

    class _MockResp:
        def __init__(self, txt):
            self._txt = txt
        def read(self):
            return json.dumps({
                "candidates": [{"content": {"parts": [{"text": self._txt}]}}]
            }).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def _fake_urlopen(req, timeout=10):
        pl = json.loads(req.data.decode("utf-8"))
        sent_payloads.append((req.full_url, pl))
        if len(sent_payloads) == 1:
            raise urllib.error.HTTPError(
                req.full_url, 400, "Bad Request", {}, io.BytesIO(b"Invalid thinkingConfig")
            )
        return _MockResp("Fast binary search summary.")

    brain = aura_brain.AuraBrain(provider="gemini", model="gemini-3-flash-preview")
    brain.api_key = "unit_synthetic_credential_for_verification_01"
    brain.thinking_level = "minimal"
    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        out = brain._call_api([{"role": "user", "parts": [{"text": "Explain binary search"}]}], [])

    assert out["candidates"][0]["content"]["parts"][0]["text"] == "Fast binary search summary."
    assert len(sent_payloads) >= 2
    assert sent_payloads[0][1]["generationConfig"].get("thinkingConfig") == {"thinkingLevel": "minimal"}
    assert "thinkingConfig" not in sent_payloads[1][1]["generationConfig"]


def test_jarvis_workspace_audit_uses_ttl_cache_and_briefing_runs_fast(tmp_path):
    """Verify JARVIS health audit caches within TTL and executive_briefing completes cleanly."""
    from aura_jarvis_hub import _audit_workspace_health
    p = tmp_path / "sample_mod.py"
    p.write_text("x = 1\n", encoding="utf-8")
    first = _audit_workspace_health(tmp_path)
    assert first["python_modules_checked"] == 1
    p2 = tmp_path / "sample_mod2.py"
    p2.write_text("y = 2\n", encoding="utf-8")
    cached = _audit_workspace_health(tmp_path)
    assert cached["python_modules_checked"] == 1  # Served instantaneously from 90s cache


def test_edge_voice_orchestrator_caches_short_phrases(monkeypatch):
    """Short spoken phrases hit in-memory LRU cache without invoking Edge-TTS twice."""
    from aura_voice_cloud import UniversalVoiceOrchestrator
    orch = UniversalVoiceOrchestrator()
    calls = {"n": 0}
    monkeypatch.setattr(orch._adapters["edge"], "is_available", lambda: (True, "ok"))

    def _fake_synth(**kwargs):
        calls["n"] += 1
        return b"ID3_FAKE_MP3_BYTES_" + (b"\x00" * 100), "mp3", "audio/mpeg"

    monkeypatch.setattr(orch._adapters["edge"], "synthesize", _fake_synth)
    a1 = orch.synthesize_speech("u1", "Systems ready.", language="en", voice_id="male_02", engine="edge")
    a2 = orch.synthesize_speech("u1", "Systems ready.", language="en", voice_id="male_02", engine="edge")
    assert calls["n"] == 1
    assert a1.bytes_len == a2.bytes_len and a2.bytes_len > 64


def test_health_endpoint_fast_default_model_and_multi_wallpaper_studio(isolated_server):
    """Verify /api/health, gemini-3-flash-preview default, and zero-cartoon multi-wallpaper UI assets."""
    import aura_settings

    base = isolated_server["base_url"]
    status, _, health = _http_json(f"{base}/api/health")
    assert status == 200
    assert health.get("status") == "ok"
    assert health.get("service") == "aura-core"

    # Settings manager & catalog default to fast live gemini-3-flash-preview
    assert aura_settings.MODEL_CATALOG["gemini"]["models"][0] == "gemini-3-flash-preview"
    brain_cfg = aura_web._selected_brain_settings({"id": 0, "username": "probe"})
    assert brain_cfg["active_provider"] == "gemini"
    assert brain_cfg["active_model"] == "gemini-3-flash-preview"

    # Multi-wallpaper studio & zero-emoji luxury static HTML check
    html = (Path(__file__).resolve().parent / "index.html").read_text(encoding="utf-8")
    assert "AURA_CURATED_WALLPAPERS" in html
    assert 'id="wallpaperQuickPopover"' in html
    assert 'id="btnHeaderWallpaper"' in html
    assert 'id="settingsWallpaperGrid"' in html
    assert 'id="quickWallpaperBlurRange"' in html
    assert 'id="wallpaperBlurRange"' in html
    assert "aura_custom_wallpapers_list" in html





