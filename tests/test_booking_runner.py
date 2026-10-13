import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

PROJECT = Path(__file__).resolve().parents[1]

class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        cfg = json.loads((PROJECT / 'examples/runner-config.json').read_text())
        cfg['runtime_dir'] = str(root)
        p = root / 'config.json'; p.write_text(json.dumps(cfg))
        cls.previous = os.environ.get('SAVAGE_RUNNER_CONFIG')
        os.environ['SAVAGE_RUNNER_CONFIG'] = str(p)
        sys.path.insert(0, str(PROJECT / 'scripts'))
        import booking_runner
        cls.runner = booking_runner

    @classmethod
    def tearDownClass(cls):
        if cls.previous is None:
            os.environ.pop('SAVAGE_RUNNER_CONFIG', None)
        else:
            os.environ['SAVAGE_RUNNER_CONFIG'] = cls.previous
        cls.temp.cleanup()

    def settlement(self):
        return {'settlementId': 'fixture', 'settlementVersion': 1,
                'item': {'scheduleId': 12345678, 'quantity': 1, 'variantCode': 'v', 'tempItemId': 't'},
                'assetAllocations': [{'deductionType': 'MEMBERSHIP_CARD'}],
                'priceSummary': {'cashPay': '0.00', 'payableAmount': '0.00'}}

    def test_normal(self):
        body, queue = self.runner.payload(self.settlement(), 12345678, 'NORMAL')
        self.assertFalse(queue); self.assertEqual(body['waitDeadlineOption'], '')

    def test_queue_default(self):
        s = self.settlement()
        s['item']['waitQueueInfo'] = {'isQueue': 1, 'deadlineOptions': [
            {'value': 'CLASS_START', 'selected': True}, {'value': 'BEFORE_1H', 'selected': False}]}
        body, queue = self.runner.payload(s, 12345678, 'FULL')
        self.assertTrue(queue); self.assertEqual(body['waitDeadlineOption'], 'CLASS_START')

    def test_cash_and_missing_cash_rejected(self):
        for amount in ('109', None):
            s = self.settlement()
            if amount is None: del s['priceSummary']['cashPay']
            else: s['priceSummary']['cashPay'] = amount
            with self.assertRaises(self.runner.Stop): self.runner.payload(s, 12345678, 'NORMAL')

    def test_wrong_class_and_unknown_queue_rejected(self):
        with self.assertRaises(self.runner.Stop): self.runner.payload(self.settlement(), 99, 'NORMAL')
        with self.assertRaises(self.runner.Stop): self.runner.payload(self.settlement(), 12345678, 'FULL')

    def test_check_only_never_writes(self):
        s = self.settlement()
        course = {'id': 12345678, 'classId': 172, 'name': 'test', 'start': 'a', 'end': 'b', 'room': 'room'}
        calls = []
        def post(path, data):
            calls.append(path)
            if path.endswith('/detail'): return {'scheduleId': 12345678, 'classId': 172,
                'scheduleName': 'test', 'startTime': 'a', 'endTime': 'b', 'roomName': 'room', 'canBook': True}
            if path.endswith('batch-query'): return {'items': [{'bizItemId': 12345678, 'status': 'NORMAL'}]}
            return s
        self.runner.book(SimpleNamespace(post=post), course, {}, check_only=True)
        self.assertNotIn('/order/place', calls); self.assertNotIn('/payment/prepay', calls)

    def test_monitor_triggers_once(self):
        import watch_and_book as w
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'work').mkdir()
            outputs = [SimpleNamespace(stdout=json.dumps({'all_open': False}), returncode=0),
                       SimpleNamespace(stdout=json.dumps({'all_open': True}), returncode=0),
                       SimpleNamespace(stdout='fixture completed', returncode=0)]
            with patch.object(w, 'ROOT', root), patch.object(w, 'STATUS', root / 'status.json'), \
                 patch.object(w, 'START', dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)), \
                 patch.object(w.subprocess, 'run', side_effect=outputs) as run, patch.object(w.time, 'sleep'):
                w.main()
                self.assertEqual(run.call_count, 3)
                self.assertEqual(sum('--execute' in c.args[0] for c in run.call_args_list), 1)
                self.assertEqual(json.loads((root / 'status.json').read_text())['phase'], 'finished')

if __name__ == '__main__':
    unittest.main()
