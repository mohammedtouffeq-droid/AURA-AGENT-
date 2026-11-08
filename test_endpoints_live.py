import unittest
import urllib.request
import json
import threading
import sys
from pathlib import Path
from http.server import HTTPServer

ROOT = Path(r"C:\Users\hp\AURA-Agent")
sys.path.insert(0, str(ROOT))

from aura_web import AuraWebHandler
import aura_db

class TestLiveEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), AuraWebHandler)
        cls.port = cls.server.server_port
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        
        reg_admin = aura_db.register_user("live_test_admin", "AdminTestPass123!")
        if not reg_admin.get("success"):
            reg_admin = aura_db.login_user("live_test_admin", "AdminTestPass123!")
        cls.admin_user = reg_admin["user"]
        cls.session_token = reg_admin["token"]
        aura_db.set_user_role(cls.admin_user["id"], "admin")
        cls.auth_headers = {
            "Authorization": f"Bearer {cls.session_token}",
            "Content-Type": "application/json"
        }

    @classmethod
    def tearDownClass(cls):
        try:
            cls.server.shutdown()
            cls.server.server_close()
        except Exception:
            pass

    def test_01_get_root_html(self):
        req = urllib.request.urlopen(f"{self.base_url}/")
        self.assertEqual(req.status, 200)
        html = req.read().decode("utf-8")
        self.assertIn("AURA", html)
        self.assertIn("authOverlay", html)

    def test_02_workspace_tree_authenticated(self):
        req = urllib.request.Request(f"{self.base_url}/api/workspace/tree", headers=self.auth_headers)
        res = urllib.request.urlopen(req)
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode("utf-8"))
        self.assertTrue(data.get("success"))
        self.assertIn("files", data)

    def test_03_terminal_exec_admin(self):
        post_data = json.dumps({"command": "Write-Output 'AURA_LIVE_ONLINE'"}).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}/api/terminal/exec", data=post_data, headers=self.auth_headers)
        res = urllib.request.urlopen(req)
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode("utf-8"))
        self.assertTrue(data.get("success"))
        self.assertIn("AURA_LIVE_ONLINE", data.get("stdout", ""))

    def test_04_cyberheist_status_authenticated(self):
        req = urllib.request.Request(f"{self.base_url}/api/cyberheist/status", headers=self.auth_headers)
        res = urllib.request.urlopen(req)
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode("utf-8"))
        self.assertTrue(data.get("success"))

if __name__ == "__main__":
    unittest.main()
