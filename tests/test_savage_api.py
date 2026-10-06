import socket

import pytest

from scripts.savage_api import ApiError, ApprovalRequired, SavageClient, UncertainPlacement


def envelope(data):
    return {"code": 200, "msg": "OK", "data": data}


def client(api_server):
    return SavageClient("secret-token", base_url=api_server["url"], timeout=0.2)


def test_list_inventory_settle_and_place_flow(api_server):
    api_server["responses"].update({
        "/groupClass/schedule/scroll": envelope({"list": [{"scheduleId": 12345678}]}),
        "/inventory/status/batch-query": envelope({"items": [{"bizItemId": 12345678, "status": "NORMAL"}]}),
        "/order/list": envelope({"orders": []}),
        "/order/settle/groupClass": envelope({"settlementId": "S", "settlementVersion": 1, "item": {"variantCode": "V", "tempItemId": "T"}, "assetAllocations": []}),
        "/order/place": envelope({"orderId": "O", "needPrepay": True}),
    })
    api = client(api_server)
    assert api.list_classes({"cursor": "", "limit": 50})["list"][0]["scheduleId"] == 12345678
    assert api.inventory(12345678)[0]["status"] == "NORMAL"
    result = api.book_unpaid(12345678, approved=True)
    assert result == {"orderId": "O", "needPrepay": True}
    paths = [request[0] for request in api_server["requests"]]
    assert paths[-4:] == ["/inventory/status/batch-query", "/order/list", "/order/settle/groupClass", "/order/place"]


def test_unavailable_inventory_stops_before_order_calls(api_server):
    api_server["responses"]["/inventory/status/batch-query"] = envelope({"items": [{"bizItemId": 12345678, "status": "SOLD_OUT"}]})
    with pytest.raises(ApiError, match="not available"):
        client(api_server).book_unpaid(12345678, approved=True)
    assert [item[0] for item in api_server["requests"]] == ["/inventory/status/batch-query"]


def test_server_error_after_place_is_uncertain(api_server):
    api_server["responses"]["/order/place"] = (500, {"code": 500, "msg": "unknown", "data": None})
    with pytest.raises(UncertainPlacement):
        client(api_server).place({"settlementId": "S", "settlementVersion": 1, "variantCode": "V", "tempItemId": "T", "assetAllocations": []}, 12345678, approved=True)


@pytest.mark.parametrize("code", [400, 401, 411, 412, 429, 500])
def test_business_error_in_http_200_stops(api_server, code):
    api_server["responses"]["/order/list"] = {"code": code, "msg": "stop", "data": None}
    with pytest.raises(ApiError, match=f"API {code}: stop"):
        client(api_server).list_orders("TO_PAY")


def test_http_error_redacts_token(api_server):
    api_server["responses"]["/order/list"] = (401, {"code": 401, "msg": "secret-token rejected", "data": None})
    with pytest.raises(ApiError) as caught:
        client(api_server).list_orders("TO_PAY")
    assert "secret-token" not in str(caught.value)
    assert "[REDACTED]" in str(caught.value)


def test_existing_unpaid_order_stops_before_settlement(api_server):
    api_server["responses"]["/inventory/status/batch-query"] = envelope({"items": [{"bizItemId": 12345678, "status": "NORMAL"}]})
    api_server["responses"]["/order/list"] = envelope({"orders": [{"orderId": "OLD", "scheduleId": 12345678}]})
    with pytest.raises(ApiError, match="already exists"):
        client(api_server).book_unpaid(12345678, approved=True)
    assert [item[0] for item in api_server["requests"]] == ["/inventory/status/batch-query", "/order/list"]


def test_missing_settlement_fields_stops_before_place(api_server):
    api_server["responses"]["/inventory/status/batch-query"] = envelope({"items": [{"bizItemId": 12345678, "status": "NORMAL"}]})
    api_server["responses"]["/order/list"] = envelope({"orders": []})
    api_server["responses"]["/order/settle/groupClass"] = envelope({"settlementId": "S"})
    with pytest.raises(ApiError, match="missing fields"):
        client(api_server).book_unpaid(12345678, approved=True)
    assert "/order/place" not in [item[0] for item in api_server["requests"]]


def test_place_requires_explicit_approval(api_server):
    with pytest.raises(ApprovalRequired):
        client(api_server).place({"settlementId": "S"}, 12345678, approved=False)
    assert api_server["requests"] == []


def test_timeout_after_place_reconciles_without_second_place(api_server):
    api_server["responses"]["/order/place"] = socket.timeout("timed out")
    api_server["responses"]["/order/list"] = envelope({"orders": [{"orderId": "O", "scheduleId": 12345678}]})
    api = client(api_server)
    with pytest.raises(UncertainPlacement) as caught:
        api.place({"settlementId": "S", "settlementVersion": 1, "variantCode": "V", "tempItemId": "T", "assetAllocations": []}, 12345678, approved=True)
    assert caught.value.schedule_id == 12345678
    assert api.reconcile(caught.value)["orderId"] == "O"
    assert [item[0] for item in api_server["requests"]].count("/order/place") == 1
