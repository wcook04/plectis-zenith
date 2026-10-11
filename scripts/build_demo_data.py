#!/usr/bin/env python3
"""Generate or check the backend-owned public graph projection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from zenith.public_graph import PUBLIC_GRAPH_PATH, build, canonical


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='fail when the generated projection is stale or absent')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    output = args.output or args.root / PUBLIC_GRAPH_PATH
    try:
        payload = build(args.root)
        content = canonical(payload)
        fresh = output.exists() and output.read_text() == content
        if not args.check:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(content)
            fresh = True
        print(json.dumps({'ok': fresh, 'schema': payload['schema'], **payload['counts']}))
        return int(not fresh)
    except (OSError, ValueError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
