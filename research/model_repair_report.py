"""Rebuild the curated cost receipt from retained local ledgers; no inference."""
from pathlib import Path
from decimal import Decimal
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
STUDIES = {
    'original': 'zenith-investigator-v1-20261013',
    'original_interface_correction': 'zenith-investigator-review-v2-20261013',
    'identical_prompt_deepseek': 'zenith-cheap-model-probe-20261013/deepseek-review',
    'deepseek_lab_smoke': 'zenith-deepseek-smoke-20261013',
    'deepseek_lossless_review': 'zenith-deepseek-lossless-review-20261013',
    'unavailable_baidu': 'zenith-deepseek-decision-audit-20261013',
    'unsupported_direct_endpoint': 'zenith-deepseek-decision-audit-direct-20261013',
    'qwen_calibration': 'zenith-qwen-decision-audit-20261013',
    'deepseek_calibration': 'zenith-deepseek-decision-audit-deepinfra-20261013',
    'qwen_capability_review': 'zenith-qwen-capability-review-20261013',
}


def build(root=ROOT):
    rows = []
    for name, directory in STUDIES.items():
        folder = root / 'work' / directory
        protocol = json.loads((folder / 'protocol.json').read_text())
        ledger_path = folder / 'budget/budget.json'
        ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {'entries': {}}
        calls = []
        for entry in ledger['entries'].values():
            receipt = entry.get('provider_receipt', {})
            calls.append({k: entry.get(k) for k in ('call_id', 'node_id', 'requested_model', 'actual_provider', 'status', 'cost', 'prompt_sha256')}
                | {'usage': receipt.get('usage', {}), 'actual_model': receipt.get('model')})
        rows.append({'study': name, 'local_directory': 'work/' + directory,
            'model': protocol.get('model'), 'calls': calls,
            'charged_calls': sum(c['cost'] is not None for c in calls),
            'reported_cost_usd': str(sum((Decimal(c['cost'] or '0') for c in calls), Decimal(0))),
            'source_hashes': {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(folder.rglob('*.json')) if p.name in ('protocol.json', 'budget.json', 'result.json', 'failure.json', 'semantic-audit.json')}})
    modern = rows[2:]
    report = {'schema': 'zenith_model_repair_cost_receipt_v1', 'date': '2026-10-13', 'studies': rows,
        'modern_charged_calls': sum(r['charged_calls'] for r in modern),
        'modern_reported_cost_usd': str(sum((Decimal(r['reported_cost_usd']) for r in modern), Decimal(0))),
        'interpretation': 'Different workloads and interfaces: not a controlled overall quality or cost comparison. See model-repair-20261013.md for semantic assessment and limits.'}
    (root / 'docs/model-repair-20261013.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    report = build()
    print(json.dumps({k: v for k, v in report.items() if k != 'studies'}, indent=2))
