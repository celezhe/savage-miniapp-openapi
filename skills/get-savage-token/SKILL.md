---
name: get-savage-token
description: Safely capture, store, validate, and rotate a SAVAGE WeChat Mini Program bearer token. Use when the SAVAGE token is missing, expired, revoked, near its expireTime, or when the user asks to renew the monthly SAVAGE login credential.
---

# Get a SAVAGE Token

Use only an account that the user owns or controls. Treat the login response, bearer token, account data, and interception logs as secrets.

## Default workflow: Proxyman

1. Start Proxyman and confirm that its CA is installed and trusted in macOS Keychain Access.
2. Enable SSL Proxying only for `wechat-api.savagepark.com.cn`. Do not inspect unrelated WeChat traffic.
3. Open the official SAVAGE Mini Program in WeChat and complete its normal login or refresh flow.
4. Find `POST /backend-api/auth/wechat/login` in Proxyman.
5. Inspect its JSON response. Confirm that the envelope has `code: 200` and that `data` contains `token` and `expireTime`.
6. Never paste the response or token into chat, logs, source files, command arguments, or shell history.

The WeChat `wx.login()` code belongs to the SAVAGE Mini Program app identity. A different Mini Program cannot exchange its own code for a SAVAGE token.

## Experimental workflow: mitmdump

Install the CLI without the quarantined macOS app bundle:

```bash
uv tool install mitmproxy
```

Start `mitmdump` once to create `~/.mitmproxy/mitmproxy-ca-cert.pem`. Add that certificate to the system keychain and trust it for SSL. Then run:

```bash
SAVAGE_ENV_FILE=/absolute/private/path/.env \
  ~/.local/bin/mitmdump --listen-port 9090 --set flow_detail=0 \
  --scripts scripts/capture_token.py
```

Set the active macOS network service's HTTP and HTTPS proxy to `127.0.0.1:9090`. Open or refresh the official SAVAGE Mini Program. The addon accepts traffic only from `wechat-api.savagepark.com.cn`. It saves a token only after a successful SAVAGE response, never prints the token, and exits after capture.

The fastest path captures the bearer value from any successful SAVAGE API request. A login response is better because it also supplies `expireTime`. If the current token is expired or revoked, complete the normal login flow so the addon can capture `POST /backend-api/auth/wechat/login`.

This workflow is experimental. In an October 2026 test, both the regular proxy and Local Capture reached the network, but the WeChat Mini Program runtime rejected mitmproxy's dynamic TLS certificate and SAVAGE showed "加载失败请重试". Do not make mitmdump the default until a clean end-to-end capture succeeds on the current WeChat build.

Always disable both system proxies and stop Local Capture after `mitmdump` exits. A proxy left at port 9090 with no listener causes apparent network failures.

To discover endpoint shapes without recording sensitive values, run the bundled observer as a separate session:

```bash
SAVAGE_ENDPOINT_LOG=/absolute/private/path/endpoints.jsonl \
  ~/.local/bin/mitmdump --listen-port 9090 --set flow_detail=0 \
  --scripts scripts/observe_endpoints.py
```

The observer records only the HTTP method, path, request field names, HTTP status, envelope code, and top-level response-data field names. Keep the output outside Git. Do not trigger a booking, cancellation, or payment merely to observe an endpoint.

## Store it safely

Run the bundled script and paste the complete login response only into its hidden prompt:

```bash
python3 scripts/save_login_response.py --env-file /absolute/private/path/.env
```

The script extracts the token, atomically updates `SAVAGE_TOKEN`, preserves unrelated `.env` entries, and sets the file mode to `600`. It prints only expiration metadata. It never prints the token.

Keep the `.env` file outside public repositories. Confirm all of the following:

- The path is ignored by Git.
- `stat -f '%Lp' /absolute/private/path/.env` prints `600` on macOS.
- No HAR, Proxyman session, login response, or token file is staged in Git.

## Validate without exposing data

Load the token into the process without printing it. Call only this read-only endpoint for validation:

```text
POST https://wechat-api.savagepark.com.cn/backend-api/order/list
{"lastOrderId":"","scene":"TO_PAY"}
```

Report only the UTC check time, HTTP status, and envelope `code`. Do not report orders, account fields, course details, headers, or the response body.

- HTTP 200 and envelope `code: 200`: token is valid.
- HTTP 401 or envelope `code: 401`: token is expired or revoked. Capture a new token.
- Network failure: report a network failure. Do not classify the token as expired.

## Record TTL

Treat the login response `expireTime` as authoritative. The observed format is Unix time in milliseconds, but tolerate a numeric string or Unix seconds.

One real response expired about 30 days after capture: 2,592,002 seconds. Treat this as observed behavior, not a permanent guarantee. The token resembles a JWT, but its payload can omit `exp`, `iat`, and `nbf`. No refresh token has been observed.

## Clean up interception

After capture:

1. Disable SSL Proxying.
2. Disable the system proxy if Proxyman left it enabled.
3. Quit Proxyman when it is not needed.
4. Remove the Proxyman CA if the user does not need future interception.

Never call booking, inventory, settlement, cancellation, or payment endpoints while rotating a token.
