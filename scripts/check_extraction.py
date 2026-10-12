#!/usr/bin/env python3
"""Verify current exported checksums; explicitly refresh after reviewed source changes."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--refresh',action='store_true',help='refresh current exports, retain original custody hashes, prune removed paths')
args=parser.parse_args()
path=ROOT/'docs/extraction-manifest.json'
manifest=json.loads(path.read_text())
if args.refresh:
    old={row['path']:row for row in manifest['files']}
    paths={p for p in old if (ROOT/p).is_file()}
    for folder in ('zenith','system','tools','feedback','research','variants','codex','examples','tests'):
        paths.update(str(p.relative_to(ROOT)) for p in (ROOT/folder).rglob('*')
                     if p.is_file() and p.suffix in ('.py','.json','.md','.jsonl') and '__pycache__' not in p.parts)
    rows=[]
    for label in sorted(paths):
        row=dict(old.get(label,{}))
        checksum=hashlib.sha256((ROOT/label).read_bytes()).hexdigest()
        changed=row.get('export_sha256')!=checksum
        row.update(path=label,export_sha256=checksum)
        if changed or row.get('disposition')=='standalone_adaptation':
            row['disposition']='standalone_adaptation'
            row['adaptation']='Observed-system protocol with explicit source identity, units, availability and frozen horizons; authored synthetic public demonstration.'
            row.pop('source_path',None)
        rows.append(row)
    manifest['files']=rows
    manifest['copy_basis']='Original custody hashes are retained where available. Current export hashes describe the generic observed-system edition; removed source modules remain in Git history.'
    path.write_text(json.dumps(manifest,indent=2)+'\n')
failures=[row['path'] for row in manifest['files'] if not (ROOT/row['path']).is_file() or hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()!=row['export_sha256']]
print(json.dumps({'ok':not failures,'checked_files':len(manifest['files']),'changed_or_missing':failures}))
raise SystemExit(bool(failures))
