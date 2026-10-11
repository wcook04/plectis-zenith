#!/usr/bin/env python3
"""Project the authored graph into inspectable per-node skills; never a second owner."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from system.core.loader import PhysicalLoader
from system.lib.hashing import hash_node


def render(root: Path) -> dict[str, str]:
    loader = PhysicalLoader(root)
    graph = loader.load_all_nodes()
    result: dict[str, str] = {}
    rows = []
    for node_id, node in sorted(graph.items()):
        source = loader.manifest[node_id].relative_to(root).as_posix()
        instruction = node.instruction or "This is a tool node. Its executable module and config own its operation."
        incoming = list(node.dependencies)
        row = {"node_id": node_id, "type": node.type.value, "mission": node.group,
               "source": source, "node_hash": hash_node(node), "incoming_context": incoming,
               "output_schema": node.output_schema,
               "instruction_sha256": hashlib.sha256(node.instruction.encode()).hexdigest(),
               "skill": f"{node_id}/SKILL.md"}
        rows.append(row)
        inputs = ", ".join(f"`{dep}`" for dep in incoming) or "none"
        result[f"{node_id}/SKILL.md"] = f'''---
name: {node_id.replace('_', '-')}
description: Apply the typed {node_id} operation to its declared context.
---
# {node_id}

- Input ports: {inputs}.
- Output contract: `{node.output_schema}`. Mission: `{node.group}`.
- Implementation: `{source}`; shared contracts compile at dispatch.
- Parameters: frozen skill rule, incoming-edge weights, context budget.
- Version: `{row['node_hash']}`.
- Inspect: `python -m zenith inspect {node_id}`.

Generated projection; edit the source or a frozen experimental variant, then rebuild. These fields declare a contract; they do not prove the model follows it.
'''
    result['index.json'] = json.dumps({"schema": "zenith_node_skill_index_v1", "owner": "codex/substrate/nodes",
        "builder": "scripts/build_node_skills.py", "node_count": len(rows), "nodes": rows}, indent=2, sort_keys=True) + "\n"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = ROOT / '.agents/node-skills'
    rendered = render(ROOT)
    stale = [p for p,s in rendered.items() if not (output/p).exists() or (output/p).read_text() != s]
    extra = [p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file() and p.relative_to(output).as_posix() not in rendered] if output.exists() else []
    if args.check:
        print(json.dumps({"ok": not stale and not extra, "node_count": len(rendered)-1, "stale": stale, "unexpected": extra}))
        return int(bool(stale or extra))
    for path,content in rendered.items():
        dest=output/path; dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(content)
    print(json.dumps({"generated_nodes":len(rendered)-1,"output":str(output.relative_to(ROOT)),"unexpected":extra}))
    return int(bool(extra))

if __name__ == '__main__':
    raise SystemExit(main())
