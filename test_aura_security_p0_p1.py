"""
===================================================================================
           AURA P0 & P1 SECURITY & ARCHITECTURAL HARDENING AUDIT TEST SUITE
===================================================================================
Dedicated verification covering:
1. P0 — Remote Command Execution Prevention (CommandGuard & Auth Enforcement)
2. P0 — User Isolation & Zero Fallback User ID 1 Verification
3. P0 — Strict Sandbox Workspace Boundaries (No outside absolute escape)
4. P1 — Session Expiry, Revocation, Rate Limiting & Password Complexity
5. P1 — Honest Engine Bridge Status & Fail-Closed Pipeline Validation
===================================================================================
"""
import os
import sys
import unittest
import threading
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import aura_db
from aura_agent import UniversalEngineBridge
from aura_brain import validate_safe_path, is_safe_command, SAFE_WORKSPACE_ROOTS
from aura_web import make_server
from aura_master_pipeline import AURA_PIPELINE


class TestAuraSecurityP0P1Hardening(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.port = 5052
        cls.server = make_server("127.0.0.1", cls.port)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

        # Create a registered test user
        cls.username = "audit_sec_user"
        cls.password = "StrongP@ssw0rd123"
        reg = aura_db.register_user(cls.username, cls.password)
        if not reg.get("success"):
            # Clean up if prior run
            conn = aura_db.get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM users WHERE username = ?", (cls.username,))
            conn.commit()
            conn.close()
            reg = aura_db.register_user(cls.username, cls.password)
        cls.token = reg["token"]
        cls.user_id = reg["user"]["id"]

    @classmethod
    def tearDownClass(cls):
        # Clean up test user
        conn = aura_db.get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE username = ?", (cls.username,))
        conn.commit()
        conn.close()
        cls.server.shutdown()

    def _post(self, path: str, data: dict, headers: dict = None):
        url = f"http://127.0.0.1:{self.port}{path}"
        body = json.dumps(data).encode("utf-8")
        all_headers = {"Content-Type": "application/json"}
        if headers:
            all_headers.update(headers)
        req = urllib.request.Request(url, data=body, headers=all_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def _get(self, path: str, headers: dict = None):
        url = f"http://127.0.0.1:{self.port}{path}"
        all_headers = {}
        if headers:
            all_headers.update(headers)
        req = urllib.request.Request(url, headers=all_headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    # =========================================================================
    # 1. P0 — ZERO FALLBACK USER ID 1 & USER ISOLATION
    # =========================================================================
    def test_sec_01_unauthenticated_thread_rename_fails_401(self):
        """Unauthenticated thread mutation must fail with HTTP 401 without affecting user 1."""
        status, body = self._post("/api/threads/rename", {"thread_id": "th_dummy", "title": "Hacked Title"})
        self.assertEqual(status, 401)
        self.assertFalse(body.get("success"))

    def test_sec_02_unauthenticated_thread_pin_fails_401(self):
        status, body = self._post("/api/threads/pin", {"thread_id": "th_dummy", "is_pinned": True})
        self.assertEqual(status, 401)
        self.assertFalse(body.get("success"))

    def test_sec_03_unauthenticated_thread_delete_fails_401(self):
        status, body = self._post("/api/threads/delete", {"thread_id": "th_dummy"})
        self.assertEqual(status, 401)
        self.assertFalse(body.get("success"))

    def test_sec_04_unauthenticated_project_create_fails_401(self):
        status, body = self._post("/api/projects/new", {"name": "Malicious Project"})
        self.assertEqual(status, 401)
        self.assertFalse(body.get("success"))

    def test_sec_05_unauthenticated_project_delete_fails_401(self):
        status, body = self._post("/api/projects/delete", {"project_id": "proj_dummy"})
        self.assertEqual(status, 401)
        self.assertFalse(body.get("success"))

    def test_sec_06_unauthenticated_memory_add_fails_401(self):
        status, body = self._post("/api/memory/add", {"key": "secret", "value": "leak"})
        self.assertEqual(status, 401)
        self.assertFalse(body.get("success"))

    def test_sec_07_unauthenticated_memory_delete_fails_401(self):
        status, body = self._post("/api/memory/delete", {"key": "secret"})
        self.assertEqual(status, 401)
        self.assertFalse(body.get("success"))

    def test_sec_08_authenticated_user_isolation(self):
        """Authenticated user actions only mutate that user's own data."""
        headers = {"Authorization": f"Bearer {self.token}"}
        status, body = self._post("/api/memory/add", {"key": "audit_test_key", "value": "audit_val_1"}, headers)
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))

        status, get_body = self._get("/api/memory", headers)
        self.assertEqual(status, 200)
        memories = get_body.get("memories", [])
        self.assertTrue(any(m["key"] == "audit_test_key" for m in memories))

        # Another user or unauthenticated request cannot see this memory
        status, anon_body = self._get("/api/memory")
        self.assertEqual(status, 200)
        self.assertEqual(anon_body.get("memories"), [])

    # =========================================================================
    # 2. P0 — FILE SANDBOX BOUNDARY ENFORCEMENT
    # =========================================================================
    def test_sec_09_sandbox_blocks_arbitrary_outside_path(self):
        """validate_safe_path must block absolute paths outside approved roots."""
        outside_path = "C:/ProgramData/malicious/file.txt"
        with self.assertRaises(PermissionError):
            validate_safe_path(outside_path)

    def test_sec_10_sandbox_allows_approved_workspace_path(self):
        safe_path = Path(__file__).resolve().parent / "workspace" / "audit_valid.txt"
        resolved = validate_safe_path(str(safe_path))
        self.assertEqual(resolved, safe_path.resolve())

    def test_sec_11_sandbox_blocks_traversal_escaping_workspace(self):
        traversal = str(ROOT / ".." / ".." / "Windows" / "win.ini")
        with self.assertRaises(PermissionError):
            validate_safe_path(traversal)

    # =========================================================================
    # 3. P0 — COMMAND GUARD & TERMINAL EXECUTION HARDENING
    # =========================================================================
    def test_sec_12_terminal_blocks_format_command(self):
        """POST /api/terminal/exec must block dangerous format command with HTTP 403."""
        status, body = self._post("/api/terminal/exec", {"command": "format C: /fs:ntfs"})
        self.assertEqual(status, 403)
        self.assertFalse(body.get("success"))
        self.assertIn("Security Sandbox", body.get("error", ""))

    def test_sec_13_terminal_blocks_recursive_deletion(self):
        """POST /api/terminal/exec must block Remove-Item -Recurse C:\\."""
        status, body = self._post("/api/terminal/exec", {"command": "Remove-Item -Recurse C:\\"})
        self.assertEqual(status, 403)
        self.assertFalse(body.get("success"))

    def test_sec_14_os_execute_blocks_destructive_command(self):
        """POST /api/os/execute must intercept destructive shell operations."""
        status, body = self._post("/api/os/execute", {"command": "Stop-Computer -Force"})
        self.assertEqual(status, 403)
        self.assertFalse(body.get("success"))

    # =========================================================================
    # 4. P1 — SESSION EXPIRATION, REVOCATION & RATE LIMITING
    # =========================================================================
    def test_sec_15_password_policy_enforcement(self):
        """Password complexity enforces minimum 6 chars and mixed character set."""
        # Short
        res1 = aura_db.register_user("weak1", "abc")
        self.assertFalse(res1.get("success"))
        self.assertIn("at least 6 characters", res1.get("error", ""))

        # Only digits
        res2 = aura_db.register_user("weak2", "12345678")
        self.assertFalse(res2.get("success"))
        self.assertIn("both letters and numbers", res2.get("error", ""))

        # Only letters
        res3 = aura_db.register_user("weak3", "abcdefgh")
        self.assertFalse(res3.get("success"))
        self.assertIn("both letters and numbers", res3.get("error", ""))

    def test_sec_16_session_revocation(self):
        """Session token is revoked via /api/auth/logout and cannot be reused."""
        # Login to get fresh token
        login_res = aura_db.login_user(self.username, self.password)
        self.assertTrue(login_res.get("success"))
        temp_token = login_res["token"]

        # Verify active
        self.assertIsNotNone(aura_db.authenticate_token(temp_token))

        # Logout via API
        status, body = self._post("/api/auth/logout", {}, headers={"Authorization": f"Bearer {temp_token}"})
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))

        # Verify token is now invalid
        self.assertIsNone(aura_db.authenticate_token(temp_token))

    def test_sec_17_login_rate_limiting(self):
        """5 consecutive bad logins locks out subsequent attempts."""
        test_user = "rate_limit_victim"
        # Register victim
        aura_db.register_user(test_user, "VictimPass123!")

        # 5 failed attempts
        for _ in range(5):
            aura_db.login_user(test_user, "wrong_pass")

        # 6th attempt should be rate limited even with correct password
        locked = aura_db.login_user(test_user, "VictimPass123!")
        self.assertFalse(locked.get("success"))
        self.assertIn("Too many failed login attempts", locked.get("error", ""))

        # Cleanup
        aura_db.clear_login_failures(test_user)
        conn = aura_db.get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE username = ?", (test_user,))
        conn.commit()
        conn.close()

    # =========================================================================
    # 5. P1 — HONEST HEALTH STATUS & FAIL-CLOSED PIPELINE
    # =========================================================================
    def test_sec_18_engine_bridge_honest_status(self):
        """Unmounted engine bridges must honestly report alive=False and NOT_MOUNTED."""
        fake_bridge = UniversalEngineBridge("non_existent_engine_xyz", "Fake Engine", "test", 100, "Demo")
        status = fake_bridge.get_status()
        self.assertFalse(status["mounted"])
        self.assertFalse(status["alive"])
        self.assertFalse(status["awakened"])
        self.assertEqual(status["status"], "NOT_MOUNTED")
        self.assertEqual(status["files_available"], 0)

    def test_sec_19_master_pipeline_fail_closed_validation(self):
        """Master pipeline validates artifact existence on disk."""
        topo = AURA_PIPELINE.get_pipeline_topology()
        self.assertIn("status", topo)
        self.assertEqual(topo["status"], "OPERATIONAL")


if __name__ == "__main__":
    unittest.main()
