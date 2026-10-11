#!/usr/bin/env python3
"""Verify the frozen exported source/asset and imported-skill checksums."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT/'docs/extraction-manifest.json').read_text())
failures = []
for row in manifest['files']:
    path = ROOT/row['path']
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row['export_sha256']:
        failures.append(row['path'])
print(json.dumps({'ok':not failures,'checked_files':len(manifest['files']),'changed_or_missing':failures}))
raise SystemExit(bool(failures))
