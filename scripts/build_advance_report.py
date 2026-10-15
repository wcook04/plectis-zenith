#!/usr/bin/env python3
"""Project the separate, source-bound Advance studies without pooling accuracy."""
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_conformance_report import safe_relative, verify_manifest

STUDIES = ('deepseek-low-v1', 'ling-qualification-v2', 'ling-interrupted-v3', 'ling-full-v3b',
           'deepseek-reasoning-v3c')


def read(path):
    return json.loads(path.read_text())


def build(root=ROOT):
    studies, bindings = [], {}
    for name in STUDIES:
        folder = root / 'examples/conformance' / name
        if not folder.exists():
            continue
        checked = verify_manifest(folder)
        bindings[str((folder / 'manifest.json').relative_to(root))] = hashlib.sha256((folder / 'manifest.json').read_bytes()).hexdigest()
        protocol, frozen, billing = checked['protocol'], read(folder / 'frozen.json'), checked['billing']
        unresolved = [r for r in billing['entries'] if r.get('cost') is None]
        studies.append(dict(id=name, complete=frozen['complete'], calls=len(billing['entries']),
            model=protocol['model'], reasoning_effort=protocol['reasoning_effort'],
            reported_cost_usd=billing['total_reported_cost_usd'],
            unresolved_attempts=len(unresolved),
            unresolved_reserved_usd=str(sum((Decimal(r['reserved_cost_usd']) for r in unresolved), Decimal(0))),
            panel_summary={p:read(folder / f'{p}-summary.json') for p in ('screen', 'confirmation') if (folder / f'{p}-summary.json').exists()},
            failures=frozen['failures']))
    folder = root / 'examples/continuation-memory/leave-one-out-v1'
    memory = {}
    if folder.exists():
        manifest = read(folder / 'manifest.json')
        for row in manifest['files']:
            raw = (folder / safe_relative(row['path'])).read_bytes()
            if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError(f'Memory artifact changed: {row["path"]}')
        with ZipFile(folder / 'source.zip') as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or set(names) != {r['path'] for r in manifest['members']}:
                raise ValueError('Memory archive membership changed')
            for row in manifest['members']:
                safe_relative(row['path'])
                raw = archive.read(row['path'])
                if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
                    raise ValueError(f'Memory artifact changed: {row["path"]}')
            for published, archived in (('results.json', 'run-v1/results.json'), ('suffix-transfer-v2-results.json', 'run-v2/results.json')):
                if (folder / published).read_bytes() != archive.read(archived):
                    raise ValueError('Published memory results differ from archived evidence')
        for name in ('results.json', 'suffix-transfer-v2-results.json', 'manifest.json'):
            path = folder / name
            bindings[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        joint, transfer = (read(folder / n) for n in ('results.json', 'suffix-transfer-v2-results.json'))
        joint_rows = [{k:r[k] for k in ('ordering', 'initial_calls', 'cache_only_extension_calls', 'retained_tests_extension_calls', 'extension_calls_saved', 'cache_only_lifetime_calls', 'retained_tests_lifetime_calls')} for r in joint['cases']]
        transfer_rows = [dict(target=r['condition']['target_original_teacher'], **{k:r[k] for k in ('generic_target_calls', 'transferred_target_calls', 'target_calls_saved', 'generic_lifetime_calls', 'transferred_lifetime_calls')}) for r in transfer['cases']]
        ordinary_calls = sum(r['receipt']['new_teacher_cost']['teacher_calls'] for r in joint['ordinary_modules'])
        memory = dict(model_calls=joint['model_calls']+transfer['model_calls'], joint_conditions=joint_rows,
            ordinary_modules_calls=ordinary_calls, suffix_transfer_conditions=transfer_rows,
            summary=f"Retained questions reduce extension queries in {joint['savings_conditions']}/6 matched-cache conditions. Separate ordinary modules use {ordinary_calls} total teacher executions, less than every joint lifetime. Transferring all acquired suffixes into ordinary modules helps {transfer['savings_conditions']}/6 and hurts {transfer['regression_conditions']}/6. These correlated synthetic conditions do not establish improved general learning.")
    unresolved = sum(r['unresolved_attempts'] for r in studies)
    retained_path = root / 'examples/conformance/learned-regressions.json'
    retained = None
    if retained_path.exists():
        relative = str(retained_path.relative_to(root))
        bindings[relative] = hashlib.sha256(retained_path.read_bytes()).hexdigest()
        retained = dict(path=relative, boundary=read(retained_path)['boundary'])
    return dict(schema='zenith_advance_campaign_v1', status='complete' if len(studies)==len(STUDIES) and memory else 'pending',
        summary='Programs, measured experiments and retained questions form the implemented loop. Native model comparisons and algebraic memory follow-ups remain separate. Partial runs and unknown billing are retained; analysis completion is not experimental construction success.',
        total_calls=sum(r['calls'] for r in studies),
        total_reported_cost_usd=str(sum((Decimal(r['reported_cost_usd']) for r in studies), Decimal(0))),
        unresolved_attempts=unresolved,
        accounting_boundary=f'Calls count reserved provider attempts, including interrupted delivery. {unresolved} attempt(s) have unknown final charges. Reported cost is the known total; reservations are ceilings, not invoices.',
        conformance_studies=studies, memory=memory, retained_regression=retained, source_bindings=bindings)


if __name__ == '__main__':
    result = build()
    (ROOT / 'docs/history/advance-campaign-20261014.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status', 'total_calls', 'total_reported_cost_usd', 'unresolved_attempts')}))
