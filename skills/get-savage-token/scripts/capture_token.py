"""mitmdump addon that stores a valid SAVAGE token without printing it."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from mitmproxy import ctx, http

from save_login_response import parse_expiration, update_env


HOST = "wechat-api.savagepark.com.cn"
LOGIN_PATH = "/backend-api/auth/wechat/login"


class CaptureSavageToken:
    saved = False

    def _save(self, token: str, expire_time: object | None = None) -> None:
        destination = os.environ.get("SAVAGE_ENV_FILE")
        if not destination:
            ctx.log.error("SAVAGE_ENV_FILE is required")
            return
        update_env(Path(destination).expanduser().resolve(), token)
        if expire_time is not None:
            expiration = parse_expiration(expire_time)
            remaining = int((expiration - datetime.now(timezone.utc)).total_seconds())
            ctx.log.info(f"SAVAGE token saved; expires UTC {expiration.isoformat()}")
            ctx.log.info(f"Remaining TTL seconds: {remaining}")
        else:
            ctx.log.info("Valid SAVAGE token saved; expiration was not present in this response")
        self.saved = True
        ctx.master.shutdown()

    def response(self, flow: http.HTTPFlow) -> None:
        if self.saved or flow.request.pretty_host != HOST:
            return
        try:
            envelope = flow.response.json()
        except (json.JSONDecodeError, ValueError):
            return
        if not isinstance(envelope, dict) or envelope.get("code") != 200:
            return

        if flow.request.path.split("?", 1)[0] == LOGIN_PATH:
            data = envelope.get("data")
            if isinstance(data, dict) and isinstance(data.get("token"), str):
                self._save(data["token"].strip(), data.get("expireTime"))
                return

        authorization = flow.request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
            if token:
                self._save(token)


addons = [CaptureSavageToken()]
