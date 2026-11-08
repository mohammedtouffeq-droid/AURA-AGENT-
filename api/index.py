import io
import sys
import traceback
from pathlib import Path

# Add project root directory to path so aura modules resolve cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from aura_web import AuraWebHandler

class DummyServer:
    server_name = "vercel"
    server_port = 443

def app(environ, start_response):
    """
    Standard WSGI callable for Vercel Serverless Functions.
    Bridges WSGI requests seamlessly into AuraWebHandler.
    """
    try:
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")
        query = environ.get("QUERY_STRING", "")
        full_path = f"{path}?{query}" if query else path

        # If Vercel rewrote the path, prefer the original matched path
        matched = environ.get("HTTP_X_MATCHED_PATH") or environ.get("HTTP_X_FORWARDED_URI") or environ.get("HTTP_X_ORIGINAL_URL")
        if matched and matched.startswith("/api"):
            full_path = matched

        lines = [f"{method} {full_path} HTTP/1.1"]
        for key, val in environ.items():
            if key.startswith("HTTP_"):
                header_name = key[5:].replace("_", "-").title()
                lines.append(f"{header_name}: {val}")
            elif key in ("CONTENT_TYPE", "CONTENT_LENGTH") and val:
                header_name = key.replace("_", "-").title()
                lines.append(f"{header_name}: {val}")

        header_bytes = ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")
        body_stream = environ.get("wsgi.input")
        content_len = int(environ.get("CONTENT_LENGTH") or 0)
        body_bytes = body_stream.read(content_len) if (body_stream and content_len > 0) else b""

        req_bytes = header_bytes + body_bytes
        rfile = io.BytesIO(req_bytes)
        wfile = io.BytesIO()

        class MockSocket:
            def makefile(self, mode, *args, **kwargs):
                if "b" in mode:
                    if "r" in mode:
                        return rfile
                    return wfile
                return rfile
            def sendall(self, data):
                wfile.write(data)

        # Dispatch through AuraWebHandler
        AuraWebHandler(MockSocket(), ("127.0.0.1", 80), DummyServer())

        res_bytes = wfile.getvalue()
        if not res_bytes:
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [b"Empty response from backend handler"]

        header_end = res_bytes.find(b"\r\n\r\n")
        if header_end == -1:
            start_response("200 OK", [("Content-Type", "text/html")])
            return [res_bytes]

        headers_part = res_bytes[:header_end].decode("iso-8859-1")
        response_body = res_bytes[header_end + 4:]

        header_lines = headers_part.split("\r\n")
        status_code = header_lines[0].split(" ", 1)[1] if " " in header_lines[0] else "200 OK"
        response_headers = [(l.split(":", 1)[0].strip(), l.split(":", 1)[1].strip()) for l in header_lines[1:] if ":" in l]

        start_response(status_code, response_headers)
        return [response_body]

    except Exception as e:
        tb = traceback.format_exc()
        start_response("500 Internal Server Error", [("Content-Type", "text/plain; charset=utf-8")])
        return [f"AURA Vercel Serverless Exception:\n{tb}".encode("utf-8")]

# Also export handler for BaseHTTPRequestHandler runtimes
class handler(AuraWebHandler):
    pass
