# SAVAGE 微信小程序 OpenAPI

这是一个非官方项目，提供 SAVAGE 微信小程序的 OpenAPI 3.1 文档、Codex Skill 和安全 API 客户端。

项目支持：

- 获取并安全保存 Bearer Token
- 根据 Bearer Token 查询当前账号资料
- 查询团课和 `scheduleId`
- 查询课程库存
- 创建结算预览
- 创建一笔待支付订单

项目不会调用支付接口。请只操作你本人拥有或控制的账号。

## 安装 Skill

```bash
git clone https://github.com/celezhe/savage-miniapp-openapi.git
cp -R savage-miniapp-openapi ~/.codex/skills/savage-miniapp-openapi
```

## 获取 Token

1. 在 Proxyman 中安装并信任 CA 证书。
2. 只为 `wechat-api.savagepark.com.cn` 开启 SSL Proxying。
3. 在官方 SAVAGE 微信小程序中正常登录或刷新页面。
4. 找到 SAVAGE API 请求，从 `Authorization: Bearer ...` 请求头复制 Token。
5. 只保存 `Bearer ` 后面的值，并设置文件权限：

```bash
chmod 600 /绝对路径/token
export SAVAGE_TOKEN_FILE=/绝对路径/token
```

不要把 Token 粘贴到聊天、日志、Shell 历史或 Git 中。抓取完成后，关闭系统代理和 SSL Proxying，并按需移除 Proxyman CA。

## Proxyman 网络排障

如果小程序显示“加载失败请重试”，先检查 macOS 系统代理：

```bash
scutil --proxy
```

如果输出包含 `HTTPEnable : 1`、`HTTPSEnable : 1` 和 `127.0.0.1:9090`，系统流量仍经过 Proxyman。

1. 在 Proxyman 中停止 Capture。
2. 关闭 **Certificate > SSL Proxying List** 中的 SAVAGE 规则。
3. 关闭 Proxyman 的系统代理覆盖。
4. 返回微信，然后刷新小程序。

如果 API 可以直接返回 `200`，但小程序仍加载失败，问题通常在本地代理链路，不在 SAVAGE 后端。

## Token 有效期

- Token 是三段式 JWT，但 payload 只有 `loginId`、`loginType` 和 `rnStr`。
- JWT 没有 `exp`、`iat` 或 `nbf`，不能直接从 Token 计算有效期。
- `/auth/wechat/login` 响应单独返回绝对时间戳 `expireTime`。
- 小程序同时兼容秒级和毫秒级时间戳，并以 `expireTime > 当前时间` 判断登录状态。
- 没有发现 refresh token。接口返回 `401` 后，必须重新执行 `wx.login()` 并换取新 Token。

2026-10-08 的一次真实登录响应返回了毫秒级 `expireTime`。该时间比登录响应时间晚约 30 天。实测差值为 2,592,002 秒，即 30 天加约 2 秒。

因此，当前观察到的 Token TTL 是约 30 天。这是接口响应中的直接证据，不是根据框架默认值推断的结论。后端仍可修改 TTL，所以客户端必须以每次登录响应中的 `expireTime` 为准。

该 Token 的结构与 Sa-Token JWT 相符。JWT payload 本身不包含过期时间。不要仅解析 JWT 来判断 Token 是否有效。

## 命令行用法

```bash
python3 scripts/savage_api.py profile
python3 scripts/savage_api.py display-profile
python3 scripts/savage_api.py classes query.json
python3 scripts/savage_api.py inventory 12345678
python3 scripts/savage_api.py orders --scene TO_PAY
python3 scripts/savage_api.py settle 12345678
python3 scripts/savage_api.py book-unpaid 12345678
```

`profile` 调用 `POST /user-base/get-user-base-info`。响应包含账号状态和持卡状态。

`display-profile` 调用 `POST /user/profile/detail`。响应包含昵称、头像和脱敏资料等展示字段。

两个接口的路径和字段均不同。它们不是按账号类型互斥的接口。使用同一个年卡 Token 调用两者时，两个接口都返回 `200`。

不要公开任何账号资料响应。

2026-10-08 使用年卡账号测试时，接口返回 `membershipCardHolder: true` 和 `sessionCardHolder: false`。这证明该接口可以识别会员卡持有人。

同次启动流量还观察到以下接口：

- `POST /user-base/check-user-hook`
- `POST /message/subscribe/quota/query`
- `POST /user/agreement/status`
- `POST /operation/position/query`
- `POST /trainingCamp/cohort/recommendation`

这些接口已经加入 OpenAPI。未确认的响应字段继续使用开放结构，避免根据名称猜测业务含义。

`book-unpaid` 会检查库存和待支付订单，展示结算信息，并要求输入准确的确认文本。每次确认最多发送一次 `order/place`。出现不确定响应时，必须先查询待支付订单，不能直接重试。

## 文件说明

- `openapi.yaml`：已观察到的 API 合约。
- `SKILL.md`：获取 Token 和创建待支付订单的工作流。
- `scripts/savage_api.py`：带安全保护的 API 客户端。

接口来自实际流量观察，可能随小程序更新而变化。仓库不包含真实 Token、用户信息或订单号。
