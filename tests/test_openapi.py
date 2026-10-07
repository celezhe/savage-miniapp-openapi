from pathlib import Path
import re

import yaml


ROOT = Path(__file__).parents[1]
SPEC_PATH = ROOT / "openapi.yaml"


def load_spec():
    assert SPEC_PATH.exists(), "openapi.yaml must exist"
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def test_required_operations_are_documented():
    spec = load_spec()
    expected = {
        "/auth/wechat/login": "loginWithWechatCode",
        "/user/profile/detail": "getUserProfile",
        "/groupClass/schedule/scroll": "listGroupClassSchedules",
        "/groupClass/schedule/detail": "getGroupClassSchedule",
        "/inventory/status/batch-query": "getInventoryStatus",
        "/order/settle/groupClass": "settleGroupClassOrder",
        "/order/place": "placeGroupClassOrder",
        "/order/query/status": "getOrderStatus",
        "/order/list": "listOrders",
        "/order/detail": "getOrderDetail",
    }
    assert {
        path: spec["paths"][path]["post"]["operationId"] for path in expected
    } == expected


def test_protected_operations_use_bearer_auth():
    spec = load_spec()
    assert spec["components"]["securitySchemes"]["bearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    public = {
        "/auth/wechat/login",
        "/base/biz-city-info",
        "/groupClass/schedule/getFilterData",
        "/groupClass/schedule/scroll",
        "/groupClass/schedule/detail",
    }
    for path, item in spec["paths"].items():
        operation = item["post"]
        if path in public:
            assert operation.get("security") == []
        else:
            assert operation.get("security") == [{"bearerAuth": []}]


def test_payment_operations_are_absent():
    serialized = SPEC_PATH.read_text(encoding="utf-8") if SPEC_PATH.exists() else ""
    assert "payment/prepay" not in serialized
    assert "wx.requestPayment" not in serialized


def test_place_declares_real_order_side_effect():
    operation = load_spec()["paths"]["/order/place"]["post"]
    assert operation["x-side-effects"] == {
        "createsUnpaidOrder": True,
        "mayReserveInventory": True,
        "requiresExplicitUserApproval": True,
    }


def test_examples_contain_no_secret_shapes():
    text = SPEC_PATH.read_text(encoding="utf-8") if SPEC_PATH.exists() else ""
    jwt = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
    assert not jwt.search(text)
    assert "Bearer eyJ" not in text


def test_business_error_envelopes_are_documented():
    spec = load_spec()
    examples = spec["components"]["schemas"]["ErrorEnvelope"]["examples"]
    assert {item["code"] for item in examples} == {400, 401, 411, 412, 429, 500}
    for path_item in spec["paths"].values():
        response = path_item["post"]["responses"]["200"]
        if "$ref" in response:
            response = spec["components"]["responses"][response["$ref"].rsplit("/", 1)[1]]
        schema = response["content"]["application/json"]["schema"]
        assert schema["oneOf"][1]["$ref"] == "#/components/schemas/ErrorEnvelope"
