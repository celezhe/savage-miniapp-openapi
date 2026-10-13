# 配置驱动的预约监控

此目录是 `celezhe/savage-miniapp-openapi` 的本地扩展，沿用原有 OpenAPI、客户端和 Skill，新增固定 Python 执行流程。没有修改线上仓库。

## Master / Slave

- **Slave token**：监控账号，只查询账号及结算预览，不能下单或支付。
- **Master token**：预约账号，两节全部开放后用于会员零元预约或候补。
- 所有线上测试使用 Slave；Master 只用于最终真实预约，不用于试单。Slave 待支付试单需另行明确授权，监控脚本自身不会下单。
- 配置分别使用 `slave_env_file`、`slave_account_id` 和 `master_env_file`、`master_account_id`。两个私有 env 文件内部仍统一写 `SAVAGE_TOKEN=...`。
- 可用 `SAVAGE_SLAVE_ENV_FILE`、`SAVAGE_MASTER_ENV_FILE` 环境变量覆盖凭证文件路径，不把 token 值写进配置或命令行。

## 文件

- `scripts/check_booking_open.py`：用监控账号查询配置中的所有场次是否能结算，不创建订单。
- `scripts/watch_and_book.py`：预期开放前 2 分钟开始，每 30 秒检查一次；所有场次均开放后调用预约执行器一次，然后退出。
- `scripts/booking_runner.py`：用预约账号按配置顺序处理普通预约或满员候补，仅允许会员抵扣、现金应付零元。
- `examples/runner-config.json`：配置结构示例，使用占位账号和场次。

## 用户选课流程

调用 `$savage-master-slave-booking` 后，用户提供课程截图或课程名、门店、日期和时间。Codex 用 Slave 查询排课列表、匹配唯一场次并确认详情，自动取得 scheduleId/classId，再展示选课结果并生成私有配置。用户无需找 ID 或填写 JSON。已有明确选课和授权时不重复询问；Master 只在最终预约执行时使用。

## 准备

需要 Python 3.10+、macOS/Linux 的 `fcntl` 和 `/usr/bin/curl`。TLS 验证保持开启。脚本不调用微信现金支付。

1. 在项目目录外准备两个私有 `.env` 文件，各包含一行 `SAVAGE_TOKEN=...`；权限必须为 `600`。
2. 将示例配置复制到项目外，填写监控账号、预约账号、凭证路径、运行目录、UTC 开始时间和准确场次。配置不保存 token。
3. 预约账号必须具有会员卡权益。只有结算明确返回会员抵扣，且 `cashPay`、`payableAmount` 都为零，才允许下单。
4. 运行目录必须是新的、私有目录。不要删除已使用运行目录中的提交记录后重试。

```sh
export SAVAGE_RUNNER_CONFIG=/absolute/private/runner-config.json
python3 scripts/booking_runner.py
python3 scripts/check_booking_open.py
python3 scripts/watch_and_book.py
```

第一条命令只载入配置，不发请求。第二条检查一次。第三条持续监控，并在所有场次开放时触发已授权的真实零元预约。必须先获得用户对配置中全部具体预约和满员候补的明确授权，再运行第三条命令。

## 固定分支

1. 监控 token 必须属于配置中的监控账号；`412` 继续等待。
2. 所有场次结算返回成功、对应 `scheduleId` 匹配，并有 `settlementId`，才触发预约账号。
3. 预约账号 ID、会员身份、课程名称、课程类型、教室和开始/结束时间必须匹配配置。
4. 库存 `NORMAL` 走普通预约；`FULL` 只有结算 `isQueue=1` 时才能候补。
5. 候补读取 `deadlineOptions` 中唯一 `selected=true` 的 `value`，作为 `waitDeadlineOption`。缺失或有多个默认值就停止。
6. 会员结算与零现金检查通过后，保存提交意图，再调用 `order/place`。每场最多一次，网络异常不重试下单。
7. 调用零元 `payment/prepay` 后，必须看到空 `prePayItems`；否则停止。查询状态及 `COMPLETED` 列表，以准确的返回 `orderId` 核验。
8. 候补状态无法从订单明确确认时，报告“已提交，需要核对”，不声称已经获得名额。

## 一次性执行与截止

进程锁避免并发监控。预约执行器使用 `O_EXCL` 创建整次运行标记；首次执行失败后也不能自动重新运行。每场下单意图、订单标识保存在私有运行目录中，文件权限为 `600`，不会输出到终端。

事件模式可在配置中的预期开始时间之前触发，以服务器实际开放状态为准；监控最晚运行到预期开始时间之后 10 分钟。直接执行 `booking_runner.py --execute` 只允许在预期开始时间后的 60 秒内运行。

轮询周期是 30 秒加可能的网络耗时，不保证精确到秒发现开放，也不保证抢到名额。电脑休眠、断网或进程退出会中断任务。脚本不会安装系统服务，也不会自动重启。

## 验证范围

已用真实非会员账号验证普通及候补结算和待支付下单参数。真实会员零元下单、支付准备及候补生效仍未完成端到端测试。离线测试覆盖零元保护、候补选项、错误场次和一次性触发。

```sh
python3 -m unittest discover -s tests -p 'test_booking_runner.py'
```
