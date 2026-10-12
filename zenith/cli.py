"""Command-line entry into the actual Zenith nodes, contracts and engine."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from . import runtime


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--root", type=Path, default=runtime.DEFAULT_ROOT, help="standalone substrate root")
    commands = cli.add_subparsers(dest="command", required=True)
    daily = commands.add_parser("daily", help="continue historical days through full Lab, Oracle and reviewed Evolve")
    daily_commands = daily.add_subparsers(dest="daily_command", required=True)
    init = daily_commands.add_parser("init", help="freeze daily snapshots and a baseline; no inference")
    init.add_argument("--work-dir", type=Path, required=True)
    init.add_argument("--dataset", type=Path, default=runtime.DEFAULT_ROOT / "work/datasets/fnspid-aa")
    init.add_argument("--start", required=True, help="first forecast session, YYYY-MM-DD")
    init.add_argument("--end", required=True, help="last forecast session; the next session supplies its truth")
    init.add_argument("--policy", type=Path, help="initial frozen native reasoning policy")
    init.add_argument("--retention", type=Path, help="verified matchoff retention receipt; enforces its evidence cutoff")
    for name in ("next", "review"):
        step = daily_commands.add_parser(name)
        step.add_argument("--work-dir", type=Path, required=True)
        if name == "review":
            step.add_argument("--response", type=Path, required=True)
            step.add_argument("--reviewer", required=True, help="disclosed reviewing agent or human identity")
    matchoff = daily_commands.add_parser("matchoff", help="freeze matched incumbent/challenger native cohort; no inference")
    matchoff.add_argument("--work-dir", type=Path, required=True)
    matchoff.add_argument("--episode", type=int, required=True)
    matchoff.add_argument("--dataset", type=Path, required=True)
    matchoff.add_argument("--start", required=True)
    matchoff.add_argument("--end", required=True)
    matchoff.add_argument("--output", type=Path, required=True)
    matchoff.add_argument("--model", required=True)
    matchoff.add_argument("--minimum-improvement", type=float, required=True, help="predeclared absolute reduction in mean relative target-price error")
    retain = daily_commands.add_parser("retain", help="record reviewed winner from a complete native development matchoff")
    retain.add_argument("--matchoff", type=Path, required=True)
    retain.add_argument("--reviewer", required=True)
    commands.add_parser("missions", help="list authored mission groups")
    serve = commands.add_parser("serve", help="serve reviewed graph metadata through a read-only local HTTP API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--allow-origin", action="append", default=[], help="exact frontend origin allowed by CORS; repeatable")
    provider = commands.add_parser("provider", help="own-key metadata-only setup checks")
    provider.add_argument("provider_command", choices=("doctor", "models"))
    provider.add_argument("--provider", choices=("openrouter_free", "nvidia_nim"), default="openrouter_free")
    provider.add_argument("--env-file", type=Path, help="explicit local dotenv file; process environment takes precedence")
    provider.add_argument("--offline", action="store_true", help="report configuration without network access")
    provider.add_argument("--check-key", action="store_true", help="explicit authenticated official key-status check; no inference")
    recovery = commands.add_parser("budget-recover", help="explicitly account for a reserved HTTP 429 failure without resending it")
    recovery.add_argument("--budget-dir", type=Path, required=True)
    recovery.add_argument("--evidence", type=Path, required=True, help="authorization and exact pre-recovery ledger/call hashes")
    inspect = commands.add_parser("inspect", help="inspect a hydrated authored node")
    inspect.add_argument("node")
    commands.add_parser("validate", help="validate the authored graph offline")
    plan = commands.add_parser("plan", help="show actual engine mission scope and waves offline")
    plan.add_argument("mission", choices=runtime.MISSION_TARGETS)
    plan.add_argument("--target")
    plan.add_argument("--graph-variant", type=Path, help="frozen topology variant JSON")
    for name in ("run", "prepare"):
        run = commands.add_parser(name, help="execute the real graph" if name == "run" else "prepare durable agent packets through the real engine")
        run.add_argument("mission", choices=("lab", "oracle", "feeds"))
        run.add_argument("--run-id", required=True)
        run.add_argument("--target")
        run.add_argument("--feed-source", help="recorded feed run id or directory; required for Lab")
        run.add_argument("--subject-run", help="Oracle subject Lab run")
        run.add_argument("--truth-run", help="Oracle later truth run")
        run.add_argument("--horizon", help="next_us_close, 24h, 48h, or timezone-aware ISO target")
        run.add_argument("--time-anchor", help="timezone-aware prediction anchor")
        run.add_argument("--policy", help="frozen reasoning policy JSON for this variant run")
        run.add_argument("--graph-variant", help="frozen topology variant JSON")
        run.add_argument("--context-profile", choices=("original", "compact_feeds"), default="original", help="explicit feed input projection, frozen for this run")
        if name == "run":
            run.add_argument("--provider", choices=("agent", "captured", "openrouter_free", "openrouter_budgeted", "nvidia_nim"), default="agent")
            run.add_argument("--responses", help="prompt-bound captured JSON responses")
            run.add_argument("--model", help="model ID; nvidia_nim requires an explicit selection")
            run.add_argument("--env-file", type=Path, help="explicit local dotenv file")
            run.add_argument("--max-cost-usd", help="explicit shared paid batch cap, at most 5 USD")
            run.add_argument("--max-calls", type=int, help="maximum attempted calls across the shared paid batch")
            run.add_argument("--max-output-tokens", type=int, default=4096, help="paid response token cap")
            run.add_argument("--budget-dir", type=Path, help="one shared ledger directory for the entire paid batch")
            run.add_argument("--provider-slug", help="exact OpenRouter endpoint tag, frozen for this paid run")
    resume = commands.add_parser("resume", help="resume from durable engine artifacts and handoff manifest")
    resume.add_argument("run_id")
    status = commands.add_parser("status", help="inspect engine outcome and pending packets")
    status.add_argument("run_id")
    import_response = commands.add_parser("import-response", help="import a packet-bound response through original validation and resume")
    import_response.add_argument("--packet", type=Path, required=True)
    import_response.add_argument("--response", type=Path, required=True)
    import_response.add_argument("--model", help="disclosed author/model identity; unavailable if omitted")
    return cli


def dispatch(args) -> dict:
    root = args.root.resolve()
    if args.command == "daily":
        from . import daily
        if args.daily_command in {"matchoff", "retain"}:
            from research import daily_matchoff
            if args.daily_command == "retain":
                return daily_matchoff.retain(root, args.matchoff, args.reviewer)
            return daily_matchoff.freeze(root, args.work_dir, args.episode, args.dataset, args.start, args.end,
                                         args.output, args.model, args.minimum_improvement)
        if args.daily_command == "init":
            return daily.initialize(root, args.work_dir, args.dataset, args.start, args.end, args.policy, args.retention)
        return daily.advance(root, args.work_dir, getattr(args, "response", None), getattr(args, "reviewer", None))
    if args.command == "serve":
        from .api import serve
        return serve(root, args.host, args.port, args.allow_origin)
    if args.command == "provider":
        from .provider_setup import check
        return check(provider=args.provider, env_file=args.env_file, offline=args.offline, check_key=args.check_key)
    if args.command == "budget-recover":
        from .budgeted import recover_budget
        return recover_budget(args.budget_dir, json.loads(args.evidence.read_text()))
    if args.command == "missions":
        graph = runtime.load_graph(root)
        groups = {}
        for node in graph.values():
            groups.setdefault(node.group, []).append(node.id)
        return {"schema": "zenith_missions_v1", "node_count": len(graph),
                "missions": [{"id": key, "node_count": len(nodes), "nodes": sorted(nodes)} for key, nodes in sorted(groups.items())]}
    if args.command == "inspect":
        graph = runtime.load_graph(root)
        if args.node not in graph:
            raise ValueError("unknown node")
        node = graph[args.node]
        return {"schema": "zenith_node_inspection_v1", "id": node.id, "group": node.group,
                "type": node.type.value, "lane": node.lane, "platform": node.platform,
                "dependencies": list(node.dependencies), "output_schema": node.output_schema,
                "execution": node.execution, "instruction": node.instruction, "config": node.config}
    if args.command == "validate":
        return runtime.validate(root)
    if args.command == "plan":
        return runtime.plan(root, args.mission, args.target,
                            json.loads(args.graph_variant.read_text()) if args.graph_variant else None)
    if args.command in ("run", "prepare"):
        if getattr(args, "env_file", None):
            from system.lib.openrouter_free_runtime import load_env_file
            load_env_file(args.env_file)
        return runtime.start(root, mission=args.mission, run_id=args.run_id, target=args.target,
                             provider=getattr(args, "provider", "agent"), responses=getattr(args, "responses", None),
                             model=getattr(args, "model", None), feed_source=args.feed_source,
                             subject_run=args.subject_run, truth_run=args.truth_run,
                             horizon=args.horizon, time_anchor=args.time_anchor, policy=args.policy, graph_variant=args.graph_variant, context_profile=args.context_profile,
                             max_cost_usd=getattr(args, "max_cost_usd", None), max_calls=getattr(args, "max_calls", None),
                             max_output_tokens=getattr(args, "max_output_tokens", 4096), budget_dir=getattr(args, "budget_dir", None),
                             provider_slug=getattr(args, "provider_slug", None))
    if args.command == "resume":
        return runtime.resume(root, args.run_id)
    if args.command == "status":
        return runtime.status(root, args.run_id)
    if args.command == "import-response":
        return runtime.import_response(root, packet_path=args.packet, response_path=args.response, model=args.model)
    raise ValueError("unknown command")


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        result = dispatch(args)
    except (ValueError, KeyError, OSError, RuntimeError) as exc:
        from system.lib.openrouter_free_runtime import safe_error
        print(json.dumps({"status": "rejected", "error": safe_error(exc)}))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    if result.get("ok") is False or result.get("status") == "failed" or result.get("catalogue_status") == "error":
        return 1
    if args.command == "import-response" and not result["import"]["engine_accepted"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
