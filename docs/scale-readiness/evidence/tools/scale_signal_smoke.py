"""Owned Linux-only, no-database signal plumbing smoke. No active-turn claims."""
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

child_code = '''
import uvicorn
from contextlib import asynccontextmanager
from app.core.config import Settings
from app.main import create_app
from tests.settings_baseline import ALL_FEATURES_OFF
settings = Settings(_env_file=None, **ALL_FEATURES_OFF, database_url='',
    database_migration_url='', openai_api_key='', supabase_url='',
    supabase_publishable_key='', voyage_api_key='', apify_api_token='')
app = create_app(settings)
original = app.router.lifespan_context
@asynccontextmanager
async def tracked(app):
    async with original(app):
        yield
    print('LOCAL_LIFESPAN_CLOSED', flush=True)
app.router.lifespan_context = tracked
uvicorn.run(app, host='127.0.0.1', port=18081,
    timeout_graceful_shutdown=10, log_level='warning')
'''

def status(path, method='GET'):
    request = urllib.request.Request('http://127.0.0.1:18081' + path, method=method)
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code

with open('/tmp/signal-child.log', 'w') as log:
    child = subprocess.Popen([sys.executable, '-c', child_code], stdout=log, stderr=log)
    try:
        until = time.monotonic() + 20
        while True:
            try:
                initial = status('/api/v1/ai/conversations/00000000-0000-0000-0000-000000000000/messages', 'POST')
                break
            except (urllib.error.URLError, ConnectionError):
                if time.monotonic() > until or child.poll() is not None:
                    raise RuntimeError('Local signal fixture failed to start') from None
                time.sleep(0.1)
        assert initial == 401, initial
        os.kill(child.pid, signal.SIGUSR1)
        until = time.monotonic() + 5
        while status('/api/v1/ai/conversations/00000000-0000-0000-0000-000000000000/messages', 'POST') != 503:
            assert time.monotonic() < until
            time.sleep(0.05)
        live = status('/api/v1/health/live')
        ready = status('/api/v1/health/ready')
        cancel = status('/api/v1/ai/runs/00000000-0000-0000-0000-000000000000/cancel', 'POST')
        assert live == 200 and ready == 503 and cancel == 401, (live, ready, cancel)
        started = time.monotonic()
        child.send_signal(signal.SIGTERM)
        code = child.wait(timeout=15)
        log.flush()
        assert code in (0, -signal.SIGTERM), code
        with open('/tmp/signal-child.log') as recorded:
            assert 'LOCAL_LIFESPAN_CLOSED' in recorded.read()
        print(json.dumps({'scope': 'Linux real Uvicorn HTTP + SIGUSR1/SIGTERM; no DB/provider/active turns',
            'status': 'LOCAL_SYNTHETIC_PASS', 'initial_new_turn': initial, 'draining_new_turn': 503,
            'liveness': live, 'readiness': ready, 'cancel_requires_auth': cancel,
            'shutdown_seconds': round(time.monotonic() - started, 3), 'exit_code': code,
            'lifespan_cleanup_completed': True,
            'active_turn_drain_worker_fence_rollback': 'NOT_VALIDATED'}))
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
