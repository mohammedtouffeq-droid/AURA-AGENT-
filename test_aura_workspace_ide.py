"""Tests for AURA Workspace IDE tools, PWA routes, preview isolation, and devserver endpoints."""
from __future__ import annotations

import json
import os
import secrets
import shutil
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request

import aura_brain
import aura_db
from aura_web import _resolve_workspace_dir, make_server
from aura_workspace_ide import WORKSPACE_DEV_MANAGER, extract_localhost_urls


class TestAuraBrainWorkspaceIdeTools(unittest.TestCase):
    def setUp(self):
        self.uid_a = 910001 + secrets.randbelow(50000)
        self.uid_b = self.uid_a + 1
        self.ws_a = _resolve_workspace_dir(self.uid_a)
        self.ws_b = _resolve_workspace_dir(self.uid_b)

    def tearDown(self):
        WORKSPACE_DEV_MANAGER.stop_all()
        shutil.rmtree(self.ws_a, ignore_errors=True)
        shutil.rmtree(self.ws_b, ignore_errors=True)

    def test_extract_localhost_urls_normalizes_loopback(self):
        sample = (
            "Server listening at http://0.0.0.0:3000/dashboard and "
            "http://localhost:5173/app?tab=1."
        )
        urls = extract_localhost_urls(sample)
        self.assertEqual(urls, ["http://127.0.0.1:3000/dashboard", "http://localhost:5173/app?tab=1"])

    def test_read_line_slice_edit_grep_and_delete(self):
        lines = "\n".join(f"line_{i} = {i * 2}" for i in range(1, 21))
        wres = aura_brain.tool_write_file("src/calc.py", lines, user_id=self.uid_a)
        self.assertTrue(wres.get("success"))

        rres = aura_brain.tool_read_file("src/calc.py", start_line=5, end_line=8, user_id=self.uid_a)
        self.assertTrue(rres.get("success"))
        self.assertEqual(rres.get("start_line"), 5)
        self.assertEqual(rres.get("end_line"), 8)
        self.assertEqual(rres.get("total_lines"), 20)
        self.assertTrue(rres.get("truncated"))
        self.assertIn("5: line_5 = 10", rres.get("numbered_content", ""))
        self.assertIn("8: line_8 = 16", rres.get("numbered_content", ""))
        self.assertNotIn("9: line_9", rres.get("numbered_content", ""))

        # Surgical edit succeeds cleanly on unique target and emits unified diff
        eres = aura_brain.tool_edit_file(
            "src/calc.py",
            target="line_6 = 12",
            replacement="line_6 = 600",
            user_id=self.uid_a,
        )
        self.assertTrue(eres.get("success"))
        self.assertIn("-line_6 = 12", eres.get("diff", ""))
        self.assertIn("+line_6 = 600", eres.get("diff", ""))

        # Missing target fails closed
        missing = aura_brain.tool_edit_file(
            "src/calc.py",
            target="does_not_exist = 999",
            replacement="x = 1",
            user_id=self.uid_a,
        )
        self.assertFalse(missing.get("success"))

        # Ambiguous target fails closed unless replace_all=True
        aura_brain.tool_write_file("dup.txt", "alpha\nbeta\nalpha\n", user_id=self.uid_a)
        ambig = aura_brain.tool_edit_file("dup.txt", target="alpha", replacement="omega", user_id=self.uid_a)
        self.assertFalse(ambig.get("success"))
        self.assertEqual(ambig.get("matches"), 2)

        all_res = aura_brain.tool_edit_file(
            "dup.txt", target="alpha", replacement="omega", replace_all=True, user_id=self.uid_a
        )
        self.assertTrue(all_res.get("success"))
        self.assertEqual(all_res.get("occurrences_replaced"), 2)

        # Grep respects tenant isolation
        aura_brain.tool_write_file("secret.txt", "SECRET_B_TOKEN_99", user_id=self.uid_b)
        grep_a = aura_brain.tool_grep_search("line_6 = 600", user_id=self.uid_a)
        self.assertTrue(grep_a.get("success"))
        self.assertEqual(grep_a.get("count"), 1)
        self.assertEqual(grep_a["matches"][0]["file"], "src/calc.py")

        grep_cross = aura_brain.tool_grep_search("SECRET_B_TOKEN_99", user_id=self.uid_a)
        self.assertTrue(grep_cross.get("success"))
        self.assertEqual(grep_cross.get("count"), 0)

        # Traversal blocked, valid file deletes cleanly
        bad_del = aura_brain.tool_delete_file("../outside.txt", user_id=self.uid_a)
        self.assertFalse(bad_del.get("success"))
        ok_del = aura_brain.tool_delete_file("dup.txt", user_id=self.uid_a)
        self.assertTrue(ok_del.get("success"))
        self.assertFalse((self.ws_a / "dup.txt").exists())

    def test_static_local_preview_lifecycle(self):
        aura_brain.tool_write_file("app/index.html", "<h1>IDE Live App</h1>", user_id=self.uid_a)
        started = aura_brain.tool_start_local_preview(directory="app", port=0, entry="index.html", user_id=self.uid_a)
        self.assertTrue(started.get("success"), started)
        url = started["url"]
        self.assertTrue(url.startswith("http://127.0.0.1:"))

        with urllib.request.urlopen(url, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("IDE Live App", resp.read().decode("utf-8"))

        listed = aura_brain.tool_list_local_previews(user_id=self.uid_a)
        self.assertTrue(listed.get("success"))
        self.assertEqual(len(listed.get("servers", [])), 1)

        stopped = aura_brain.tool_stop_local_preview(started["server_id"], user_id=self.uid_a)
        self.assertTrue(stopped.get("success"))


class TestAuraWebIdeAndPwaRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.25)

        cls.std_user = aura_db.register_user(f"ide_std_{secrets.token_hex(4)}", "IdePass123!")
        cls.std_token = cls.std_user["token"]
        cls.std_uid = cls.std_user["user"]["id"]

        cls.admin_user = aura_db.register_user(f"ide_adm_{secrets.token_hex(4)}", "IdeAdmPass123!")
        cls.admin_token = cls.admin_user["token"]
        cls.admin_uid = cls.admin_user["user"]["id"]
        aura_db.set_user_role(cls.admin_uid, "admin")

    @classmethod
    def tearDownClass(cls):
        WORKSPACE_DEV_MANAGER.stop_all()
        try:
            cls.server.shutdown()
            cls.server.server_close()
        except Exception:
            pass
        shutil.rmtree(_resolve_workspace_dir(cls.std_uid), ignore_errors=True)
        shutil.rmtree(_resolve_workspace_dir(cls.admin_uid), ignore_errors=True)

    def _req(self, path: str, method: str = "GET", token: str = "", body: dict | None = None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(f"{self.base}{path}", data=data, headers=headers, method=method)
        return urllib.request.urlopen(req, timeout=8)

    def test_pwa_routes_and_csp_headers(self):
        with self._req("/") as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")
            csp = resp.headers.get("Content-Security-Policy", "")
            self.assertIn("frame-ancestors 'none'", csp)

        with self._req("/manifest.json") as resp:
            self.assertEqual(resp.status, 200)
            manifest = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(manifest.get("display"), "standalone")

        with self._req("/sw.js") as resp:
            self.assertEqual(resp.status, 200)
            sw_txt = resp.read().decode("utf-8")
            self.assertIn("addEventListener", sw_txt)

        with self._req("/api/pwa/icon.svg") as resp:
            self.assertEqual(resp.status, 200)
            svg_txt = resp.read().decode("utf-8")
            self.assertIn("<svg", svg_txt)

    def test_workspace_ide_http_endpoints_and_preview_security(self):
        # Unauthenticated preview rejected
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._req("/api/workspace/preview/demo.html")
        self.assertEqual(ctx.exception.code, 401)

        # Save HTML + Python files as standard user
        with self._req(
            "/api/workspace/save",
            method="POST",
            token=self.std_token,
            body={"path": "demo.html", "content": "<html><body><h1>Old Title</h1></body></html>"},
        ) as resp:
            self.assertEqual(resp.status, 200)

        with self._req(
            "/api/workspace/save",
            method="POST",
            token=self.std_token,
            body={"path": "secret.py", "content": "API_KEY = 'demo'\n"},
        ) as resp:
            self.assertEqual(resp.status, 200)

        # Grep endpoint locates text
        with self._req(
            "/api/workspace/grep",
            method="POST",
            token=self.std_token,
            body={"query": "Old Title"},
        ) as resp:
            gdata = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(gdata.get("success"))
            self.assertEqual(gdata.get("count"), 1)

        # Edit endpoint updates HTML surgically
        with self._req(
            "/api/workspace/edit",
            method="POST",
            token=self.std_token,
            body={"path": "demo.html", "target": "Old Title", "replacement": "New Live Title"},
        ) as resp:
            edata = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(edata.get("success"))
            self.assertIn("+<html><body><h1>New Live Title</h1></body></html>", edata.get("diff", ""))

        # Preview serves safe HTML with SAMEORIGIN + frame-ancestors 'self'
        with self._req("/api/workspace/preview/demo.html", token=self.std_token) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("X-Frame-Options"), "SAMEORIGIN")
            self.assertIn("frame-ancestors 'self'", resp.headers.get("Content-Security-Policy", ""))
            self.assertIn("New Live Title", resp.read().decode("utf-8"))

        # Unsupported file types (.py) refused (415) and traversal refused (403)
        with self.assertRaises(urllib.error.HTTPError) as ctx_py:
            self._req("/api/workspace/preview/secret.py", token=self.std_token)
        self.assertEqual(ctx_py.exception.code, 415)

        with self.assertRaises(urllib.error.HTTPError) as ctx_trav:
            self._req("/api/workspace/preview?path=../../aura_web.py", token=self.std_token)
        self.assertEqual(ctx_trav.exception.code, 403)

        # Delete removes file
        with self._req(
            "/api/workspace/delete",
            method="POST",
            token=self.std_token,
            body={"path": "secret.py"},
        ) as resp:
            ddata = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(ddata.get("success"))

    def test_devserver_and_terminal_exec_permissions_and_urls(self):
        with self._req(
            "/api/workspace/save",
            method="POST",
            token=self.std_token,
            body={"path": "site/index.html", "content": "<title>DevSite</title><p>Mobile Ready</p>"},
        ) as resp:
            self.assertEqual(resp.status, 200)

        # Standard user can launch static workspace preview server
        with self._req(
            "/api/workspace/devserver/start",
            method="POST",
            token=self.std_token,
            body={"mode": "static", "directory": "site", "entry": "index.html"},
        ) as resp:
            sdata = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(sdata.get("success"))
            srv_id = sdata["server_id"]
            with urllib.request.urlopen(sdata["url"], timeout=5) as site_resp:
                self.assertEqual(site_resp.status, 200)
                self.assertIn("Mobile Ready", site_resp.read().decode("utf-8"))

        with self._req("/api/workspace/devserver/status", token=self.std_token) as resp:
            stdata = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(len(stdata.get("servers", [])), 1)

        with self._req(
            "/api/workspace/devserver/stop",
            method="POST",
            token=self.std_token,
            body={"server_id": srv_id},
        ) as resp:
            stopdata = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(stopdata.get("success"))

        # Standard user blocked on command-mode devserver and /api/terminal/exec
        with self.assertRaises(urllib.error.HTTPError) as ctx_cmd:
            self._req(
                "/api/workspace/devserver/start",
                method="POST",
                token=self.std_token,
                body={"mode": "command", "command": "python --version"},
            )
        self.assertEqual(ctx_cmd.exception.code, 401)

        # Admin user runs /api/terminal/exec and gets cwd + detected_urls
        term_cmd = "echo App running at http://127.0.0.1:4321/app"
        with self._req(
            "/api/terminal/exec",
            method="POST",
            token=self.admin_token,
            body={"command": term_cmd},
        ) as resp:
            tdata = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(tdata.get("success"), tdata)
            self.assertTrue(bool(tdata.get("cwd")))
            self.assertEqual(tdata.get("detected_urls"), ["http://127.0.0.1:4321/app"])


if __name__ == "__main__":
    unittest.main()
