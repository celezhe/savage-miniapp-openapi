"""Cross-platform skill tests: synthetic tokens only, no real SAVAGE calls."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import pytest

ROOT = Path(__file__).resolve().parents[1]
TOKEN_SCRIPTS = ROOT / 'skills/get-savage-token/scripts'

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def token_modules():
    logs = []
    shutdown = []
    ctx = SimpleNamespace(log=SimpleNamespace(info=logs.append, error=logs.append),
                          master=SimpleNamespace(shutdown=lambda: shutdown.append(True)))
    fake = SimpleNamespace(ctx=ctx, http=SimpleNamespace(HTTPFlow=object))
    save = load('save_login_response', TOKEN_SCRIPTS / 'save_login_response.py')
    with patch.dict(sys.modules, {'mitmproxy': fake, 'save_login_response': save}):
        capture = load('capture_fixture', TOKEN_SCRIPTS / 'capture_token.py')
        observer = load('observe_fixture', TOKEN_SCRIPTS / 'observe_endpoints.py')
        yield save, capture, observer, logs, shutdown

def flow(host='wechat-api.savagepark.com.cn', code=200):
    return SimpleNamespace(request=SimpleNamespace(pretty_host=host, method='POST',
        path='/backend-api/auth/wechat/login?private=value', headers={'Authorization': 'Bearer synthetic-request-secret'},
        json=lambda: {'code': 'private-request-value'}),
        response=SimpleNamespace(status_code=200, json=lambda: {'code': code,
            'data': {'token': 'synthetic-response-secret', 'expireTime': 2000000000000}}))

def test_token_save_preserves_other_entries_and_bom(token_modules, tmp_path):
    save, *_ = token_modules
    path = tmp_path / 'private.env'
    path.write_text('\ufeffNOTE=中文\nSAVAGE_TOKEN=old\nSAVAGE_TOKEN=duplicate\n', encoding='utf-8')
    save.update_env(path, 'synthetic-secret')
    assert path.read_text(encoding='utf-8') == 'NOTE=中文\nSAVAGE_TOKEN=synthetic-secret\n'
    if os.name != 'nt': assert path.stat().st_mode & 0o777 == 0o600

def test_expiration_seconds_milliseconds_and_invalid(token_modules):
    save, *_ = token_modules
    assert save.parse_expiration('2000000000') == save.parse_expiration(2000000000000)
    with pytest.raises(ValueError): save.parse_expiration('invalid')

def test_capture_rejects_unrelated_host_and_failed_login(token_modules, tmp_path):
    _, capture, _, logs, shutdown = token_modules
    path = tmp_path / 'token.env'
    with patch.dict(os.environ, SAVAGE_ENV_FILE=str(path)):
        addon = capture.CaptureSavageToken()
        addon.response(flow(host='unrelated.example'))
        addon.response(flow(code=401))
    assert not path.exists() and not shutdown and not logs

def test_capture_saves_once_without_secret_logging(token_modules, tmp_path):
    _, capture, _, logs, shutdown = token_modules
    path = tmp_path / 'token.env'
    with patch.dict(os.environ, SAVAGE_ENV_FILE=str(path)):
        addon = capture.CaptureSavageToken()
        addon.response(flow()); addon.response(flow())
    assert 'synthetic-response-secret' in path.read_text(encoding='utf-8')
    assert len(shutdown) == 1
    assert all('synthetic' not in message for message in logs)

def test_observer_logs_shapes_not_values(token_modules, tmp_path):
    _, _, observer, _, _ = token_modules
    path = tmp_path / 'endpoints.jsonl'
    with patch.dict(os.environ, SAVAGE_ENDPOINT_LOG=str(path)):
        observer.ObserveSavageEndpoints().response(flow())
    raw = path.read_text(encoding='utf-8'); record = json.loads(raw)
    assert record['path'] == '/backend-api/auth/wechat/login'
    assert record['requestKeys'] == ['code']
    assert 'secret' not in raw and 'private-request-value' not in raw and 'private=value' not in raw

def test_every_skill_script_compiles():
    for path in (ROOT / 'skills').rglob('*.py'):
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')

@pytest.mark.parametrize('source', ['scripts', 'skills/savage-master-slave-booking/scripts'])
def test_runner_offline_and_lock_contention_in_real_processes(source, tmp_path):
    script_dir = ROOT / source
    cfg = json.loads((ROOT / 'examples/runner-config.json').read_text(encoding='utf-8'))
    cfg['runtime_dir'] = str(tmp_path / '运行目录')
    config = tmp_path / '配置.json'
    config.write_text(json.dumps(cfg, ensure_ascii=False), encoding='utf-8-sig')
    env = {**os.environ, 'SAVAGE_RUNNER_CONFIG': str(config), 'PYTHONIOENCODING': 'utf-8'}
    result = subprocess.run([sys.executable, str(script_dir / 'booking_runner.py')],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=10)
    assert result.returncode == 0, result.stderr
    assert 'Offline mode' in result.stdout
    lock = tmp_path / 'lock'
    helper = '''import sys
from runtime_platform import fcntl
with open(sys.argv[1], 'a+') as f:
 fcntl.flock(f, 3)
 print('locked', flush=True)
 sys.stdin.readline()
'''
    lock_env = {**env, 'PYTHONPATH': str(script_dir)}
    first = subprocess.Popen([sys.executable, '-c', helper, str(lock)], env=lock_env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert first.stdout.readline().strip() == 'locked'
        second = subprocess.run([sys.executable, '-c', helper, str(lock)], env=lock_env,
                                input='\n', capture_output=True, text=True, timeout=10)
        assert second.returncode != 0
    finally:
        first.communicate('\n', timeout=10)
    third = subprocess.run([sys.executable, '-c', helper, str(lock)], env=lock_env,
                           input='\n', capture_output=True, text=True, timeout=10)
    assert third.returncode == 0, third.stderr
