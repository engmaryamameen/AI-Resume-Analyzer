"""Export backend response schemas. Run from repo root; --check rejects drift in CI."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['APP_ENV'] = 'test'
from app.api.main import app

spec = app.openapi()
routes = []
for path, methods in spec['paths'].items():
    if not path.startswith('/api/v1'): continue
    for method, operation in methods.items():
        for status, response in operation.get('responses', {}).items():
            schema = response.get('content', {}).get('application/json', {}).get('schema')
            if status.startswith('2') and schema:
                routes.append({'path': path.removeprefix('/api/v1'), 'method': method.upper(), 'status': int(status), 'schema': schema})
data = json.dumps({'components': spec['components'], 'routes': routes}, sort_keys=True, indent=2) + '\n'
target = ROOT / 'frontend/src/lib/response-contracts.json'
if '--check' in sys.argv:
    if not target.exists() or json.loads(target.read_text()) != json.loads(data):
        raise SystemExit('Response contracts changed. Run: .venv/bin/python frontend/scripts/export-contracts.py')
else: target.write_text(data)
