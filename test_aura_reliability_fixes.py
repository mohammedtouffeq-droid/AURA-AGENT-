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
