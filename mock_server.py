"""Mock endpoint for the expense auto-approver exercise.

Stdlib only. Run:  python mock_server.py
Listens on http://localhost:8000

  POST /decisions   body = one decision object OR a JSON list of them
  GET  /decisions   returns every decision received so far
  GET  /health      liveness check

A decision is whatever shape you design. There is no enforced schema. When the
decision is "flag", include a clarifying question for the submitter on the same
object (e.g. a "question" field) — flags and their questions travel together
through this one endpoint.

Received decisions are printed and appended to received_decisions.jsonl next to
this file.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "localhost", 8000
HERE = os.path.dirname(os.path.abspath(__file__))

DECISIONS = []
LOG_PATH = os.path.join(HERE, "received_decisions.jsonl")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status": "ok"})
        elif self.path == "/decisions":
            self._send(200, {"count": len(DECISIONS), "items": DECISIONS})
        else:
            self._send(404, {"error": "not found", "path": self.path})

    def do_POST(self):
        if self.path != "/decisions":
            self._send(404, {"error": "not found", "path": self.path})
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            self._send(400, {"error": "invalid JSON", "detail": str(e)})
            return

        batch = parsed if isinstance(parsed, list) else [parsed]
        with open(LOG_PATH, "a") as f:
            for item in batch:
                DECISIONS.append(item)
                f.write(json.dumps(item) + "\n")
                print(f"  received decision: {json.dumps(item)}", flush=True)
        self._send(200, {"status": "received", "count": len(batch), "total": len(DECISIONS)})

    def log_message(self, *args):
        pass  # quiet default per-request logging; we print items ourselves


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)  # binds here — fail loudly if port is busy
    print(f"mock endpoint listening on http://{HOST}:{PORT}")
    print("  POST /decisions   GET /decisions   GET /health\n")
    server.serve_forever()
