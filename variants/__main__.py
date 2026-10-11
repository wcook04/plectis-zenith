"""Inspect frozen topology experiments without dispatching models."""
import argparse
import json
from pathlib import Path

from system.core.loader import PhysicalLoader
from system.lib.strict_json import loads_json_strict
from .graph import FrozenGraphLoader, build_base_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--variant", type=Path)
    args = parser.parse_args()
    loader = PhysicalLoader(args.root, inject_sys_path=False)
    if args.variant:
        payload = loads_json_strict(args.variant.read_text(), source=str(args.variant))
        output = FrozenGraphLoader(loader, payload).receipt
    else:
        output = build_base_identity(loader.load_all_nodes())
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
