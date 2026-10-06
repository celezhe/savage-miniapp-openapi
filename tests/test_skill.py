from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]


def test_skill_has_valid_identity_and_interface():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    _, frontmatter, _ = skill.split("---", 2)
    metadata = yaml.safe_load(frontmatter)
    assert metadata["name"] == "savage-miniapp-openapi"
    assert set(metadata) == {"name", "description"}
    interface = yaml.safe_load((ROOT / "agents/openai.yaml").read_text())
    assert "$savage-miniapp-openapi" in interface["interface"]["default_prompt"]


def test_skill_defines_safe_token_workflow():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for requirement in ["wx.login()", "wechat-api.savagepark.com.cn", "Proxyman", "chmod 600", "expireTime", "401"]:
        assert requirement in skill
    assert "refresh token" in skill.lower()
    assert "SAVAGE_TOKEN_FILE" in skill


def test_skill_defines_guarded_booking_workflow():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    ordered_terms = ["List classes", "Check inventory", "TO_PAY", "Settle", "explicit approval", "order/place", "Query the order"]
    positions = [skill.index(term) for term in ordered_terms]
    assert positions == sorted(positions)
    for requirement in ["one `order/place`", "429", "timeout", "Do not pay"]:
        assert requirement in skill


def test_pressure_scenarios_have_expected_safe_outcomes():
    scenarios = (ROOT / "tests/skill_scenarios.md").read_text(encoding="utf-8")
    for heading in ["Token capture", "List classes", "Book without payment", "Uncertain placement", "Unsafe retry request"]:
        assert heading in scenarios
    for outcome in ["No secret output", "Explicit approval", "Reconcile TO_PAY", "Stop on 429", "No payment"]:
        assert outcome in scenarios
