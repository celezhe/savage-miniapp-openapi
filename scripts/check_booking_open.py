#!/usr/bin/env python3
"""Read-only booking availability check using hrz; no placement or payment."""
import datetime as dt
from runtime_platform import fcntl
import json
import os
from pathlib import Path
from booking_runner import API, ROOT, CLASSES, Stop, CONFIG

def main():
    ROOT.joinpath('work').mkdir(parents=True, exist_ok=True)
    with open(ROOT / 'work/check-booking-open.lock', 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        api = API(Path(os.environ.get('SAVAGE_SLAVE_ENV_FILE', CONFIG['slave_env_file'])).expanduser())
        if str(api.post('/user/profile/detail', {}).get('userId')) != str(CONFIG['slave_account_id']):
            raise Stop('hrz 账号不匹配，停止检查')
        results = []
        for course in CLASSES:
            try:
                detail = api.post('/groupClass/schedule/detail', {'scheduleId': course['id']})
                if (str(detail.get('scheduleId')) != str(course['id']) or
                    detail.get('displayStatus') == 'PREVIEW' or detail.get('canBook') is not True):
                    results.append({'scheduleId': course['id'], 'open': False,
                                    'result': '排课尚未开放', 'displayStatus': detail.get('displayStatus')})
                    continue
                settlement = api.post('/order/settle/groupClass', {
                    'firstSettle': True, 'quantity': 1, 'scheduleId': course['id']})
                item = settlement.get('item', {})
                opened = str(item.get('scheduleId')) == str(course['id']) and bool(settlement.get('settlementId'))
                results.append({'scheduleId': course['id'], 'open': opened,
                                'result': '已开放结算' if opened else '返回字段不匹配，需核对'})
            except Stop as exc:
                results.append({'scheduleId': course['id'], 'open': False, 'result': str(exc)})
        print(json.dumps({'checked_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                          'all_open': all(r['open'] for r in results), 'classes': results}, ensure_ascii=False))

if __name__ == '__main__':
    try:
        main()
    except Stop as exc:
        print(json.dumps({'stop': str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
