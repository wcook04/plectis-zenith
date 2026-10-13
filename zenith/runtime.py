"""Portable controls over the extracted engine, not a second mission scheduler."""
from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from system.core.engine import GodModeEngine
from system.core.governance import compute_waves, validate_topology
from system.core.loader import PhysicalLoader
from system.lib.hashing import hash_node
from system.lib.types import ExecutionMode, RunMode
from system.lib.utils import resolve_runs_dir
from .providers import AgentProvider, CapturedProvider, OpenRouterFreeProvider, NvidiaNimProvider, digest, text_digest, verify_packet, verify_response, write_json

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
MISSION_TARGETS = {"lab": "lab_integrity", "oracle": "oracle_cp2_emitter", "feeds": "global_derived_feed", "refinement": "version_committer"}
MISSION_TARGETS.update(basket="basket_final", basket_serial="basket_serial_final", basket_evolve="basket_evolve")


def _graph_loader(root: Path, graph_variant: dict | None = None, task_profile: str = "generic"):
    loader = PhysicalLoader(Path(root))
    if task_profile == "financial_investigator_v1":
        from .investigator import InvestigatorGraphLoader
        loader = InvestigatorGraphLoader()
    elif task_profile == "financial":
        from .market_graph import MarketGraphLoader
        loader = MarketGraphLoader(loader)
    elif task_profile != "generic":
        raise ValueError("unknown task profile")
    if graph_variant is not None:
        if not isinstance(graph_variant, dict):
            raise ValueError("graph variant must be an object")
        from variants.graph import FrozenGraphLoader
        loader = FrozenGraphLoader(loader, graph_variant)
    return loader


def load_graph(root: Path, graph_variant: dict | None = None, task_profile: str = "generic"):
    return _graph_loader(root, graph_variant, task_profile).load_all_nodes()


def graph_for_manifest(root: Path, spec: dict):
    """Hydrate the effective frozen graph, including explicitly admitted topology edits."""
    return load_graph(root, spec.get("graph_variant"), spec.get("task_profile", "generic"))


def scope_for(graph: dict, target: str) -> set[str]:
    # Invoke the actual engine scope policy without constructing a run/bridge.
    context = SimpleNamespace(_universe=graph, logger=logging.getLogger("zenith.plan"))
    GodModeEngine._resolve_execution_scope(context, target)
    return context._execution_scope


def plan(root: Path, mission: str, target: str | None = None, graph_variant: dict | None = None, task_profile: str = "generic") -> dict:
    graph = load_graph(root, graph_variant, task_profile)
    if task_profile == "financial_investigator_v1":
        from .investigator import TARGETS
        if mission not in TARGETS or graph_variant:
            raise ValueError("investigator profile supports Lab and combined refinement review only")
        selected = target or TARGETS[mission]
        if selected != TARGETS[mission]:
            raise ValueError("investigator profile requires its complete mission target")
    else:
        selected = target or MISSION_TARGETS[mission]
    scope = scope_for(graph, selected)
    scoped = {key: graph[key] for key in scope}
    waves = compute_waves(scoped)
    return {"schema": "zenith_mission_plan_v1", "mission": mission, "target": selected,
            "node_count": len(scoped), "wave_count": len(waves), "waves": waves,
            "nodes": [{"id": key, "type": node.type.value, "group": node.group,
                       "lane": node.lane, "dependencies": list(node.dependencies),
                       "output_schema": node.output_schema, "node_hash": hash_node(node)}
                      for key, node in sorted(scoped.items())],
            "execution": "offline_plan_no_provider_or_run_state"}


def validate(root: Path) -> dict:
    graph = load_graph(root)
    issues = validate_topology(graph)
    return {"schema": "zenith_topology_validation_v1", "node_count": len(graph), "ok": not issues,
            "issues": [{"code": item.code, "message": item.message, "node_id": item.node_id} for item in issues]}


def runs_root(root: Path) -> Path:
    config_path = Path(root) / "master_config.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    return resolve_runs_dir(root, config.get("paths", {}).get("runs_dir"))


def safe_run_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", value) or value in (".", ".."):
        raise ValueError("run_id must be a simple local name (letters, numbers, _, . or -)")
    return value


def stamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("temporal anchor requires a timezone")
    return parsed.astimezone(timezone.utc)


def resolve_source(root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        # Named runs belong to configured runs root; existing relative directories also work.
        candidate = Path(root) / path
        path = candidate if candidate.is_dir() else runs_root(root) / path
    path = path.resolve()
    if not path.is_dir() or not (path / "artifacts").is_dir():
        raise ValueError(f"source run must contain an artifacts directory: {value}")
    return path


def forward_preflight(root: Path, source: Path, anchor: datetime) -> None:
    """Do not hydrate realized/future records into the forward-only Lab."""
    if anchor > datetime.now(timezone.utc):
        raise ValueError("Lab time anchor cannot be in the future")
    context_path = source / "runtime_context.json"
    if context_path.exists():
        context = json.loads(context_path.read_text())
        for key in ("as_of", "time_anchor"):
            if context.get(key) and stamp(str(context[key])) > anchor:
                raise ValueError("Lab feed source context is later than the prediction anchor")
        if context.get("subject_group") == "oracle" or context.get("oracle_mode"):
            raise ValueError("Oracle truth run cannot be used as Lab forward evidence")
    for node in load_graph(root).values():
        if not node.meta.get("is_feed"):
            continue
        path = source / "artifacts" / f"{node.id}.json"
        if not path.exists():
            continue  # The original engine will classify a missing required feed.
        envelope = json.loads(path.read_text())
        metadata = envelope.get("metadata", {})
        for key in ("as_of", "timestamp_iso"):
            if metadata.get(key) and stamp(str(metadata[key])) > anchor:
                raise ValueError(f"Lab feed {node.id}.{key} is later than the prediction anchor")
        data = envelope.get("data", {})
        rows = data.get("observations", []) + data.get("items", []) if isinstance(data, dict) else []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("observation row must be an object")
            for key in ("observed_at", "available_at"):
                if not row.get(key) or stamp(str(row[key])) > anchor:
                    raise ValueError(f"Lab observation {key} missing or later than cutoff")
            if stamp(row["available_at"]) < stamp(row["observed_at"]):
                raise ValueError("observation availability precedes observation")


@contextlib.contextmanager
def run_lock(run_dir: Path):
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / ".zenith.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("this run already has an active Zenith command") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def provider_for(run_dir: Path, spec: dict):
    name = spec["provider"]
    if name == "agent":
        return AgentProvider(run_dir)
    if name == "captured":
        return CapturedProvider(run_dir, Path(spec["responses"]))
    if name == "openrouter_free":
        return OpenRouterFreeProvider(run_dir, spec.get("model"))
    if name == "nvidia_nim":
        return NvidiaNimProvider(run_dir, spec.get("model"))
    if name == "openrouter_budgeted":
        from .budgeted import OpenRouterBudgetedProvider
        return OpenRouterBudgetedProvider(run_dir, spec.get("model"),
                                          provider_slug=spec.get("provider_slug"),
                                          **spec["paid_budget"])
    raise ValueError(f"unknown provider {name}")


class CompactContextEngine(GodModeEngine):
    """Original engine with an explicit input projection before prompt assembly/hash."""
    def _gather_inputs(self, node):
        from .context import gather_compact_feed_inputs
        return gather_compact_feed_inputs(self, node, super()._gather_inputs(node))


def _engine(root: Path, run_dir: Path, spec: dict, *, resume: bool, provider=None):
    loader = None
    if spec.get("graph_variant") is not None or spec.get("task_profile", "generic") != "generic":
        loader = _graph_loader(root, spec.get("graph_variant"), spec.get("task_profile", "generic"))
    engine_type = CompactContextEngine if spec.get("context_profile") == "compact_feeds" else GodModeEngine
    if spec.get("task_profile") == "financial":
        from .market_graph import MarketEngine
        engine_type = MarketEngine
    if spec.get("task_profile") == "financial_investigator_v1":
        from .investigator import InvestigatorEngine
        engine_type = InvestigatorEngine
    engine = engine_type(run_id=run_dir.name, root_dir=str(root), loader=loader,
                         run_mode=RunMode.RESUME if resume else RunMode.FRESH,
                         execution_mode=ExecutionMode.LAB if spec.get("feed_source") else ExecutionMode.RUNTIME,
                         feed_source_run_id=spec.get("feed_source"), subject_group=spec["mission"],
                         horizon=spec.get("horizon"), time_anchor=spec.get("time_anchor"),
                         oracle_subject_run_dir=spec.get("subject_run"), oracle_truth_run_dir=spec.get("truth_run"),
                         bridge=provider or provider_for(run_dir, spec), reasoning_policy=spec.get("reasoning_policy"))
    if spec.get("task_profile") == "financial_investigator_v1":
        engine.investigation_policy = spec["investigation_policy"]
    return engine


def status(root: Path, run_id: str) -> dict:
    run_dir = runs_root(root) / safe_run_id(run_id)
    spec_path = run_dir / "zenith_run.json"
    if not spec_path.exists():
        raise ValueError("run has no Zenith execution manifest")
    spec = json.loads(spec_path.read_text())
    complete, failed, engine_failure_nodes = [], [], []
    for node_id in spec["scope"]:
        path = run_dir / "artifacts" / f"{node_id}.json"
        if path.exists():
            envelope = json.loads(path.read_text())
            if envelope.get("status") in ("success", "loaded"):
                complete.append(node_id)
            elif envelope.get("status") == "failure":
                engine_failure_nodes.append(node_id)
                error = str(envelope.get("metadata", {}).get("error") or "")
                # Missing human/agent responses are a handoff, not a provider/model failure.
                if not error.startswith("Agent response pending:"):
                    failed.append(node_id)
    pending = []
    for path in sorted((run_dir / "handoff" / "requests").glob("*.json")):
        packet = json.loads(path.read_text())
        if packet["node_id"] not in complete and not (run_dir / "handoff" / "responses" / path.name).exists():
            pending.append({"node_id": packet["node_id"], "packet_id": packet["packet_id"], "packet_path": str(path),
                            "prompt_sha256": packet["prompt_sha256"]})
    summary_path = run_dir / "run_summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else None
    outcome = "completed" if len(complete) == len(spec["scope"]) else "awaiting_agent" if pending else "failed" if failed else "incomplete"
    return {"schema": "zenith_run_status_v1", "run_id": run_id, "mission": spec["mission"],
            "status": outcome, "completed_count": len(complete), "scope_count": len(spec["scope"]),
            "failed_nodes": failed, "pending": pending, "engine_failure_nodes": engine_failure_nodes, "run_summary": summary,
            "execution_kind": "captured_replay" if spec["provider"] == "captured" else spec["provider"],
            "claim_boundary": "Execution and contract validation do not establish forecasting accuracy or usefulness for the observed system."}


def _source_hashes(directories: list[Path]) -> dict:
    # Freeze input bytes, including provenance/readiness, before any engine hydration.
    import hashlib
    result = {}
    for directory in directories:
        paths = [directory / "runtime_context.json", *sorted((directory / "artifacts").glob("*.json"))]
        result[str(directory)] = {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in paths if path.is_file()}
    return result


def implementation_hashes() -> dict:
    """Freeze actual executing Python implementation, independent of data-root placement."""
    import hashlib
    package_root = Path(__file__).resolve().parents[1]
    paths = []
    for folder in ("zenith", "system/core", "system/lib", "tools", "variants"):
        paths.extend((package_root / folder).rglob("*.py"))
    return {str(path.relative_to(package_root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths) if path.is_file()}


def _check_frozen_graph(root: Path, spec: dict) -> None:
    if spec.get("implementation_hashes") is not None and implementation_hashes() != spec["implementation_hashes"]:
        raise ValueError("pipeline implementation changed since preparation; start a new run")
    graph = graph_for_manifest(root, spec)
    actual = {key: hash_node(graph[key]) for key in spec["scope"] if key in graph}
    if actual != spec["node_hashes"]:
        raise ValueError("mission source changed since run preparation; start a new run")
    if spec.get("graph_variant_source"):
        variant_path = Path(spec["graph_variant_source"])
        if not variant_path.exists() or text_digest(variant_path.read_text()) != spec["graph_variant_source_sha256"]:
            raise ValueError("frozen graph variant source changed; start a new variant run")
    if spec.get("policy_source"):
        policy_path = Path(spec["policy_source"])
        if not policy_path.exists() or text_digest(policy_path.read_text()) != spec["policy_source_sha256"]:
            raise ValueError("frozen reasoning policy source changed; start a new variant run")
    source_hashes = spec.get("source_hashes", {})
    if _source_hashes([Path(path) for path in source_hashes]) != source_hashes:
        raise ValueError("recorded source run changed since preparation; start a new run")


def start(root: Path, *, mission: str, run_id: str, provider: str = "agent", target: str | None = None,
          feed_source: str | None = None, subject_run: str | None = None, truth_run: str | None = None,
          horizon: str | None = None, time_anchor: str | None = None, responses: str | None = None,
          model: str | None = None, policy: str | None = None, graph_variant: str | None = None,
          context_profile: str = "original", max_cost_usd=None, max_calls: int | None = None,
          max_output_tokens: int = 4096, budget_dir: str | Path | None = None,
          provider_slug: str | None = None, task_profile: str = "generic",
          replay_from: str | None = None, replay_node: str | None = None) -> dict:
    root = Path(root).resolve()
    if context_profile not in ("original", "compact_feeds"):
        raise ValueError("unknown context profile")
    variant_path = Path(graph_variant).resolve() if graph_variant else None
    variant_payload = json.loads(variant_path.read_text()) if variant_path else None
    selected = plan(root, mission, target, variant_payload, task_profile)
    if task_profile == "financial" and (context_profile != "original" or graph_variant):
        raise ValueError("financial task profile uses the full original topology and context protocol")
    if task_profile == "financial_investigator_v1" and (context_profile != "original" or graph_variant):
        raise ValueError("investigator profile has its own frozen context and graph protocol")
    if bool(replay_from) != bool(replay_node):
        raise ValueError("replay requires source and intervention node")
    if replay_from and (task_profile not in ("financial", "financial_investigator_v1") or mission != "lab"):
        raise ValueError("local replay is supported for the financial Lab only")
    run_dir = runs_root(root) / safe_run_id(run_id)
    if run_dir.exists():
        raise ValueError("run already exists; use resume with its frozen manifest")
    if mission in ("lab", "basket", "basket_serial", "basket_evolve"):
        if subject_run or truth_run:
            raise ValueError("Lab is forward-only; subject/truth pairing belongs to Oracle")
        if not feed_source:
            raise ValueError("Lab requires --feed-source with a recorded feed run")
    if mission == "oracle" and (not subject_run or not truth_run):
        raise ValueError("Oracle requires both --subject-run and --truth-run")
    if provider == "nvidia_nim" and not model:
        raise ValueError("nvidia_nim requires an explicit --model")
    if provider == "openrouter_free" and not model:
        import os
        model = os.environ.get("OPENROUTER_CHAT_MODEL")
    paid_budget = None
    if provider == "openrouter_budgeted":
        from .budgeted import budget_options, normalize_provider_slug
        paid_budget = budget_options(model, max_cost_usd, max_calls, max_output_tokens, budget_dir)
        provider_slug = normalize_provider_slug(provider_slug)
    elif max_cost_usd is not None or max_calls is not None or budget_dir is not None or provider_slug is not None:
        raise ValueError("paid budget options require --provider openrouter_budgeted")
    if provider == "captured" and not responses:
        raise ValueError("captured provider requires --responses")
    if mission == "refinement" and task_profile not in ("financial", "financial_investigator_v1"):
        raise ValueError("Evolve uses its reviewed pair runner; inspect the graph or use tools/refinement/run_evolve.py")
    if mission == "refinement" and task_profile in ("financial", "financial_investigator_v1") and not feed_source:
        raise ValueError("financial Evolve requires its recorded Lab/Oracle evidence packet")
    source = resolve_source(root, feed_source) if feed_source else None
    if source:
        if time_anchor is None:
            context = source / "runtime_context.json"
            data = json.loads(context.read_text()) if context.exists() else {}
            time_anchor = data.get("as_of") or data.get("time_anchor")
        time_anchor = time_anchor or datetime.now(timezone.utc).isoformat()
        forward_preflight(root, source, stamp(time_anchor))
    subject = resolve_source(root, subject_run) if subject_run else None
    truth = resolve_source(root, truth_run) if truth_run else None
    if mission == "oracle" and subject is not None and horizon is None:
        context_path = subject / "runtime_context.json"
        context = json.loads(context_path.read_text()) if context_path.exists() else {}
        horizon = (context.get("horizon") or {}).get("target_time_iso")
    spec = {"schema": "zenith_execution_manifest_v1", "run_id": run_id, "mission": mission,
            "target": selected["target"], "scope": [node["id"] for node in selected["nodes"]],
            "node_hashes": {node["id"]: node["node_hash"] for node in selected["nodes"]},
            "provider": provider, "feed_source": str(source) if source else None,
            "subject_run": str(subject) if subject else None, "truth_run": str(truth) if truth else None,
            "horizon": horizon, "time_anchor": time_anchor,
            "responses": str(Path(responses).resolve()) if responses else None, "model": model,
            "context_profile": context_profile, "task_profile": task_profile,
            "implementation_hashes": implementation_hashes()}
    if task_profile == "financial_investigator_v1":
        from .investigator_contracts import DEFAULT_PROCEDURE
        from system.lib.reasoning_policy import investigation_policy
        spec["investigation_policy"] = investigation_policy(DEFAULT_PROCEDURE)
    if paid_budget is not None:
        spec["paid_budget"] = paid_budget
    if provider_slug is not None:
        spec["provider_slug"] = provider_slug
    if variant_path:
        spec["graph_variant"] = variant_payload
        spec["graph_variant_source"] = str(variant_path)
        spec["graph_variant_source_sha256"] = text_digest(variant_path.read_text())
    if policy:
        from system.lib.reasoning_policy import validate_reasoning_policy, validate_investigation_policy
        policy_path = Path(policy).resolve()
        payload = json.loads(policy_path.read_text())
        if task_profile == "financial_investigator_v1":
            spec["investigation_policy"] = validate_investigation_policy(payload)
        else:
            spec["reasoning_policy"] = validate_reasoning_policy(payload, graph_for_manifest(root, spec))
        spec["policy_source"] = str(policy_path)
        spec["policy_source_sha256"] = text_digest(policy_path.read_text())
    source_dirs = [path for path in (source, subject, truth) if path is not None]
    if replay_from:
        spec["replay_from"] = str(resolve_source(root, replay_from))
        spec["replay_node"] = replay_node
        source_dirs.append(Path(spec["replay_from"]))
    spec["source_hashes"] = _source_hashes(source_dirs)
    if task_profile == "financial_investigator_v1" and mission == "lab":
        from .investigator import read
        from .basket_panel import InvestigationStore
        case = read(source,"investigator_case")
        InvestigationStore(case)  # Verify external array hashes before provider construction.
        if stamp(time_anchor).date().isoformat() != case["cutoff"]:
            raise ValueError("investigator anchor differs from cutoff snapshot")
        if replay_from:
            old = json.loads((Path(spec["replay_from"])/"zenith_run.json").read_text())
            _check_frozen_graph(root,old)
            if replay_node != "investigator_entry":
                raise ValueError("investigator procedure edits replay from investigator_entry")
            for field in ("task_profile","feed_source","time_anchor","horizon","model","provider","node_hashes"):
                if old.get(field) != spec.get(field):
                    raise ValueError("investigator replay changed "+field)
            if status(root,old["run_id"])["status"] != "completed":
                raise ValueError("investigator replay requires a complete subject")
            spec["replay_receipt"] = {"boundary":"whole Lab from entry", "source":spec["replay_from"],
                "reused_reasoning_outputs":[], "interpretation":"outcome-informed development replay, not held-out evidence"}
    with run_lock(run_dir):
        bridge = provider_for(run_dir, spec)
        engine = _engine(root, run_dir, spec, resume=False, provider=bridge)
        if replay_from and task_profile == "financial":
            from .market_graph import seed_replay
            spec["replay_receipt"] = seed_replay(engine, spec, root)
        spec["time_anchor"] = engine._run_anchor_iso
        spec["horizon"] = engine._target_time_iso
        write_json(run_dir / "zenith_run.json", spec)
        with contextlib.redirect_stdout(sys.stderr):
            engine.run(spec["target"])
    return status(root, run_id)


def resume(root: Path, run_id: str) -> dict:
    root = Path(root).resolve()
    run_dir = runs_root(root) / safe_run_id(run_id)
    if not (run_dir / "zenith_run.json").exists():
        raise ValueError("run has no Zenith execution manifest")
    with run_lock(run_dir):
        spec = json.loads((run_dir / "zenith_run.json").read_text())
        _check_frozen_graph(root, spec)
        if spec.get("task_profile") == "financial_investigator_v1" and status(root,run_id)["failed_nodes"]:
            raise ValueError("investigator failed attempt is terminal; no automatic resampling through resume")
        if spec.get("feed_source"):
            forward_preflight(root, Path(spec["feed_source"]), stamp(spec["time_anchor"]))
        engine = _engine(root, run_dir, spec, resume=True)
        with contextlib.redirect_stdout(sys.stderr):
            engine.run(spec["target"])
    return status(root, run_id)


def import_response(root: Path, *, packet_path: Path, response_path: Path, model: str | None = None) -> dict:
    """Import raw response text or an identity-bound record, then resume the original engine."""
    root = Path(root).resolve()
    packet_path = Path(packet_path).resolve()
    packet = json.loads(packet_path.read_text())
    verify_packet(packet)
    run_id = safe_run_id(packet["run_id"])
    run_dir = runs_root(root) / run_id
    expected = run_dir / "handoff" / "requests" / (packet["packet_id"] + ".json")
    if packet_path != expected.resolve():
        raise ValueError("packet must be the original request in this run's handoff directory")
    with run_lock(run_dir):
        spec = json.loads((run_dir / "zenith_run.json").read_text())
        if spec["provider"] != "agent" or packet["node_id"] not in spec["scope"]:
            raise ValueError("packet does not belong to this agent mission")
        if spec.get("task_profile") == "financial_investigator_v1" and status(root,run_id)["failed_nodes"]:
            raise ValueError("investigator failed attempt is terminal; preserve rejected output")
        _check_frozen_graph(root, spec)
        if spec.get("feed_source"):
            forward_preflight(root, Path(spec["feed_source"]), stamp(spec["time_anchor"]))
        artifact_path = run_dir / "artifacts" / (packet["node_id"] + ".json")
        destination = run_dir / "handoff" / "responses" / (packet["packet_id"] + ".json")
        if artifact_path.exists() and json.loads(artifact_path.read_text()).get("status") in ("success", "loaded") and not destination.exists():
            raise ValueError("node already completed; this packet is obsolete")
        text = Path(response_path).read_text(encoding="utf-8")
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, dict) and decoded.get("schema") == "zenith_agent_response_v1":
            response = decoded
        else:
            response = {"schema": "zenith_agent_response_v1", "packet_id": packet["packet_id"],
                        "run_id": run_id, "node_id": packet["node_id"], "prompt_sha256": packet["prompt_sha256"],
                        "response_text": text, "requested_model": model, "actual_model": model,
                        "usage": None, "cost": None, "imported_at": datetime.now(timezone.utc).isoformat()}
        verify_response(packet, response)
        destination = run_dir / "handoff" / "responses" / (packet["packet_id"] + ".json")
        if destination.exists():
            existing = json.loads(destination.read_text())
            if existing["response_text"] != response["response_text"]:
                validation_path = run_dir / "handoff" / "validation" / (packet["packet_id"] + ".json")
                if not validation_path.exists() or json.loads(validation_path.read_text()).get("engine_accepted"):
                    raise ValueError("accepted or unvalidated response cannot be replaced")
                # A correction remains bound to the same exact prompt; retain the rejected version.
                archive = run_dir / "handoff" / "rejected_responses" / packet["packet_id"] / (text_digest(existing["response_text"]) + ".json")
                write_json(archive, {**existing, "engine_validation": json.loads(validation_path.read_text())})
                write_json(destination, response)
        else:
            write_json(destination, response)
        engine = _engine(root, run_dir, spec, resume=True)
        with contextlib.redirect_stdout(sys.stderr):
            engine.run(spec["target"])
        artifact = run_dir / "artifacts" / (packet["node_id"] + ".json")
        accepted = artifact.exists() and json.loads(artifact.read_text()).get("status") in ("success", "loaded")
        envelope = json.loads(artifact.read_text()) if artifact.exists() else {}
        validation = {"schema": "zenith_import_validation_v1", "packet_id": packet["packet_id"],
                      "run_id": run_id, "node_id": packet["node_id"], "engine_accepted": accepted,
                      "response_sha256": text_digest(response["response_text"]),
                      "engine_errors": envelope.get("metadata", {}).get("validation_errors", []),
                      "engine_error": envelope.get("metadata", {}).get("error")}
        write_json(run_dir / "handoff" / "validation" / (packet["packet_id"] + ".json"), validation)
    return {"import": validation, "run": status(root, run_id)}
