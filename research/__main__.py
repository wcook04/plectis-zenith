"""Compare incumbent and candidate through the native graph."""
import argparse
import json
from pathlib import Path
from research import cohort
from research.engine import read_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('cohort-freeze', 'cohort-attach', 'cohort-evaluate', 'cohort-next'):
        sub = commands.add_parser(name)
        sub.add_argument('--study', type=Path, required=True)
        if name == 'cohort-freeze':
            sub.add_argument('--spec', type=Path, required=True)
        elif name == 'cohort-attach':
            sub.add_argument('--candidate-id', required=True)
            sub.add_argument('--issue-id', required=True)
            sub.add_argument('--run', type=Path, required=True)
        elif name == 'cohort-evaluate':
            sub.add_argument('--final-key')
    selection = commands.add_parser('selection-score')
    selection.add_argument('--input', type=Path, required=True)
    diagnosis = commands.add_parser('failure-windows', help='source-bound Oracle hypotheses across sliding windows')
    diagnosis.add_argument('--oracle-run', type=Path, action='append', required=True)
    diagnosis.add_argument('--widths', type=int, nargs='+', default=[1, 2, 5])
    diagnosis.add_argument('--stride', type=int, default=1)
    diagnosis.add_argument('--annotations', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'failure-windows':
            from research.failure_windows import diagnose
            annotations = read_json(args.annotations)['annotations'] if args.annotations else []
            result = diagnose(args.oracle_run, args.widths, args.stride, annotations)
        elif args.command == 'selection-score':
            from feedback.selection import score_panel
            result = score_panel(read_json(args.input))
        elif args.command == 'cohort-freeze':
            result = cohort.freeze(args.spec, args.study)
        elif args.command == 'cohort-attach':
            result = cohort.attach(args.study, candidate_id=args.candidate_id,
                                   issue_id=args.issue_id, run=args.run)
        elif args.command == 'cohort-evaluate':
            result = cohort.evaluate(args.study, final_key=args.final_key)
        else:
            result = cohort.next_actions(args.study)
    except (ValueError, OSError, KeyError, RuntimeError, TypeError, IndexError) as exc:
        print(json.dumps({'status': 'rejected', 'error': str(exc)}))
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
