"""Temporary proxy maintenance gate for an authorized controlled release.

Run on the existing EC2 host as root. The test token comes only from the runtime
SecureString and is never printed. The normal Caddyfile is retained for recovery.
This gates HTTP; operators must also fence incompatible background workers.
"""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path


def render_gate(source: str, token: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', token):
        raise ValueError('Invalid release test token')
    anchor = '{$APP_DOMAIN} {'
    if source.count(anchor) != 1 or '@releaseGate' in source:
        raise ValueError('Expected exactly one ungated application site')
    gate = '''
    # Temporary release gate; remove using release_gate.py disable.
    @releaseGate {
        not path /api/v1/health/live /api/v1/health/ready
        not header X-MoodPrint-Release-Test "TOKEN"
    }
    handle @releaseGate {
        header Retry-After "120"
        respond "MoodPrint dang duoc cap nhat. Vui long quay lai sau." 503
    }
'''.replace('TOKEN', token)
    return source.replace(anchor, anchor + '\n' + gate, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['enable', 'disable'])
    args = parser.parse_args()
    if not hasattr(os, 'geteuid') or os.geteuid() != 0:
        parser.error('Run on the existing EC2 host as root')
    base = Path('/opt/moodprint')
    target = base / 'Caddyfile'
    backup = base / 'Caddyfile.before-mvp-gate'
    if target.is_symlink() or backup.is_symlink():
        raise ValueError('Symlink targets are not supported')
    current = target.read_text()
    if args.action == 'enable':
        if backup.exists():
            raise ValueError('Existing maintenance backup preserved; inspect state first')
        raw = subprocess.check_output([
            'aws', '--region', 'ap-southeast-2', 'ssm', 'get-parameter',
            '--name', '/moodprint/staging/runtime', '--with-decryption',
        ], text=True)
        values = dict(line.split('=', 1) for line in json.loads(raw)['Parameter']['Value'].splitlines()
                      if '=' in line and not line.startswith('#'))
        candidate = render_gate(current, values.get('RELEASE_TEST_TOKEN', ''))
        with backup.open('x') as handle:
            handle.write(current)
        backup.chmod(0o600)
    else:
        if not backup.is_file() or '@releaseGate' not in current:
            raise ValueError('No matching maintenance gate/backup')
        candidate = backup.read_text()
    # Preserve the inode of the existing file bind mount into Caddy.
    target.write_text(candidate)
    validate = ['docker', 'exec', 'moodprint-staging-web-1', 'caddy', 'validate',
                '--config', '/etc/caddy/Caddyfile']
    reload = ['docker', 'exec', 'moodprint-staging-web-1', 'caddy', 'reload',
              '--config', '/etc/caddy/Caddyfile']
    try:
        subprocess.run(validate, check=True, capture_output=True)
        subprocess.run(reload, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        target.write_text(current)
        subprocess.run(reload, check=True, capture_output=True)
        raise RuntimeError('Gate validation failed; original configuration restored') from None
    if args.action == 'disable':
        backup.unlink()
    print(json.dumps({'releaseGate': args.action, 'configValidated': True,
                      'backendWorkersChanged': False, 'tokenPrinted': False}))


if __name__ == '__main__':
    main()
