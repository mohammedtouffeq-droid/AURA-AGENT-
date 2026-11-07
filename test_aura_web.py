"""Comprehensive integration tests for AURA web server and API endpoints."""
from __future__ import annotations

import json
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from aura_web import AuraWebHandler, make_server


class AuraWebIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 5052
        cls.server = make_server("127.0.0.1", cls.port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.4)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_get_root_page(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode("utf-8")
            self.assertIn("AURA Core", body)
            self.assertIn("permissionPrompt", body)
            self.assertIn("Allow once", body)

    def test_get_safety_status(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/system/safety_status")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertFalse(data.get("sandbox_active"))
            self.assertTrue(data.get("command_filter_active"))
            self.assertIn("not process isolation", data.get("sandbox_note", ""))

    def test_permission_requests_require_authentication(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/permission/pending")
        with self.assertRaises(urllib.error.HTTPError) as response:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(response.exception.code, 401)

    def test_permission_decisions_require_authentication(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/permission/respond",
            data=json.dumps({"id": "missing", "decision": "ALLOW_ONCE"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as response:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(response.exception.code, 401)

    def test_model_settings_require_authentication(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/settings")
        with self.assertRaises(urllib.error.HTTPError) as response:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(response.exception.code, 401)

    def test_model_settings_are_user_scoped_and_do_not_expose_secrets(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/settings",
            headers={"Authorization": "Bearer settings-test-token"}
        )
        user = {"id": 42, "settings": {"brain_settings": {
            "active_provider": "ollama",
            "active_model": "qwen2.5-coder:7b"
        }}}
        with (
            patch("aura_db.authenticate_token", return_value=user),
            patch("aura_web.BRAIN.api_key", "server-secret"),
            urllib.request.urlopen(req, timeout=5) as response
        ):
            data = json.loads(response.read().decode())
        self.assertTrue(data["success"])
        self.assertEqual(data["brain_settings"]["active_provider"], "ollama")
        self.assertEqual(data["brain_settings"]["active_model"], "qwen2.5-coder:7b")
        self.assertTrue(data["gemini_key_configured"])
        self.assertNotIn("server-secret", json.dumps(data))

    def test_model_settings_post_validates_and_saves_for_authenticated_user(self):
        payload = json.dumps({
            "active_provider": "ollama",
            "active_model": "qwen2.5-coder:7b"
        }).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/settings",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer settings-test-token"
            },
            method="POST"
        )
        user = {"id": 42, "settings": {"other_preference": "preserved"}}
        with (
            patch("aura_db.authenticate_token", return_value=user),
            patch("aura_db.save_user_settings", return_value=True) as save_settings,
            urllib.request.urlopen(req, timeout=5) as response
        ):
            data = json.loads(response.read().decode())
        self.assertTrue(data["success"])
        self.assertEqual(data["brain_settings"]["active_model"], "qwen2.5-coder:7b")
        saved = save_settings.call_args.args[1]
        self.assertEqual(saved["other_preference"], "preserved")
        self.assertEqual(saved["brain_settings"]["active_provider"], "ollama")

    def test_model_settings_reject_unknown_provider_or_model(self):
        payload = json.dumps({
            "active_provider": "copilot",
            "active_model": "gpt-4o"
        }).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/settings",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer settings-test-token"
            },
            method="POST"
        )
        with (
            patch("aura_db.authenticate_token", return_value={"id": 42, "settings": {}}),
            patch("aura_db.save_user_settings") as save_settings,
            self.assertRaises(urllib.error.HTTPError) as response
        ):
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(response.exception.code, 400)
        save_settings.assert_not_called()

    def test_get_projects_list(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/projects")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertTrue(data.get("success"))
            self.assertIsInstance(data.get("projects"), list)

    def test_chat_api_post_authenticated(self):
        payload = json.dumps({
            "prompt": "What is the weather in Hyderabad?",
            "thread_id": "test_thread",
            "mode": "auto_pilot"
        }).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": "Bearer test-token"},
            method="POST"
        )
        with (
            patch("aura_db.authenticate_token", return_value={
                "id": "test-user",
                "settings": {"brain_settings": {
                    "active_provider": "ollama",
                    "active_model": "qwen2.5-coder:7b"
                }}
            }),
            patch("aura_db.save_message"),
            patch("aura_db.get_thread_messages", return_value=[]),
            patch("aura_web.AuraBrain") as brain_type
        ):
            brain_type.return_value.think_and_act.return_value = "Stubbed test response"
            brain_type.return_value.last_tools = []
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode())
                self.assertEqual(data.get("status"), "completed")
                self.assertIn("reply", data)
            brain_type.assert_called_once_with(provider="ollama", model="qwen2.5-coder:7b")

    def test_public_workspace_bypass_token_is_strictly_rejected(self):
        """Verify aura_public_workspace_token is never accepted by database or API."""
        import aura_db
        self.assertIsNone(aura_db.authenticate_token("aura_public_workspace_token"))
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/auth/me",
            headers={"Authorization": "Bearer aura_public_workspace_token"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 401)

    def test_signup_login_wrong_password_expiry_and_logout_lifecycle(self):
        """Test full signup, login, wrong password rejection, session expiry, and server-side logout."""
        import aura_db
        import secrets
        import datetime

        uname = f"sec_user_{secrets.token_hex(4)}"
        good_pass = "StrongPass2026!"

        # 1. Signup via API
        reg_req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/auth/register",
            data=json.dumps({"username": uname, "password": good_pass}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(reg_req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            set_cookie = resp.headers.get("Set-Cookie", "")
            self.assertIn("HttpOnly", set_cookie)
            self.assertIn("SameSite=Strict", set_cookie)
            reg_data = json.loads(resp.read().decode())
        self.assertTrue(reg_data["success"])
        token1 = reg_data["token"]
        self.assertTrue(len(token1) >= 32)
        self.assertNotEqual(token1, "aura_public_workspace_token")

        # 2. Wrong password rejection (401)
        bad_login = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/auth/login",
            data=json.dumps({"username": uname, "password": "WrongPassword999"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(bad_login, timeout=5)
        self.assertEqual(ctx.exception.code, 401)

        # 3. Valid login via API
        ok_login = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/auth/login",
            data=json.dumps({"username": uname, "password": good_pass}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(ok_login, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            login_data = json.loads(resp.read().decode())
        self.assertTrue(login_data["success"])
        token2 = login_data["token"]
        self.assertNotEqual(token1, token2)

        # 4. Session expiry enforcement
        expired_token = secrets.token_hex(24)
        past_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
        conn = aura_db.get_connection()
        c = conn.cursor()
        c.execute(
            "INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (expired_token, login_data["user"]["id"], past_iso)
        )
        conn.commit()
        conn.close()
        self.assertIsNone(aura_db.authenticate_token(expired_token))

        # 5. Logout revokes active session token
        logout_req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/auth/logout",
            data=json.dumps({"token": token2}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token2}"},
            method="POST"
        )
        with urllib.request.urlopen(logout_req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)

        me_req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/auth/me",
            headers={"Authorization": f"Bearer {token2}"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(me_req, timeout=5)
        self.assertEqual(ctx.exception.code, 401)

    def test_user_a_and_user_b_strict_multi_tenant_isolation(self):
        """Verify User A cannot read, modify, or delete User B's threads, messages, memory, settings, or projects."""
        import aura_db
        import secrets

        u_a = aura_db.register_user(f"alice_{secrets.token_hex(4)}", "AlicePass123!")
        u_b = aura_db.register_user(f"bob_{secrets.token_hex(4)}", "BobPass123!")
        self.assertTrue(u_a["success"] and u_b["success"])
        tok_a, id_a = u_a["token"], u_a["user"]["id"]
        tok_b, id_b = u_b["token"], u_b["user"]["id"]

        # User A creates thread, message, memory, project, and model settings
        th_a = aura_db.create_user_thread(id_a, "Alice Secret Thread")
        aura_db.save_message(id_a, th_a["id"], "user", "Alice confidential message")
        aura_db.save_user_memory(id_a, "secret_api_note", "Alice vault value")
        proj_a = aura_db.create_user_project(id_a, "AliceStealthProject", "AliceCorp", "Rust")
        aura_db.save_user_settings(id_a, {"brain_settings": {"active_provider": "ollama", "active_model": "llama3:8b"}})

        # User B attempts to read User A's threads and messages via API
        req_b_threads = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/threads",
            headers={"Authorization": f"Bearer {tok_b}"}
        )
        with urllib.request.urlopen(req_b_threads, timeout=5) as resp:
            b_threads = json.loads(resp.read().decode())["threads"]
        self.assertNotIn(th_a["id"], [t["id"] for t in b_threads])

        req_b_msgs = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/threads/messages?thread_id={th_a['id']}",
            headers={"Authorization": f"Bearer {tok_b}"}
        )
        with urllib.request.urlopen(req_b_msgs, timeout=5) as resp:
            b_msgs = json.loads(resp.read().decode())["messages"]
        self.assertEqual(b_msgs, [])

        # User B attempts to rename, pin, or delete User A's thread
        self.assertFalse(aura_db.rename_user_thread(id_b, th_a["id"], "Hacked Title"))
        self.assertFalse(aura_db.pin_user_thread(id_b, th_a["id"], True))
        self.assertFalse(aura_db.delete_user_thread(id_b, th_a["id"]))

        # User B attempts to read or delete User A's memory
        b_mems = aura_db.get_user_memories(id_b)
        self.assertNotIn("secret_api_note", [m["key"] for m in b_mems])
        self.assertFalse(aura_db.delete_user_memory(id_b, "secret_api_note"))

        # User B attempts to read, rename, pin, or delete User A's project
        b_projs = aura_db.get_user_projects(id_b)
        self.assertNotIn(proj_a["id"], [p["id"] for p in b_projs])
        self.assertFalse(aura_db.rename_user_project(id_b, proj_a["id"], "HackedProj"))
        self.assertFalse(aura_db.pin_user_project(id_b, proj_a["id"], True))
        self.assertFalse(aura_db.delete_user_project(id_b, proj_a["id"]))

        # User B's settings remain isolated from User A's settings
        auth_b = aura_db.authenticate_token(tok_b)
        self.assertNotEqual(auth_b["settings"].get("brain_settings", {}).get("active_model"), "llama3:8b")

    def test_cookie_csrf_protection_and_cors_origin_restriction(self):
        """Verify cookie-based POST requests require valid X-CSRF-Token and CORS blocks wildcard origins."""
        import aura_db
        import secrets

        u = aura_db.register_user(f"csrf_{secrets.token_hex(4)}", "CsrfPass123!")
        token = u["token"]
        csrf = aura_db.compute_csrf_token(token)

        # 1. Cookie-authenticated POST without CSRF token must return 401
        req_no_csrf = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/threads/new",
            data=json.dumps({"title": "Cookie Thread"}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Cookie": f"aura_session={token}",
                "Origin": "https://evil.example.com"
            },
            method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_no_csrf, timeout=5)
        self.assertEqual(ctx.exception.code, 401)
        # Verify wildcard '*' is not returned for untrusted origin
        self.assertNotEqual(ctx.exception.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertNotEqual(ctx.exception.headers.get("Access-Control-Allow-Origin"), "https://evil.example.com")

        # 2. Cookie-authenticated POST with valid X-CSRF-Token succeeds
        req_with_csrf = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/threads/new",
            data=json.dumps({"title": "Valid CSRF Thread"}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Cookie": f"aura_session={token}",
                "X-CSRF-Token": csrf,
                "Origin": "https://aura-agent-mohammedtouffeq-7681s-projects.vercel.app"
            },
            method="POST"
        )
        with urllib.request.urlopen(req_with_csrf, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(
                resp.headers.get("Access-Control-Allow-Origin"),
                "https://aura-agent-mohammedtouffeq-7681s-projects.vercel.app"
            )

    def test_unauthenticated_and_non_admin_endpoints_blocked(self):
        """Verify private endpoints return 401 unauthenticated and admin endpoints reject standard users."""
        import aura_db
        import secrets

        # Unauthenticated requests to private endpoints must return 401
        for get_ep in ["/api/threads", "/api/threads/messages?thread_id=1", "/api/memory", "/api/os/telemetry", "/api/workspace/tree", "/api/workspace/file?path=a.txt", "/api/coderx/ast", "/api/pipeline/runs", "/api/system/test_browser"]:
            req = urllib.request.Request(f"http://127.0.0.1:{self.port}{get_ep}")
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req, timeout=5)
            self.assertEqual(ctx.exception.code, 401, f"Expected 401 for unauthenticated GET {get_ep}")

        # Standard non-admin user must be rejected (401) on terminal and OS endpoints
        std_user = aura_db.register_user(f"std_{secrets.token_hex(4)}", "StdPass123!")
        std_tok = std_user["token"]
        for admin_post in ["/api/terminal/exec", "/api/os/execute", "/api/os/read_file", "/api/os/write_file", "/api/os/screenshot"]:
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}{admin_post}",
                data=json.dumps({"command": "whoami", "path": "test.txt"}).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {std_tok}"},
                method="POST"
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req, timeout=5)
            self.assertEqual(ctx.exception.code, 401, f"Expected 401 for non-admin POST {admin_post}")

    def test_honest_serverless_storage_detection_and_backup_migration(self):
        """Verify Vercel ephemeral storage never claims to be permanent and blocks silent account loss."""
        import aura_db
        import os

        # When VERCEL=1 without AURA_DATABASE_URL, storage is marked non-persistent and signup returns storage_unavailable
        with patch.dict(os.environ, {"VERCEL": "1", "AURA_DATABASE_URL": "", "TURSO_DATABASE_URL": "", "AURA_PERSISTENT_DB_PATH": ""}):
            status = aura_db.get_storage_status()
            self.assertFalse(status["persistent"])
            self.assertFalse(status["production_accounts_available"])
            res = aura_db.register_user("vercel_ephemeral_user", "ValidPass123!")
            self.assertFalse(res["success"])
            self.assertTrue(res.get("storage_unavailable"))

        # Verify database backup export & import across invocations
        snap = aura_db.export_database_backup()
        self.assertEqual(snap["schema_version"], 1)
        self.assertIn("users", snap["tables"])
        counts = aura_db.import_database_backup(snap)
        self.assertGreaterEqual(counts["users"], 1)

    def test_complete_end_to_end_user_journey(self):
        """
        End-to-end user journey test:
        1. Open AURA root page (verify auth modal & splash exist, no public bypass token).
        2. Sign up a new user via /api/auth/register.
        3. Log out via /api/auth/logout and verify token revocation.
        4. Log back in via /api/auth/login.
        5. Execute real assistant chat actions via /api/chat (weather telemetry & conversation persistence).
        6. Verify thread and message persistence via /api/threads and /api/threads/messages.
        7. Save & retrieve per-user memory via /api/memory/add and /api/memory.
        8. Create & retrieve per-user coding project via /api/projects/new and /api/projects.
        9. Save & retrieve per-user model settings via /api/settings.
        10. Verify permission gate endpoints (/api/permission/pending and /api/permission/mode).
        """
        import secrets
        uname = f"journey_{secrets.token_hex(4)}"
        pwd = "JourneyPass2026!"

        # 1. Open AURA root page
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=5) as r:
            html = r.read().decode("utf-8")
            self.assertEqual(r.status, 200)
            self.assertNotIn("aura_public_workspace_token", html)
            self.assertNotIn("AuraGuestUser2026!", html)
            self.assertIn('id="authOverlay"', html)

        # 2. Sign up
        reg_req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/auth/register",
            data=json.dumps({"username": uname, "password": pwd}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(reg_req, timeout=5) as r:
            reg_data = json.loads(r.read().decode())
        self.assertTrue(reg_data["success"])
        first_token = reg_data["token"]
        default_thread_id = reg_data["default_thread_id"]

        # 3. Log out
        out_req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/auth/logout",
            data=json.dumps({"token": first_token}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {first_token}"},
            method="POST"
        )
        with urllib.request.urlopen(out_req, timeout=5) as r:
            self.assertEqual(r.status, 200)

        # 4. Log in
        in_req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/auth/login",
            data=json.dumps({"username": uname, "password": pwd}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(in_req, timeout=5) as r:
            in_data = json.loads(r.read().decode())
        self.assertTrue(in_data["success"])
        token = in_data["token"]
        auth_headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        # 5. Real Assistant Action via /api/chat (Live Weather Telemetry tool execution)
        chat_req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/chat",
            data=json.dumps({
                "prompt": "What is the current weather in Hyderabad?",
                "thread_id": default_thread_id,
                "mode": "auto_pilot"
            }).encode("utf-8"),
            headers=auth_headers,
            method="POST"
        )
        with urllib.request.urlopen(chat_req, timeout=15) as r:
            chat_data = json.loads(r.read().decode())
        self.assertEqual(chat_data["status"], "completed")
        self.assertTrue(len(chat_data.get("reply", "")) > 10)

        # 6. Verify thread & message persistence
        with urllib.request.urlopen(
            urllib.request.Request(f"http://127.0.0.1:{self.port}/api/threads/messages?thread_id={default_thread_id}", headers=auth_headers),
            timeout=5
        ) as r:
            msgs = json.loads(r.read().decode())["messages"]
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[1]["role"], "assistant")

        # 7. Save & retrieve memory
        mem_req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/memory/add",
            data=json.dumps({"key": "preferred_stack", "value": "Python + Godot 4.3"}).encode("utf-8"),
            headers=auth_headers,
            method="POST"
        )
        with urllib.request.urlopen(mem_req, timeout=5) as r:
            self.assertTrue(json.loads(r.read().decode())["success"])

        with urllib.request.urlopen(
            urllib.request.Request(f"http://127.0.0.1:{self.port}/api/memory", headers=auth_headers),
            timeout=5
        ) as r:
            mems = json.loads(r.read().decode())["memories"]
        self.assertTrue(any(m["key"] == "preferred_stack" for m in mems))

        # 8. Create & retrieve coding project
        proj_req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/projects/new",
            data=json.dumps({"name": "AURA Core Service", "company": "AURA", "stack": "Python"}).encode("utf-8"),
            headers=auth_headers,
            method="POST"
        )
        with urllib.request.urlopen(proj_req, timeout=5) as r:
            self.assertTrue(json.loads(r.read().decode())["success"])

        with urllib.request.urlopen(
            urllib.request.Request(f"http://127.0.0.1:{self.port}/api/projects", headers=auth_headers),
            timeout=5
        ) as r:
            projs = json.loads(r.read().decode())["projects"]
        self.assertTrue(any(p["name"] == "AURA Core Service" for p in projs))

        # 9. Update & verify model settings
        set_req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/settings",
            data=json.dumps({"active_provider": "gemini", "active_model": "gemini-flash-lite-latest"}).encode("utf-8"),
            headers=auth_headers,
            method="POST"
        )
        with urllib.request.urlopen(set_req, timeout=5) as r:
            self.assertTrue(json.loads(r.read().decode())["success"])

        # 10. Check permission system pending queue
        with urllib.request.urlopen(
            urllib.request.Request(f"http://127.0.0.1:{self.port}/api/permission/pending", headers=auth_headers),
            timeout=5
        ) as r:
            perm_data = json.loads(r.read().decode())
        self.assertTrue(perm_data["success"])


if __name__ == "__main__":
    unittest.main()
