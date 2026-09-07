#!/usr/bin/env python3
"""
Lightweight Static + Reverse Proxy Server for Gold Signal Frontend.
Serves frontend/dist on port 5173 and transparently proxies /api requests
to the FastAPI backend on http://127.0.0.1:8000 using a multi-threaded server.
"""

import http.server
import os
import sys
import urllib.error
import urllib.request

PORT = 5173
BACKEND_HOST = "http://127.0.0.1:8000"
DIST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "dist"))


class FrontendProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api"):
            self._proxy("GET")
        else:
            req_path = self.path.split("?")[0].lstrip("/")
            full_path = os.path.join(DIST_DIR, req_path)
            if not os.path.exists(full_path) and not req_path.startswith("assets"):
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api"):
            self._proxy("POST")
        else:
            self.send_error(405, "Method Not Allowed")

    def do_PUT(self):
        if self.path.startswith("/api"):
            self._proxy("PUT")
        else:
            self.send_error(405, "Method Not Allowed")

    def do_OPTIONS(self):
        if self.path.startswith("/api"):
            self._proxy("OPTIONS")
        else:
            super().do_OPTIONS()

    def _proxy(self, method: str):
        target_url = f"{BACKEND_HOST}{self.path}"
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        req = urllib.request.Request(target_url, data=body, method=method)
        for key, val in self.headers.items():
            if key.lower() not in ["host", "content-length"]:
                req.add_header(key, val)

        try:
            # Handle streaming endpoints like /api/stream with indefinite read
            is_stream = self.path.startswith("/api/stream")
            timeout = None if is_stream else 30
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                self.send_response(resp.status)
                for h, v in resp.headers.items():
                    if h.lower() not in ["transfer-encoding", "content-encoding"]:
                        self.send_header(h, v)
                self.end_headers()

                if is_stream:
                    while True:
                        line = resp.readline()
                        if not line:
                            break
                        self.wfile.write(line)
                        self.wfile.flush()
                else:
                    data = resp.read()
                    self.wfile.write(data)
        except urllib.error.HTTPError as err:
            self.send_response(err.code)
            for h, v in err.headers.items():
                if h.lower() not in ["transfer-encoding", "content-encoding"]:
                    self.send_header(h, v)
            self.end_headers()
            self.wfile.write(err.read())
        except Exception as exc:
            self.send_error(502, f"Bad Gateway: {exc}")

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server_address = ("0.0.0.0", PORT)
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    httpd = http.server.ThreadingHTTPServer(server_address, FrontendProxyHandler)
    print(f"• Frontend proxy server running at http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
