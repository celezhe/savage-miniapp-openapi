#!/usr/bin/env python3
"""Poll hrz every 30 seconds during the two-minute pre-release window; trigger exactly one yuer booking run when both open."""
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from booking_runner import ROOT, START

STATUS = ROOT / 'work/watch-and-book-status.json'

def record(value):
    value['updated_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    tmp = STATUS.with_suffix('.new')
    with open(tmp, 'w') as f:
        os.chmod(tmp, 0o600)
        json.dump(value, f, ensure_ascii=False)
    os.replace(tmp, STATUS)

def main():
    ROOT.joinpath('work').mkdir(parents=True, exist_ok=True)
    with open(ROOT / 'work/watch-and-book.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (ROOT / 'work/booking-run-once.json').exists():
            record({'phase': 'stopped', 'reason': '鱼儿预约脚本已运行过，禁止重跑'})
            return
        begin = START - dt.timedelta(minutes=2)
        deadline = START + dt.timedelta(minutes=10)
        while dt.datetime.now(dt.timezone.utc) < begin:
            record({'phase': 'waiting', 'begin_utc': begin.isoformat(),
                    'release_utc': START.isoformat(), 'interval_seconds': 30})
            time.sleep(min(30, max(0, (begin - dt.datetime.now(dt.timezone.utc)).total_seconds())))
        while dt.datetime.now(dt.timezone.utc) <= deadline:
            tick = time.monotonic()
            try:
                check = subprocess.run([sys.executable, str(Path(__file__).with_name('check_booking_open.py'))],
                                       capture_output=True, text=True, timeout=60)
                report = json.loads(check.stdout)
            except (subprocess.TimeoutExpired, ValueError):
                record({'phase': 'monitoring', 'reason': '网络或检查输出异常，等待下一轮'})
                time.sleep(max(0, 30 - (time.monotonic() - tick)))
                continue
            if report.get('stop') or any(any(code in c.get('result', '') for code in ('401', '411', '429')) for c in report.get('classes', [])):
                record({'phase': 'stopped', 'reason': report.get('stop', '监控账号登录失效或服务端限流/业务限制')})
                return
            if report.get('all_open') is True:
                record({'phase': 'booking', 'check': report})
                # No retries, even after timeout or a failed booking run.
                try:
                    result = subprocess.run([sys.executable, str(Path(__file__).with_name('booking_runner.py')),
                                             '--execute', '--when-open'], capture_output=True, text=True, timeout=240)
                    record({'phase': 'finished', 'exit_code': result.returncode, 'result': result.stdout.strip()})
                except subprocess.TimeoutExpired:
                    record({'phase': 'stopped', 'reason': '预约脚本超时，禁止重跑，需核对订单'})
                return
            record({'phase': 'monitoring', 'check': report})
            time.sleep(max(0, 30 - (time.monotonic() - tick)))
        record({'phase': 'stopped', 'reason': '监控达到开始时间后10分钟的截止点，停止'})

if __name__ == '__main__':
    main()
