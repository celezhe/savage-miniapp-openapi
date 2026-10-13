import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import pytest
from unittest.mock import patch
from types import SimpleNamespace

PROJECT = Path(__file__).resolve().parents[1]

class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        cfg = json.loads((PROJECT / 'examples/runner-config.json').read_text(encoding='utf-8'))
        cfg['runtime_dir'] = str(root)
        p = root / 'config.json'; p.write_text(json.dumps(cfg), encoding='utf-8')
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

    def test_windows_curl_discovery(self):
        import runtime_platform as platform
        with patch.object(platform.sys, 'platform', 'win32'), patch.object(platform.shutil, 'which', return_value='C:/Windows/System32/curl.exe') as which:
            self.assertEqual(platform.curl_executable(), 'C:/Windows/System32/curl.exe')
            which.assert_called_once_with('curl.exe')

    def test_missing_curl_stops(self):
        import runtime_platform as platform
        with patch.object(platform.sys, 'platform', 'win32'), patch.object(platform.shutil, 'which', return_value=None):
            with self.assertRaises(RuntimeError): platform.curl_executable()

    def test_windows_lock_uses_byte_zero(self):
        import runtime_platform as platform
        msvcrt = SimpleNamespace(LK_NBLCK=99, locking=lambda *a: captured.append(a))
        captured = []
        with tempfile.TemporaryFile(mode='w+') as file, patch.object(platform.os, 'name', 'nt'), patch.dict(sys.modules, {'msvcrt': msvcrt}):
            platform.fcntl.flock(file, 3)
            self.assertEqual(captured[0], (file.fileno(), 99, 1))
            self.assertEqual(file.tell(), 0)

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
                 patch.object(w, 'START', dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=1)), \
                 patch.object(w.subprocess, 'run', side_effect=outputs) as run, patch.object(w.time, 'sleep'):
                w.main()
                self.assertEqual(run.call_count, 3)
                self.assertEqual(sum('--execute' in c.args[0] for c in run.call_args_list), 1)
                self.assertEqual(json.loads((root / 'status.json').read_text(encoding='utf-8'))['phase'], 'finished')

if __name__ == '__main__':
    unittest.main()

def test_actual_curl_transport_with_local_fixture(api_server, tmp_path):
    # Real curl executable, local HTTP server, synthetic credentials. No SAVAGE requests.
    import booking_runner
    path = tmp_path / 'token.env'
    path.write_text('SAVAGE_TOKEN=synthetic-test-token\n', encoding='utf-8')
    if os.name != 'nt': path.chmod(0o600)
    api = booking_runner.API(path, base_url=api_server['url'])
    api_server['responses']['/fixture'] = {'code': 200, 'data': {'name': '中文', 'ok': True}}
    assert api.post('/fixture', {'name': '中文'}) == {'name': '中文', 'ok': True}
    assert api_server['requests'][0][2] == 'Bearer synthetic-test-token'
    api_server['responses']['/fixture'] = {'code': 401, 'msg': 'synthetic-test-token', 'data': None}
    with pytest.raises(booking_runner.Stop) as exc:
        api.post('/fixture', {})
    assert '401' in str(exc.value) and 'synthetic-test-token' not in str(exc.value)
