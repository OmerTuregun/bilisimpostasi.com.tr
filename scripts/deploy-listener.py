#!/usr/bin/env python3
"""Minimal deploy trigger for n8n over the docker bridge only."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

LOG = logging.getLogger("agent-icerik-deploy-listener")

BIND_HOST = os.environ.get("DEPLOY_LISTENER_BIND", "172.18.0.1")
PORT = int(os.environ.get("DEPLOY_LISTENER_PORT", "9876"))
TOKEN = os.environ.get("DEPLOY_LISTENER_TOKEN", "")
SCRIPT = os.environ.get("DEPLOY_SCRIPT", "/root/agent-icerik-sistemi/scripts/build-and-deploy-site.sh")
LOCK_FILE = os.environ.get("DEPLOY_LOCK_FILE", "/var/lock/agent-icerik-deploy.lock")
TIMEOUT = int(os.environ.get("DEPLOY_TIMEOUT_SEC", "30"))


class DeployHandler(BaseHTTPRequestHandler):
    server_version = "AgentIcerikDeployListener/1.0"

    def log_message(self, fmt: str, *args) -> None:
        LOG.info("%s - %s", self.address_string(), fmt % args)

    def _reject(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self._reject(405, b"Method Not Allowed")

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/deploy":
            self._reject(404, b"Not Found")
            return

        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {TOKEN}"
        if not TOKEN or auth != expected:
            LOG.warning("Unauthorized deploy request from %s", self.address_string())
            self._reject(401, b"Unauthorized")
            return

        LOG.info("Deploy requested from %s", self.address_string())
        try:
            result = subprocess.run(
                [
                    "flock",
                    "-w",
                    str(TIMEOUT),
                    LOCK_FILE,
                    "sudo",
                    "-n",
                    SCRIPT,
                ],
                capture_output=True,
                text=True,
                timeout=TIMEOUT + 5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            LOG.error("Deploy timed out after %ss", TIMEOUT + 5)
            self._reject(504, b"Deploy timeout")
            return

        if result.stdout:
            LOG.info("deploy stdout: %s", result.stdout.strip()[-2000:])
        if result.stderr:
            LOG.info("deploy stderr: %s", result.stderr.strip()[-2000:])

        if result.returncode == 0:
            LOG.info("Deploy succeeded")
            self._reject(200, b"OK")
            return

        LOG.error("Deploy failed with exit code %s", result.returncode)
        body = (result.stderr or result.stdout or "deploy failed").encode("utf-8", errors="replace")[:2000]
        self._reject(500, body or b"deploy failed")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )

    if not TOKEN:
        LOG.error("DEPLOY_LISTENER_TOKEN is required")
        sys.exit(1)

    server = ThreadingHTTPServer((BIND_HOST, PORT), DeployHandler)
    LOG.info("Listening on http://%s:%s/deploy", BIND_HOST, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("Shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
