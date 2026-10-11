"""The local, offline scientific experiment CLI."""
import argparse
import json
from pathlib import Path

from research.engine import finalize, freeze, recover, status, trial


def main(argv=None):
    parser = argparse.ArgumentParser(description='Frozen Zenith replay experiments')
    commands = parser.add_subparsers(dest='command', required=True)
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
    args = parser.parse_args(argv)
    try:
        if args.command.startswith('cohort-'):
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
