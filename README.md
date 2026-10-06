# SAVAGE Mini Program OpenAPI

Unofficial OpenAPI 3.1 documentation and a Codex skill for the SAVAGE WeChat Mini Program. It can list classes, check inventory, settle an order, and create one unpaid order. It never pays.

Use this only with an account that you own or control. The observed API can change without notice.

## Install the skill

```bash
git clone https://github.com/celezhe/savage-miniapp-openapi.git
cp -R savage-miniapp-openapi ~/.codex/skills/savage-miniapp-openapi
```

## Token

Use Proxyman with SSL Proxying limited to `wechat-api.savagepark.com.cn`. Log in through the official WeChat client and copy the bearer value from a SAVAGE request. Save it outside this repository:

```bash
chmod 600 /absolute/path/to/token
export SAVAGE_TOKEN_FILE=/absolute/path/to/token
```

The login response `expireTime` is the observed TTL source. No refresh token was observed. Get a new `wx.login()` code after a `401`.

Disable the system proxy and remove the Proxyman CA after inspection.

## CLI

```bash
python3 scripts/savage_api.py classes query.json
python3 scripts/savage_api.py inventory 12345678
python3 scripts/savage_api.py orders --scene TO_PAY
python3 scripts/savage_api.py settle 12345678
python3 scripts/savage_api.py book-unpaid 12345678
```

`book-unpaid` requires an exact interactive confirmation. It sends at most one `order/place` request. It does not call a payment API.

## Files

- `openapi.yaml`: observed API contract.
- `SKILL.md`: token and booking workflow.
- `scripts/savage_api.py`: guarded client.

Do not commit tokens, login codes, proxy captures, or API responses.
