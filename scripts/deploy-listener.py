#!/usr/bin/env python3
"""Deploy + R2 upload helper for n8n over the docker bridge only."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

LOG = logging.getLogger("agent-icerik-deploy-listener")

BIND_HOST = os.environ.get("DEPLOY_LISTENER_BIND", "172.18.0.1")
PORT = int(os.environ.get("DEPLOY_LISTENER_PORT", "9876"))
TOKEN = os.environ.get("DEPLOY_LISTENER_TOKEN", "")
SCRIPT = os.environ.get("DEPLOY_SCRIPT", "/root/agent-icerik-sistemi/scripts/build-and-deploy-site.sh")
LOCK_FILE = os.environ.get("DEPLOY_LOCK_FILE", "/var/lock/agent-icerik-deploy.lock")
TIMEOUT = int(os.environ.get("DEPLOY_TIMEOUT_SEC", "300"))
ENV_PATH = Path(os.environ.get("R2_ENV_PATH", "/root/agent-icerik-sistemi/n8n/.env"))
KEY_RE = re.compile(r"^covers/[A-Za-z0-9._-]{1,200}\.jpe?g$", re.I)


def load_r2_env() -> dict[str, str]:
    # Prefer process env (systemd EnvironmentFile); fall back to n8n .env for local runs.
    keys = (
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET_NAME",
    )
    if all(os.environ.get(k) for k in keys):
        return {k: os.environ[k] for k in keys}
    env: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"')
    return env


def put_r2(key: str, body: bytes, content_type: str = "image/jpeg") -> None:
    import boto3
    from botocore.config import Config

    env = load_r2_env()
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )
    client.put_object(
        Bucket=env["R2_BUCKET_NAME"],
        Key=key,
        Body=body,
        ContentType=content_type or "image/jpeg",
    )


class DeployHandler(BaseHTTPRequestHandler):
    server_version = "AgentIcerikDeployListener/1.1"

    def log_message(self, fmt: str, *args) -> None:
        LOG.info("%s - %s", self.address_string(), fmt % args)

    def _reject(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self) -> bool:
        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {TOKEN}"
        return bool(TOKEN) and auth == expected

    def do_GET(self) -> None:
        self._reject(405, b"Method Not Allowed")

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/deploy":
            self._handle_deploy()
            return
        if path == "/r2-upload":
            self._handle_r2_upload()
            return
        self._reject(404, b"Not Found")

    def _handle_deploy(self) -> None:
        if not self._auth_ok():
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

    def _handle_r2_upload(self) -> None:
        if not self._auth_ok():
            LOG.warning("Unauthorized r2-upload from %s", self.address_string())
            self._reject(401, b"Unauthorized")
            return

        key = (self.headers.get("X-R2-Key") or "").strip().lstrip("/")
        if not KEY_RE.match(key):
            self._reject(400, b"Invalid X-R2-Key")
            return

        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0 or length > 15_000_000:
            self._reject(400, b"Invalid Content-Length")
            return

        body = self.rfile.read(length)
        if len(body) < 100 or body[:2] != b"\xff\xd8":
            self._reject(400, b"Body must be a JPEG")
            return

        ctype = self.headers.get("Content-Type") or "image/jpeg"
        try:
            put_r2(key, body, ctype)
        except Exception as e:
            LOG.exception("R2 upload failed for %s", key)
            self._reject(502, f"R2 upload failed: {e}".encode("utf-8", errors="replace")[:500])
            return

        LOG.info("R2 upload ok key=%s bytes=%s", key, len(body))
        self._reject(200, b"OK")


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
    LOG.info("Listening on http://%s:%s/deploy and /r2-upload", BIND_HOST, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("Shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
