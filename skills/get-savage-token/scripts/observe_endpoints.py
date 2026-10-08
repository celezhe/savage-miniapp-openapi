"""Record redacted SAVAGE endpoint shapes from mitmdump traffic."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from mitmproxy import ctx, http


HOST = "wechat-api.savagepark.com.cn"


def object_keys(value: object) -> list[str]:
    return sorted(value) if isinstance(value, dict) else []


class ObserveSavageEndpoints:
    def response(self, flow: http.HTTPFlow) -> None:
        if flow.request.pretty_host != HOST:
            return
        try:
            request_json = flow.request.json()
        except (json.JSONDecodeError, ValueError):
            request_json = None
        try:
            response_json = flow.response.json()
        except (json.JSONDecodeError, ValueError):
            response_json = None

        envelope_code = response_json.get("code") if isinstance(response_json, dict) else None
        data = response_json.get("data") if isinstance(response_json, dict) else None
        record = {
            "timeUtc": datetime.now(timezone.utc).isoformat(),
            "method": flow.request.method,
            "path": flow.request.path.split("?", 1)[0],
            "requestKeys": object_keys(request_json),
            "httpStatus": flow.response.status_code,
            "envelopeCode": envelope_code,
            "dataKeys": object_keys(data),
        }
        destination = os.environ.get("SAVAGE_ENDPOINT_LOG")
        if not destination:
            ctx.log.info(json.dumps(record, ensure_ascii=False))
            return
        path = Path(destination).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        os.chmod(path, 0o600)


addons = [ObserveSavageEndpoints()]
