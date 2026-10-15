#!/usr/bin/env python3
"""Prepare a funding-only continuation of a terminal, unopened conformance run.

The original run remains byte-for-byte untouched. A new directory replays its
exact paid responses through the provider's immutable call IDs, then pays only
for previously unattempted nodes under an explicitly enlarged reservation cap.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.conformance_study import replay_partial, run, verify
from scripts.build_conformance_report import checked_billing, checked_call_frames
from zenith.budgeted import amount
from zenith.providers import digest, write_json

SCHEMA = "zenith_conformance_funding_continuation_v1"
MAX_AUTHORIZED_USD = Decimal("4")
REMOVED_ON_CLONE = {"started.json", "frozen.json", "frozen-receipt.json"}
ADMINISTRATIVE_MUTATIONS = {"protocol.json", "preparation.json", "budget/budget.json"}


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_hashes(folder: Path) -> dict[str, str]:
    if folder.is_symlink() or any(path.is_symlink() for path in folder.rglob("*")):
        raise ValueError("Continuation source contains symlinks")
    return {str(path.relative_to(folder)): sha(path)
            for path in sorted(folder.rglob("*")) if path.is_file()}


def _budget_entries(original: Path, protocol: dict) -> dict:
    budget = read(original / "budget/budget.json")
    entries = budget["entries"]
    if not isinstance(entries, dict) or not entries or budget["halted"]:
        raise ValueError("Original budget is empty, halted, or malformed")
    if any(row["status"] != "response_supplied" or row.get("cost") is None
           for row in entries.values()):
        raise ValueError("Failed, unknown, or active paid attempts cannot be continued")
    if (budget["limits"]["max_cost_usd"] != protocol["max_cost_usd"] or
            budget["limits"]["max_calls"] != protocol["max_calls"] or
            budget["limits"]["max_output_tokens"] != protocol["max_output_tokens"] or
            Path(budget["limits"]["budget_dir"]).resolve() != (original / "budget").resolve()):
        raise ValueError("Original budget differs from frozen protocol")
    checked_billing(budget, [row["node_id"] for row in entries.values()], complete=True)
    checked_call_frames(original, list(entries.values()))
    if len(entries) >= protocol["max_calls"]:
        raise ValueError("Call ceiling, not funding, ended the original run")
    return budget


def _preflight(original: Path, freeze: Path) -> tuple[dict, dict, dict, dict]:
    original = original.resolve()
    protocol, data = verify(original)
    if (not (original / "started.json").is_file() or
            not (original / "frozen.json").is_file() or
            any((original / name).exists() for name in (
                "screen.json", "confirmation.json", "screen-selection.json",
                "confirmation-selection.json", "screen-summary.json",
                "confirmation-summary.json"))):
        raise ValueError("Expected a terminal started run with unopened protected panels")
    frozen = read(original / "frozen.json")
    if frozen["complete"] or not any(
        "worst-case reservation would exceed the shared paid budget" in row["error"]
        for row in frozen["failures"]
    ):
        raise ValueError("Original run did not stop at the reservation cap")
    partial = replay_partial(original)
    if (not partial["ok"] or partial["unknown_cost_attempts"] or
            partial["protected_partitions"]):
        raise ValueError("Original partial replay failed or contains unknown costs")
    budget = _budget_entries(original, protocol)
    if (partial["budget_attempts"] != len(budget["entries"]) or
            partial["response_files_replayed"] != len(budget["entries"])):
        raise ValueError("Original paid responses are not fully replayable")
    prospective = read(freeze)
    expected = prospective["diagnostic"]
    if (prospective.get("schema") != "zenith_progress_prospective_freeze_v1" or
            sha(original / "protocol.json") != expected["protocol_sha256"] or
            digest(data) != expected["dataset_sha256"] or
            protocol["max_calls"] != expected["maximum_model_calls"]):
        raise ValueError("Original diagnostic differs from its prospective freeze")
    return protocol, data, budget, partial


def prepare(original: Path, continuation: Path, freeze: Path, *,
            max_cost_usd: str = "4") -> dict:
    original, continuation, freeze = (Path(original).resolve(), Path(continuation).resolve(),
                                      Path(freeze).resolve())
    if continuation.exists() or continuation == original or original in continuation.parents:
        raise ValueError("Continuation must be a fresh directory outside the original")
    limit = amount(max_cost_usd, "amended maximum cost")
    if limit > MAX_AUTHORIZED_USD:
        raise ValueError("Amended cap exceeds the authorized $4 ceiling")
    protocol, data, budget, partial = _preflight(original, freeze)
    if limit <= amount(protocol["max_cost_usd"]):
        raise ValueError("Funding amendment must enlarge the original cap")
    before = file_hashes(original)
    tmp = continuation.with_name(continuation.name + ".preparing-" + uuid.uuid4().hex)
    try:
        shutil.copytree(original, tmp)
        for name in REMOVED_ON_CLONE:
            (tmp / name).unlink()
        amended = dict(protocol, max_cost_usd=str(limit))
        write_json(tmp / "protocol.json", amended)
        preparation = read(tmp / "preparation.json")
        preparation["protocol_sha256"] = digest(amended)
        write_json(tmp / "preparation.json", preparation)
        new_budget = read(tmp / "budget/budget.json")
        new_budget["limits"] = dict(new_budget["limits"], max_cost_usd=str(limit),
                                     budget_dir=str(continuation / "budget"))
        write_json(tmp / "budget/budget.json", new_budget)
        bindings = {}
        for path in sorted((tmp / "providers").glob("*/handoff/budgeted_binding.json")):
            relative = str(path.relative_to(tmp))
            binding = read(path)
            if binding["limits"] != budget["limits"]:
                raise ValueError(f"Original provider binding differs from budget: {relative}")
            binding["limits"] = dict(new_budget["limits"])
            write_json(path, binding)
            bindings[relative] = sha(path)
        if not bindings:
            raise ValueError("No original paid provider bindings found")
        if read(tmp / "datasets.json") != data or read(tmp / "protocol.json") != amended:
            raise ValueError("Science data or funding amendment changed during copy")
        changed = ADMINISTRATIVE_MUTATIONS | set(bindings)
        copied = file_hashes(tmp)
        if (set(copied) != set(before) - REMOVED_ON_CLONE or
                any(copied[name] != old_hash for name, old_hash in before.items()
                    if name not in REMOVED_ON_CLONE | changed)):
            raise ValueError("Continuation clone changed scientific or paid evidence")
        receipt = {
            "schema": SCHEMA,
            "boundary": "Funding-only amendment before resumed inference; original terminal run is immutable, its protected panels unopened, and every previous paid response is reused by exact provider identity. No failed or unknown attempt is retried.",
            "original_name": original.name,
            "continuation_name": continuation.name,
            "prospective_freeze_sha256": sha(freeze),
            "original_protocol_sha256": sha(original / "protocol.json"),
            "amended_protocol_sha256": sha(tmp / "protocol.json"),
            "dataset_sha256": digest(data),
            "original_cap_usd": protocol["max_cost_usd"],
            "amended_cap_usd": str(limit),
            "prior_paid_attempts": len(budget["entries"]),
            "prior_reported_cost_usd": budget["total_reported_cost_usd"],
            "prior_reserved_usd": budget["total_reserved_usd"],
            "prior_call_ids": sorted(budget["entries"]),
            "prior_node_ids": sorted(row["node_id"] for row in budget["entries"].values()),
            "original_files": before,
            "clone_administrative_files": {name: copied[name] for name in sorted(changed)},
            "copied_scientific_file_count": len(copied) - len(changed),
            "terminal_partial_replay": partial,
        }
        write_json(tmp / "funding-continuation.json", receipt)
        if file_hashes(original) != before:
            raise ValueError("Original terminal evidence changed while preparing continuation")
        tmp.rename(continuation)
        return receipt
    except BaseException:
        if tmp.exists():
            shutil.rmtree(tmp)
        raise


def verify_prepared(continuation: Path, original: Path, freeze: Path) -> dict:
    continuation, original, freeze = (Path(continuation).resolve(), Path(original).resolve(),
                                      Path(freeze).resolve())
    receipt = read(continuation / "funding-continuation.json")
    if (receipt.get("schema") != SCHEMA or receipt["original_name"] != original.name or
            receipt["continuation_name"] != continuation.name or
            receipt["prospective_freeze_sha256"] != sha(freeze) or
            file_hashes(original) != receipt["original_files"] or
            (continuation / "started.json").exists()):
        raise ValueError("Original custody changed or continuation already started")
    protocol, data = verify(continuation)
    original_protocol = read(original / "protocol.json")
    prospective = read(freeze)
    original_budget = read(original / "budget/budget.json")
    expected_admin = ADMINISTRATIVE_MUTATIONS | {
        str(path.relative_to(original))
        for path in (original / "providers").glob("*/handoff/budgeted_binding.json")
    }
    cap = amount(protocol["max_cost_usd"], "amended maximum cost")
    if (cap > MAX_AUTHORIZED_USD or cap <= amount(original_protocol["max_cost_usd"]) or
            receipt["original_cap_usd"] != original_protocol["max_cost_usd"] or
            receipt["original_protocol_sha256"] != sha(original / "protocol.json") or
            receipt["original_protocol_sha256"] != prospective["diagnostic"]["protocol_sha256"] or
            digest(data) != prospective["diagnostic"]["dataset_sha256"] or
            protocol["max_calls"] != prospective["diagnostic"]["maximum_model_calls"] or
            set(receipt["clone_administrative_files"]) != expected_admin or
            receipt["prior_paid_attempts"] != len(original_budget["entries"]) or
            receipt["prior_call_ids"] != sorted(original_budget["entries"]) or
            receipt["prior_node_ids"] != sorted(
                row["node_id"] for row in original_budget["entries"].values())):
        raise ValueError("Funding receipt differs from original freeze, authority, or paid identities")
    if (dict(protocol, max_cost_usd=original_protocol["max_cost_usd"]) != original_protocol or
            digest(data) != receipt["dataset_sha256"] or
            sha(continuation / "protocol.json") != receipt["amended_protocol_sha256"] or
            protocol["max_cost_usd"] != receipt["amended_cap_usd"]):
        raise ValueError("Continuation changed scientific fields or amended protocol")
    prior = read(original / "budget/budget.json")["entries"]
    current = read(continuation / "budget/budget.json")
    if (current["entries"] != prior or
            current["total_reserved_usd"] != receipt["prior_reserved_usd"] or
            current["total_reported_cost_usd"] != receipt["prior_reported_cost_usd"] or
            current["limits"]["max_cost_usd"] != receipt["amended_cap_usd"] or
            current["limits"]["budget_dir"] != str(continuation / "budget")):
        raise ValueError("Continuation prior paid ledger changed")
    now_files = file_hashes(continuation)
    expected = (set(receipt["original_files"]) - REMOVED_ON_CLONE |
                {"funding-continuation.json"})
    if set(now_files) != expected:
        raise ValueError("Prepared continuation file membership changed")
    changed = ADMINISTRATIVE_MUTATIONS | set(receipt["clone_administrative_files"])
    for name, old_hash in receipt["original_files"].items():
        if name not in REMOVED_ON_CLONE | changed and now_files[name] != old_hash:
            raise ValueError(f"Prepared scientific or paid file changed: {name}")
    if any(now_files[name] != expected_hash for name, expected_hash in
           receipt["clone_administrative_files"].items()):
        raise ValueError("Prepared funding administration changed")
    return receipt


def run_prepared(continuation: Path, original: Path, freeze: Path,
                 env_file: Path | None = None) -> dict:
    receipt = verify_prepared(continuation, original, freeze)
    result = run(continuation, env_file)
    original = Path(original).resolve()
    continuation = Path(continuation).resolve()
    if file_hashes(original) != receipt["original_files"]:
        raise ValueError("Original terminal study changed during continuation")
    for name, old_hash in receipt["original_files"].items():
        if name.startswith(("prompts/", "responses/")) and sha(continuation / name) != old_hash:
            raise ValueError(f"Previously paid prompt or response changed: {name}")
    current = read(continuation / "budget/budget.json")["entries"]
    old = read(original / "budget/budget.json")["entries"]
    if any(current.get(call_id) != entry for call_id, entry in old.items()):
        raise ValueError("Previously paid ledger entries changed")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for action in ("prepare", "verify", "run"):
        command = sub.add_parser(action)
        command.add_argument("original", type=Path)
        command.add_argument("continuation", type=Path)
        command.add_argument("--prospective-freeze", type=Path, required=True)
        if action == "prepare":
            command.add_argument("--max-cost-usd", default="4")
        if action == "run":
            command.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.original, args.continuation, args.prospective_freeze,
                         max_cost_usd=args.max_cost_usd)
    elif args.command == "verify":
        result = verify_prepared(args.continuation, args.original, args.prospective_freeze)
    else:
        result = run_prepared(args.continuation, args.original, args.prospective_freeze,
                              args.env_file)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
