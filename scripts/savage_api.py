#!/usr/bin/env python3
"""Small guarded client for observed SAVAGE Mini Program endpoints."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://wechat-api.savagepark.com.cn/backend-api"


class ApiError(RuntimeError):
    """The API rejected a request or returned malformed data."""


class ApprovalRequired(ApiError):
    """A real order was blocked because the user did not approve it."""


class UncertainPlacement(ApiError):
    """The connection failed after placement began; reconcile before retrying."""

    def __init__(self, schedule_id: int):
        super().__init__("Order result is uncertain; query TO_PAY before any retry")
        self.schedule_id = schedule_id


class SavageClient:
    def __init__(self, token: str, base_url: str = DEFAULT_BASE_URL, timeout: float = 10.0):
        if not token:
            raise ValueError("token is required")
        self._token = token.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._placement_attempts: set[int] = set()

    def _redact(self, text: str) -> str:
        return text.replace(self._token, "[REDACTED]")

    def _post(self, path: str, payload: dict[str, Any], *, placement: bool = False) -> Any:
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read())
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            if placement and exc.code >= 500:
                raise UncertainPlacement(payload["items"][0]["bizItemId"]) from None
            try:
                message = json.loads(raw).get("msg", raw)
            except json.JSONDecodeError:
                message = raw
            raise ApiError(self._redact(f"HTTP {exc.code}: {message}")) from None
        except (URLError, OSError, TimeoutError) as exc:
            if placement:
                raise UncertainPlacement(payload["items"][0]["bizItemId"]) from None
            raise ApiError(self._redact(f"Network error: {exc}")) from None
        if not isinstance(body, dict) or "code" not in body:
            if placement:
                raise UncertainPlacement(payload["items"][0]["bizItemId"])
            raise ApiError("Malformed API envelope")
        if body["code"] != 200:
            if placement and int(body["code"]) >= 500:
                raise UncertainPlacement(payload["items"][0]["bizItemId"])
            raise ApiError(self._redact(f"API {body['code']}: {body.get('msg', 'Unknown error')}"))
        return body.get("data")

    def list_classes(self, query: dict[str, Any]) -> dict[str, Any]:
        return self._post("/groupClass/schedule/scroll", query)

    def inventory(self, schedule_id: int) -> list[dict[str, Any]]:
        data = self._post("/inventory/status/batch-query", {"items": [{"bizItemId": schedule_id, "productType": "GROUP_CLASS"}]})
        return data.get("items", data) if isinstance(data, dict) else data

    def list_orders(self, scene: str = "TO_PAY") -> dict[str, Any]:
        data = self._post("/order/list", {"lastOrderId": "", "scene": scene})
        if isinstance(data, dict) and "orders" in data:
            return {**data, "list": data["orders"]}
        return data

    def settle(self, schedule_id: int) -> dict[str, Any]:
        data = self._post("/order/settle/groupClass", {"firstSettle": True, "quantity": 1, "scheduleId": schedule_id})
        if isinstance(data, dict) and isinstance(data.get("item"), dict):
            data = {**data, **data["item"]}
        required = {"settlementId", "settlementVersion", "variantCode", "tempItemId"}
        missing = sorted(required - set(data or {}))
        if missing:
            raise ApiError(f"Settlement is missing fields: {', '.join(missing)}")
        return data

    def place(self, settlement: dict[str, Any], schedule_id: int, *, approved: bool) -> dict[str, Any]:
        if not approved:
            raise ApprovalRequired("Explicit approval is required before order/place")
        if schedule_id in self._placement_attempts:
            raise ApiError("A placement was already attempted; query TO_PAY before any retry")
        self._placement_attempts.add(schedule_id)
        payload = {
            "assetAllocations": settlement.get("assetAllocations", []),
            "settlementId": settlement["settlementId"],
            "settlementVersion": settlement["settlementVersion"],
            "waitDeadlineOption": "",
            "items": [{
                "bizItemId": schedule_id,
                "quantity": 1,
                "productType": "GROUP_CLASS",
                "itemSceneCode": "GROUP_CLASS",
                "variantCode": settlement["variantCode"],
                "tempItemId": settlement["tempItemId"],
            }],
            "useSavageCard": False,
        }
        return self._post("/order/place", payload, placement=True)

    def book_unpaid(self, schedule_id: int, *, approved: bool) -> dict[str, Any]:
        inventory = self.inventory(schedule_id)
        if not inventory or inventory[0].get("status") != "NORMAL":
            raise ApiError("Class inventory is not available")
        orders = self.list_orders("TO_PAY").get("list", [])
        if orders:
            raise ApiError("An unpaid order already exists; reconcile it before another placement")
        settlement = self.settle(schedule_id)
        return self.place(settlement, schedule_id, approved=approved)

    def reconcile(self, uncertain: UncertainPlacement) -> dict[str, Any] | None:
        orders = self.list_orders("TO_PAY").get("list", [])
        return next((item for item in orders if item.get("scheduleId") == uncertain.schedule_id), None)


def read_token(path: Path) -> str:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise ApiError(f"Token file permissions must be 600 or stricter, found {mode:o}")
    return path.read_text(encoding="utf-8").strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    sub = parser.add_subparsers(dest="command", required=True)
    classes = sub.add_parser("classes")
    classes.add_argument("query_file", type=Path)
    inventory = sub.add_parser("inventory")
    inventory.add_argument("schedule_id", type=int)
    orders = sub.add_parser("orders")
    orders.add_argument("--scene", default="TO_PAY")
    settle = sub.add_parser("settle")
    settle.add_argument("schedule_id", type=int)
    book = sub.add_parser("book-unpaid")
    book.add_argument("schedule_id", type=int)
    args = parser.parse_args(argv)
    try:
        token_path = Path(os.environ["SAVAGE_TOKEN_FILE"])
        api = SavageClient(read_token(token_path), base_url=args.base_url)
        if args.command == "classes":
            result = api.list_classes(json.loads(args.query_file.read_text()))
        elif args.command == "inventory":
            result = api.inventory(args.schedule_id)
        elif args.command == "orders":
            result = api.list_orders(args.scene)
        elif args.command == "settle":
            result = api.settle(args.schedule_id)
        else:
            inventory_result = api.inventory(args.schedule_id)
            if not inventory_result or inventory_result[0].get("status") != "NORMAL":
                raise ApiError("Class inventory is not available")
            if api.list_orders("TO_PAY").get("list", []):
                raise ApiError("An unpaid order already exists; reconcile it before another placement")
            preview = api.settle(args.schedule_id)
            print(json.dumps({"scheduleId": args.schedule_id, "settlement": preview}, ensure_ascii=False, indent=2))
            approval = input("Type PLACE UNPAID ORDER to continue: ")
            placement = api.place(preview, args.schedule_id, approved=approval == "PLACE UNPAID ORDER")
            result = {"placement": placement, "toPay": api.list_orders("TO_PAY")}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ApiError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
