#!/usr/bin/env python3
"""Rebind the checked-in teaching example; never reseal a frozen experiment."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from system.core.loader import PhysicalLoader
from variants.graph import FrozenGraphLoader, build_base_identity, variant_sha256


def main():
    path = ROOT / 'examples/variants/lab_evidence_check.json'
    payload = json.loads(path.read_text())
    loader = PhysicalLoader(ROOT, inject_sys_path=False)
    payload.update(build_base_identity(loader.load_all_nodes()))
    payload['variant_sha256'] = variant_sha256(payload)
    FrozenGraphLoader(loader, payload)  # Validate before replacing the teaching example.
    path.write_text(json.dumps(payload, indent=2) + '\n')
    print(path.relative_to(ROOT))


if __name__ == '__main__':
    main()
