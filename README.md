# SAVAGE 微信小程序 OpenAPI

这是一个非官方项目，提供 SAVAGE 微信小程序的 OpenAPI 3.1 文档、Codex Skill 和安全 API 客户端。

项目支持：

- 获取并安全保存 Bearer Token
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

## Token 有效期

- Token 是三段式 JWT，但 payload 只有 `loginId`、`loginType` 和 `rnStr`。
- JWT 没有 `exp`、`iat` 或 `nbf`，不能直接从 Token 计算有效期。
- `/auth/wechat/login` 响应单独返回绝对时间戳 `expireTime`。
- 小程序同时兼容秒级和毫秒级时间戳，并以 `expireTime > 当前时间` 判断登录状态。
- 没有发现 refresh token。接口返回 `401` 后，必须重新执行 `wx.login()` 并换取新 Token。

该 Token 的结构与 Sa-Token JWT 相符。Sa-Token 默认超时是 30 天，但 SAVAGE 后端可以覆盖该配置。因此，必须以每次登录响应中的 `expireTime` 为准，不能仅根据框架默认值断言实际 TTL。

## 命令行用法

```bash
python3 scripts/savage_api.py classes query.json
python3 scripts/savage_api.py inventory 12345678
python3 scripts/savage_api.py orders --scene TO_PAY
python3 scripts/savage_api.py settle 12345678
python3 scripts/savage_api.py book-unpaid 12345678
```

`book-unpaid` 会检查库存和待支付订单，展示结算信息，并要求输入准确的确认文本。每次确认最多发送一次 `order/place`。出现不确定响应时，必须先查询待支付订单，不能直接重试。

## 文件说明

- `openapi.yaml`：已观察到的 API 合约。
- `SKILL.md`：获取 Token 和创建待支付订单的工作流。
- `scripts/savage_api.py`：带安全保护的 API 客户端。

接口来自实际流量观察，可能随小程序更新而变化。仓库不包含真实 Token、用户信息或订单号。
