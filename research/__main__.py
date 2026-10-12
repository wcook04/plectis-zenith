"""The local, offline scientific experiment CLI."""
import argparse
import json
from pathlib import Path

from research.engine import finalize, freeze, recover, status, trial


def reflection_command(args):
    from research import reflection
    from research.engine import read_json
    from zenith import runtime

    output = args.output.resolve()
    if output.exists():
        raise ValueError('reflection output already exists; preserve the earlier attempt')
    if args.command == 'reflection-packet':
        if args.study:
            if not args.as_of:
                raise ValueError('--study requires --as-of')
            scope = reflection.scope_from_study(args.study, args.as_of)
        else:
            if args.as_of:
                raise ValueError('--scope already declares as_of; do not override it')
            scope = read_json(args.scope)
        options = {'source_root': args.source_root.resolve()} if args.source_root else {}
        result = reflection.build_packet(args.proposal, scope=scope, node_id=args.node, **options)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
        return {'state': 'reflection_ready', 'packet': str(output), 'live_mutation_permission': False}

    edit = read_json(args.edit)
    required = {'node_id', 'parameter', 'value', 'hypothesis', 'variant_id'}
    if not isinstance(edit, dict) or not required <= set(edit) or set(edit) - required - {'edge_id'}:
        raise ValueError('edit requires node_id, parameter, value, hypothesis, variant_id and optional edge_id')
    graph = runtime.load_graph(runtime.DEFAULT_ROOT, read_json(args.graph_variant) if args.graph_variant else None)
    packet = read_json(args.packet)
    result = reflection.compile_candidate(packet, graph=graph,
        baseline_policy=read_json(args.baseline_policy) if args.baseline_policy else None, **edit)
    fragment = None
    if args.study:
        if not args.source_commit:
            raise ValueError('--study requires a declared --source-commit for the new candidate')
        from research.reflection_cohort import candidate_fragment
        fragment = candidate_fragment(packet, result, study=args.study, policy_path=output / 'policy.json',
            candidate_id=edit['variant_id'], source_commit=args.source_commit,
            source_candidate_id=args.source_candidate_id)
    elif args.source_commit or args.source_candidate_id != 'baseline':
        raise ValueError('source candidate/commit metadata requires --study')
    # Reserve a fresh directory only after validating the complete proposal.
    output.mkdir(parents=True)
    for name, key in (('policy.json', 'reasoning_policy'), ('candidate.json', 'candidate')):
        with (output / name).open('x') as stream:
            json.dump(result[key], stream, indent=2, allow_nan=False)
            stream.write('\n')
    if fragment:
        for name, key in (('cohort-candidate.json', 'candidate'), ('cohort-review.json', 'review')):
            with (output / name).open('x') as stream:
                json.dump(fragment[key], stream, indent=2, allow_nan=False)
                stream.write('\n')
    return {'state': 'candidate_ready', 'reasoning_policy': str(output / 'policy.json'),
        'candidate': str(output / 'candidate.json'),
        'cohort_candidate': str(output / 'cohort-candidate.json') if fragment else None,
        'live_mutation_permission': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Frozen Zenith replay experiments')
    commands = parser.add_subparsers(dest='command', required=True)
    synthetic = commands.add_parser('synthetic-learning', help='run the constructed operator-learning example; no model calls')
    synthetic.add_argument('--output', type=Path, required=True, help='fresh directory; never overwrite a previous attempt')
    synthetic.add_argument('--seed', type=int, default=1729)
    synthetic.add_argument('--no-signal', action='store_true', help='negative control: labels contain noise only')
    selection = commands.add_parser('selection-score', help='descriptive fixed-universe scores; does not admit native cohorts')
    selection.add_argument('--input', type=Path, required=True, help='JSON array of issue cases with universe, selection, forecasts, fallback and truth')
    init = commands.add_parser('freeze', help='validate and freeze a new study before trials')
    init.add_argument('--spec', type=Path, required=True)
    init.add_argument('--study', type=Path, required=True)
    run = commands.add_parser('trial', help='reserve and execute one development attempt')
    run.add_argument('--study', type=Path, required=True)
    run.add_argument('--candidate', type=Path, required=True)
    run.add_argument('--key', required=True, help='stable idempotency key')
    run.add_argument('--hypothesis', required=True)
    run.add_argument('--change', required=True)
    run.add_argument('--model', default='offline-deterministic')
    run.add_argument('--prompt-file', type=Path)
    for name in ('status', 'recover', 'final'):
        sub = commands.add_parser(name)
        sub.add_argument('--study', type=Path, required=True)
        if name == 'final':
            sub.add_argument('--key', required=True)
    for name in ('cohort-freeze', 'cohort-attach', 'cohort-evaluate', 'cohort-next'):
        sub = commands.add_parser(name, help='preregister/import/compare actual native Lab CP2 runs')
        sub.add_argument('--study', type=Path, required=True)
        if name == 'cohort-freeze':
            sub.add_argument('--spec', type=Path, required=True)
        elif name == 'cohort-attach':
            sub.add_argument('--candidate-id', required=True)
            sub.add_argument('--issue-id', required=True)
            sub.add_argument('--run', type=Path, required=True)
        elif name == 'cohort-evaluate':
            sub.add_argument('--final-key', help='consume heldout evaluation once')
    packet = commands.add_parser('reflection-packet', help='freeze complete development feedback for an agent')
    packet.add_argument('--proposal', type=Path, required=True)
    scope = packet.add_mutually_exclusive_group(required=True)
    scope.add_argument('--scope', type=Path, help='explicit development/heldout membership JSON')
    scope.add_argument('--study', type=Path, help='derive membership from a frozen native cohort')
    packet.add_argument('--as-of', help='analysis cutoff when deriving scope from a cohort')
    packet.add_argument('--source-root', type=Path, help='root containing the proposal evidence files')
    packet.add_argument('--node', default='lab_director', help='node whose verified trace context to inspect')
    packet.add_argument('--output', type=Path, required=True)
    candidate = commands.add_parser('reflection-candidate', help='compile one reviewed node parameter change')
    candidate.add_argument('--packet', type=Path, required=True)
    candidate.add_argument('--edit', type=Path, required=True)
    candidate.add_argument('--baseline-policy', type=Path)
    candidate.add_argument('--graph-variant', type=Path)
    candidate.add_argument('--study', type=Path, help='verified parent cohort for a native candidate fragment')
    candidate.add_argument('--source-commit', help='declared source revision for the new candidate')
    candidate.add_argument('--source-candidate-id', default='baseline')
    candidate.add_argument('--output', type=Path, required=True, help='new directory for policy and provenance')
    args = parser.parse_args(argv)
    try:
        if args.command == 'synthetic-learning':
            from research.synthetic_learning import run as synthetic_run
            report = synthetic_run(args.output, seed=args.seed, signal=not args.no_signal)
            result = {k: report[k] for k in ('kind', 'boundary', 'decision', 'assessment', 'trial_count', 'model_calls')}
            result['report'] = str(args.output / 'report.json')
        elif args.command == 'selection-score':
            from feedback.selection import score_panel
            from research.engine import read_json
            result = score_panel(read_json(args.input))
        elif args.command.startswith('reflection-'):
            result = reflection_command(args)
        elif args.command.startswith('cohort-'):
            from research import cohort
            if args.command == 'cohort-freeze':
                result = cohort.freeze(args.spec, args.study)
            elif args.command == 'cohort-attach':
                result = cohort.attach(args.study, candidate_id=args.candidate_id, issue_id=args.issue_id, run=args.run)
            elif args.command == 'cohort-evaluate':
                result = cohort.evaluate(args.study, final_key=args.final_key)
            else:
                result = cohort.next_actions(args.study)
        elif args.command == 'freeze':
            result = freeze(args.spec, args.study)
        elif args.command == 'trial':
            prompt, input_error = b'', None
            if args.prompt_file:
                try:
                    prompt = args.prompt_file.read_bytes()
                except OSError as exc:
                    input_error = f'prompt file unavailable: {exc}'
            result = trial(args.study, args.candidate, key=args.key, hypothesis=args.hypothesis,
                change=args.change, model=args.model, prompt=prompt, input_error=input_error)
        elif args.command == 'final':
            result = finalize(args.study, key=args.key)
        else:
            result = {'status': status, 'recover': recover}[args.command](args.study)
        print(json.dumps(result, indent=2))
        return 1 if result.get('state') == 'error' else 0
    except (ValueError, OSError) as exc:
        parser.exit(2, f'error: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
