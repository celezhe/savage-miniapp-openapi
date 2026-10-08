---
name: savage-miniapp-openapi
description: "Use for the SAVAGE WeChat Mini Program API: get and store a bearer token, read the account profile, list classes, find a schedule ID, check inventory, settle a class, or create one unpaid order without payment."
---

# SAVAGE Mini Program OpenAPI

Use this skill only for an account that the user owns or controls. Treat every token and API response as private.

## Choose a workflow

- For a missing or expired token, use **Get a token**.
- For schedules only, stop after **List classes**.
- For account information, run `python3 scripts/savage_api.py profile` and stop.
- For an unpaid reservation, follow **Book one unpaid class** in order.

## Get a token

1. Open the official SAVAGE Mini Program in WeChat. Use `wx.login()` through the official client; do not invent a code.
2. In Proxyman, install and trust its CA certificate in macOS Keychain Access.
3. Enable SSL Proxying only for `wechat-api.savagepark.com.cn`. Do not inspect unrelated WeChat traffic.
4. Complete a normal SAVAGE login or refresh in WeChat.
5. Find a SAVAGE API request and copy only its bearer value from the `Authorization` header.
6. Save the value without the `Bearer ` prefix to a private local file. Do not paste it into chat, logs, source files, shell history, or Git.
7. Run `chmod 600 /absolute/path/to/token` and set `SAVAGE_TOKEN_FILE` to that path.
8. Disable the system proxy and SSL Proxying. Remove the Proxyman CA when inspection is no longer needed.

The login response `expireTime` is the only observed TTL source. One captured response set it about 30 days after login. The measured difference was 2,592,002 seconds. Treat this value as evidence for that login, not as a permanent service guarantee.

The token can look like a JWT but can omit `exp`, `iat`, and `nbf`. No refresh token was observed. If an API response has code `401`, repeat this workflow with a new `wx.login()` code.

## Book one unpaid class

Perform these steps in this exact order:

1. **List classes.** Run `python3 scripts/savage_api.py classes QUERY.json`. Select the exact date, location, start time, class name, and `scheduleId`.
2. **Check inventory.** Run `python3 scripts/savage_api.py inventory SCHEDULE_ID`. Continue only when the status is available, such as `NORMAL`.
3. **Check `TO_PAY`.** Run `python3 scripts/savage_api.py orders --scene TO_PAY`. Stop if a matching `scheduleId` already has an unpaid order.
4. **Settle.** Run `python3 scripts/savage_api.py settle SCHEDULE_ID`. Show the user the class, location, date, time, payable amount, and any deadline. Do not place yet.
5. Get **explicit approval** from the user for that exact summary. Old approval does not apply to a changed schedule or settlement.
6. After approval, run `python3 scripts/savage_api.py book-unpaid SCHEDULE_ID`. Allow one `order/place` attempt only.
7. **Query the order.** Confirm the returned order with the order-list or status endpoint and report the unpaid deadline.

Do not pay. Never call a prepay endpoint or `wx.requestPayment`. Do not make concurrent booking requests or use high-frequency polling.

## Failure rules

- On `401`, stop and use **Get a token**. Do not claim a refresh token exists.
- On `411` or `412`, stop and show the business message.
- On `429`, stop. Do not retry in a loop.
- On `400` or `500`, stop and show the redacted API message.
- On a network timeout after `order/place`, treat the result as uncertain. Run `orders --scene TO_PAY` and reconcile the `scheduleId` before any new approval or attempt.
- Never reveal the token in output or error text.

Use `openapi.yaml` for the observed request and response schemas. Remember that the API is unofficial and can change.
