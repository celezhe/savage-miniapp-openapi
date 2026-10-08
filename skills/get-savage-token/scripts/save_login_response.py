#!/usr/bin/env python3
"""Store a SAVAGE login token without exposing it in argv or output."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import tempfile


def parse_expiration(value: object) -> datetime:
    if not isinstance(value, (int, str)) or not str(value).isdigit():
        raise ValueError("expireTime must be a Unix timestamp")
    timestamp = int(value)
    if timestamp > 10_000_000_000:
        timestamp /= 1000
    return datetime.fromtimestamp(timestamp, timezone.utc)


def update_env(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text().splitlines() if path.exists() else []
    replacement = f"SAVAGE_TOKEN={token}"
    output: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith("SAVAGE_TOKEN="):
            if not replaced:
                output.append(replacement)
                replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(replacement)

    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write("\n".join(output) + "\n")
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    args = parser.parse_args()

    raw = getpass.getpass("Paste the SAVAGE login JSON response (input is hidden): ")
    envelope = json.loads(raw)
    if envelope.get("code") != 200 or not isinstance(envelope.get("data"), dict):
        raise ValueError("login response is not a successful SAVAGE envelope")
    data = envelope["data"]
    token = data.get("token")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("login response does not contain a token")
    expiration = parse_expiration(data.get("expireTime"))

    update_env(args.env_file.expanduser().resolve(), token.strip())
    remaining = int((expiration - datetime.now(timezone.utc)).total_seconds())
    print(f"Saved securely. Expires UTC: {expiration.isoformat()}")
    print(f"Remaining TTL seconds: {remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
