"""Synthetic stream used only by the local Caddy proxy smoke test."""

import time
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/api/v1/sse-smoke":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(b"data: first\n\n")
        self.wfile.flush()
        time.sleep(2)
        self.wfile.write(b"data: second\n\n")
        self.wfile.flush()

    def log_message(self, *_args):
        pass


HTTPServer(("0.0.0.0", 8001), Handler).serve_forever()
