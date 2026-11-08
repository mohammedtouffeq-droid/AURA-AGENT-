import sys
import traceback
from pathlib import Path

# Add project root directory to path so aura modules resolve cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from aura_web import AuraWebHandler
except Exception as e:
    import http.server
    err_tb = traceback.format_exc()
    class handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Import Error in api/index.py:\n{err_tb}".encode('utf-8'))
        def do_POST(self):
            self.do_GET()
else:
    class handler(AuraWebHandler):
        def do_GET(self):
            try:
                super().do_GET()
            except Exception:
                tb = traceback.format_exc()
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Vercel Handler Exception:\n{tb}".encode('utf-8'))

        def do_POST(self):
            try:
                super().do_POST()
            except Exception:
                tb = traceback.format_exc()
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"Vercel Handler Exception:\n{tb}".encode('utf-8'))
