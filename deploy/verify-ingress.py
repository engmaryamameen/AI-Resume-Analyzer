"""Run against the supplied nginx config with a local echo backend; needs Docker.

No user data or production containers are touched. HTTP listeners bind loopback only.
"""

import contextlib
import http.client
import json
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Echo(BaseHTTPRequestHandler):
    def do_GET(self):
        data = json.dumps({"forwarded": self.headers.get("X-Forwarded-For")}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def main():
    with tempfile.TemporaryDirectory(prefix="resume-ingress-") as directory:
        config = (
            (ROOT / "deploy/nginx.conf")
            .read_text()
            .replace("listen 8080;", "listen 127.0.0.1:8099;")
            .replace("api:8000", "api:8018")
            .replace("web:3000", "web:8018")
        )
        path = Path(directory) / "nginx.conf"
        path.write_text(config)
        server = HTTPServer(("127.0.0.1", 8018), Echo)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        container = subprocess.Popen(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "host",
                "--add-host",
                "api:127.0.0.1",
                "--add-host",
                "web:127.0.0.1",
                "-v",
                f"{path}:/etc/nginx/nginx.conf:ro",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,size=64m",
                "--user",
                "101:101",
                "--cap-drop",
                "ALL",
                "--entrypoint",
                "nginx",
                "nginx:1.28-alpine",
                "-g",
                "daemon off;",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen(
                        "http://127.0.0.1:8099/", timeout=1
                    ) as response:
                        assert response.status == 200
                    break
                except OSError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("Ingress did not start")
            request = urllib.request.Request(
                "http://127.0.0.1:8099/api/v1/guest",
                headers={"X-Forwarded-For": "6.6.6.6, 1.2.3.4"},
            )
            with urllib.request.urlopen(request) as response:
                assert json.load(response)["forwarded"] == "127.0.0.1"
            connection = http.client.HTTPConnection("127.0.0.1", 8099, timeout=5)
            connection.request(
                "POST",
                "/api/v1/guest/analyze",
                body=(b"x" * 65536 for _ in range(90)),
                encode_chunked=True,
            )
            response = connection.getresponse()
            assert response.status == 413
            assert json.loads(response.read())["error"]["code"] == "payload_too_large"
            connection.close()
            # Slow client begins a chunk and never completes it. The edge must close after 10s.
            with socket.create_connection(("127.0.0.1", 8099), timeout=15) as slow:
                slow.sendall(
                    b"POST /api/v1/guest/analyze HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\n\r\n100\r\nx"
                )
                started = time.monotonic()
                reply = slow.recv(4096)
                assert not reply or b"408" in reply
                assert time.monotonic() - started < 14
            print(
                json.dumps(
                    {
                        "status": "passed",
                        "checks": [
                            "nginx configuration starts unprivileged",
                            "supplied XFF replaced",
                            "chunked body cap returns JSON 413",
                            "slow body timeout closes connection",
                        ],
                    }
                )
            )
        finally:
            container.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                container.wait(timeout=5)
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
