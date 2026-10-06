import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest


@pytest.fixture
def api_server():
    state = {"responses": {}, "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            state["requests"].append((self.path, body, self.headers.get("Authorization")))
            configured = state["responses"].get(self.path, {"code": 200, "msg": "OK", "data": {}})
            if isinstance(configured, Exception):
                self.connection.shutdown(2)
                self.connection.close()
                return
            status, response = configured if isinstance(configured, tuple) else (200, configured)
            payload = json.dumps(response).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state["url"] = f"http://127.0.0.1:{server.server_port}"
    yield state
    server.shutdown()
    server.server_close()
    thread.join()
