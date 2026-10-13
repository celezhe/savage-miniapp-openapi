#!/usr/bin/env python3
"""One-shot, zero-cash SAVAGE booking. No credentials in this source."""
import argparse
import datetime as dt
from decimal import Decimal
from runtime_platform import fcntl, curl_executable
import json
import os
from pathlib import Path
import subprocess
import time

CONFIG_PATH = Path(os.environ.get('SAVAGE_RUNNER_CONFIG', '')).expanduser()
if not CONFIG_PATH.is_file():
    raise SystemExit('Set SAVAGE_RUNNER_CONFIG to a private configuration file')
CONFIG = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
ROOT = Path(CONFIG['runtime_dir']).expanduser()
ENV = Path(os.environ.get('SAVAGE_MASTER_ENV_FILE', CONFIG['master_env_file'])).expanduser()
STATE = ROOT / 'work/booking-state.json'
START = dt.datetime.fromisoformat(CONFIG['start_utc'].replace('Z', '+00:00'))
CLASSES = CONFIG['classes']
EXPECTED_ACCOUNT = str(CONFIG['master_account_id'])

class Stop(Exception):
    pass

def objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from objects(child)

def has_class(data, sid):
    return any(str(o.get('scheduleId', o.get('bizItemId', ''))) == str(sid) for o in objects(data))

def payload(settlement, sid, inventory):
    for key in ('settlementId', 'settlementVersion', 'item', 'assetAllocations', 'priceSummary'):
        if key not in settlement:
            raise Stop('结算缺少必要字段：' + key)
    item = settlement['item']
    if str(item.get('scheduleId')) != str(sid) or item.get('quantity') != 1:
        raise Stop('结算场次或数量不匹配')
    prices = settlement['priceSummary']
    for key in ('payableAmount', 'cashPay'):
        if key not in prices or Decimal(str(prices[key])) != 0:
            raise Stop('需要现金支付或零元金额无法确认')
    allocations = settlement['assetAllocations']
    if not isinstance(allocations, list) or not allocations:
        raise Stop('缺少会员资产抵扣')
    if not any('MEMBER' in str(a.get('deductionType', '')).upper() for a in allocations):
        raise Stop('资产抵扣不是已确认的会员方案')
    for allocation in allocations:
        if allocation.get('deductionType') == 'CASH' and Decimal(str(allocation.get('amount', 'NaN'))) != 0:
            raise Stop('资产分配包含现金支付')
    queue = item.get('waitQueueInfo') or {}
    is_queue = queue.get('isQueue') in (1, True, '1')
    deadline = ''
    if inventory == 'FULL' or is_queue:
        if not is_queue:
            raise Stop('满员但结算未确认支持候补')
        choices = [o for o in queue.get('deadlineOptions', []) if o.get('selected') is True]
        if len(choices) != 1 or not isinstance(choices[0].get('value'), str) or not choices[0]['value']:
            raise Stop('候补截止选项无法唯一确认')
        deadline = choices[0]['value']
    for key in ('variantCode', 'tempItemId'):
        if not item.get(key):
            raise Stop('结算课程字段缺失：' + key)
    return {
        'assetAllocations': allocations,
        'settlementId': settlement['settlementId'],
        'settlementVersion': settlement['settlementVersion'],
        'waitDeadlineOption': deadline,
        'items': [{'bizItemId': sid, 'quantity': 1, 'productType': 'GROUP_CLASS',
                   'itemSceneCode': 'GROUP_CLASS', 'variantCode': item['variantCode'], 'tempItemId': item['tempItemId']}],
    }, is_queue

class API:
    def __init__(self, env=ENV):
        if os.name != 'nt' and env.stat().st_mode & 0o077:
            raise Stop('凭证权限必须为 600')
        self.token = next(line.split('=', 1)[1].strip().strip('\"\'') for line in env.read_text(encoding='utf-8').splitlines() if line.startswith('SAVAGE_TOKEN='))

    def post(self, path, body):
        # Credentials enter curl via stdin only; TLS verification stays enabled.
        config = '\n'.join([
            'url = ' + json.dumps('https://wechat-api.savagepark.com.cn/backend-api' + path),
            'request = "POST"', 'header = "Content-Type: application/json"',
            'header = ' + json.dumps('Authorization: Bearer ' + self.token),
            'data = ' + json.dumps(json.dumps(body)), ''])
        try:
            r = subprocess.run([curl_executable(), '--config', '-', '--silent', '--noproxy', '*',
                                '--max-time', '15', '--write-out', '\n%{http_code}'],
                               input=config, text=True, encoding='utf-8', capture_output=True, timeout=20)
            if r.returncode:
                raise Stop('网络错误，未自动重试请求')
            raw, http = r.stdout.rsplit('\n', 1)
            envelope = json.loads(raw)
            if http != '200' or envelope.get('code') != 200:
                # Only known business reasons are emitted, never raw response data.
                code = envelope.get('code')
                reason = {401: '登录已失效', 412: '预约条件未满足', 429: '请求受限', 411: '业务限制'}.get(code, '接口拒绝请求')
                raise Stop(f'{reason}（HTTP {http}，code {code}）')
            return envelope.get('data')
        except (ValueError, subprocess.TimeoutExpired):
            raise Stop('响应或网络异常，未自动重试请求') from None

def save(state):
    tmp = STATE.with_suffix('.new')
    with open(tmp, 'w', encoding='utf-8') as f:
        os.chmod(tmp, 0o600)
        json.dump(state, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE)

def orders(api, scene):
    data = api.post('/order/list', {'lastOrderId': '', 'scene': scene})
    if not isinstance(data, dict):
        raise Stop('订单列表结构无法确认')
    result = data.get('orders', data.get('list'))
    if not isinstance(result, list):
        raise Stop('订单列表缺少可检查的数组')
    return result

def reconcile(api, sid):
    completed = orders(api, 'COMPLETED')
    if any(has_class(o, sid) for o in completed):
        return '订单已出现在 COMPLETED；候补或名额需按订单状态区分'
    unpaid = orders(api, 'TO_PAY')
    if any(has_class(o, sid) for o in unpaid):
        return '存在待支付订单，需人工核对，禁止重复下单'
    all_orders = orders(api, 'ALL')
    if any(has_class(o, sid) for o in all_orders):
        return '已有相关订单，需人工核对，禁止重复下单'
    return None

def book(api, course, state, check_only=False):
    sid = course['id']
    key = str(sid)
    previous = None if check_only else reconcile(api, sid)
    if previous:
        return previous
    if key in state:
        return '本场已尝试提交，禁止再次下单；暂未确认订单'
    detail = api.post('/groupClass/schedule/detail', {'scheduleId': sid})
    if not isinstance(detail, dict) or not all([
        str(detail.get('scheduleId')) == str(sid), detail.get('classId') == course['classId'],
        detail.get('scheduleName') == course['name'],
        detail.get('startTime') == course['start'], detail.get('endTime') == course['end'],
        str(detail.get('roomName', '')).strip() == course['room'], detail.get('canBook') is True]):
        raise Stop('课程详情不匹配或不允许预约')
    stock = api.post('/inventory/status/batch-query', {'items': [{'bizItemId': sid, 'productType': 'GROUP_CLASS'}]})
    stock_rows = stock.get('items', []) if isinstance(stock, dict) else stock
    matching = [i for i in stock_rows if str(i.get('bizItemId')) == str(sid)]
    if len(matching) != 1 or matching[0].get('status') not in ('NORMAL', 'FULL'):
        raise Stop('库存状态不允许预约或无法确认')
    settlement = api.post('/order/settle/groupClass', {'firstSettle': True, 'quantity': 1, 'scheduleId': sid})
    body, queue = payload(settlement, sid, matching[0]['status'])
    if check_only:
        return '检查通过：候补参数已构造，未下单' if queue else '检查通过：预约参数已构造，未下单'
    # Write durable submission intent before the write request; a crash cannot duplicate it.
    state[key] = {'phase': 'placement_attempted', 'queue': queue}
    save(state)
    try:
        placed = api.post('/order/place', body)
    except Stop:
        return reconcile(api, sid) or '提交结果不确定；未重复下单，需人工核对'
    order_id = placed.get('orderId') if isinstance(placed, dict) else None
    if not order_id:
        return '提交返回缺少订单标识；未重试，需核对'
    state[key].update(orderId=order_id, phase='placed')
    save(state)
    prepaid = api.post('/payment/prepay', {'orderId': order_id})
    if not isinstance(prepaid, dict) or prepaid.get('prePayItems') != []:
        raise Stop('零元支付准备未确认；已创建订单，停止并需核对')
    api.post('/order/query/status', {'orderId': order_id, 'times': 1})
    api.post('/order/paySuccess', {'orderId': order_id})
    for attempt in range(3):
        completed = orders(api, 'COMPLETED')
        # This API's list can omit scheduleId. The exact returned orderId is authoritative.
        matching_orders = [o for root in completed for o in objects(root) if str(o.get('orderId')) == str(order_id)]
        if matching_orders:
            order_detail = api.post('/order/detail', {'orderId': order_id})
            queue_confirmed = any(o.get('isQueue') in (1, True, '1') or
                                  str(o.get('status', '')).upper() in ('WAITING', 'QUEUING', 'QUEUE', 'WAIT_QUEUE')
                                  for o in objects(order_detail))
            if queue and not queue_confirmed:
                return '零元订单已完成，候补模式已提交；最终候补状态需人工确认'
            result = '候补成功（不代表已取得名额）' if queue_confirmed else '预约成功'
            state[key]['phase'] = 'confirmed'
            save(state)
            return result
        if attempt < 2:
            time.sleep(1)
    return '已提交零元订单，但未出现在 COMPLETED，需核对'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--when-open', action='store_true', help='Authorized event-triggered execution')
    args = parser.parse_args()
    if not args.execute:
        print('Offline mode: no requests. Configuration loaded; explicit --execute required.')
        return
    now = dt.datetime.now(dt.timezone.utc)
    if args.when_open and not args.execute:
        raise Stop('--when-open 必须与 --execute 一起使用')
    if args.when_open:
        if now > START + dt.timedelta(minutes=10):
            raise Stop('监控已超过截止时间，未发请求')
    elif not START <= now <= START + dt.timedelta(seconds=60):
        raise Stop('不在授权执行窗口，未发请求')
    ROOT.joinpath('work').mkdir(parents=True, exist_ok=True)
    with open(ROOT / 'work/booking.lock', 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Exclusive durable creation permits only one execution, including failed runs.
        run_marker = ROOT / 'work/booking-run-once.json'
        try:
            fd = os.open(run_marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise Stop('鱼儿定时任务已运行过，禁止再次执行') from None
        with os.fdopen(fd, 'w', encoding='utf-8') as marker:
            json.dump({'started_utc': now.isoformat()}, marker)
            marker.flush()
            os.fsync(marker.fileno())
        api = API()
        if str(api.post('/user/profile/detail', {}).get('userId')) != EXPECTED_ACCOUNT:
            raise Stop('账号不匹配')
        if api.post('/user-base/get-user-base-info', {}).get('membershipCardHolder') is not True:
            raise Stop('账号会员身份未确认')
        state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
        for course in CLASSES:
            try:
                result = book(api, course, state)
            except Stop as exc:
                result = str(exc)
            except Exception:
                result = '未预期的结构或运行异常；停止本场，需核对'
            print(json.dumps({'course': course['room'], 'start': course['start'], 'result': result}, ensure_ascii=False))

if __name__ == '__main__':
    try:
        main()
    except Stop as exc:
        print(str(exc))
        raise SystemExit(1)
