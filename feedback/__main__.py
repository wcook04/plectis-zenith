"""Local forecast admission, exact-horizon scoring and proposed skill feedback."""
import argparse
import json
from pathlib import Path

from . import engine


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    admission = commands.add_parser("register", help="admit validated forward Lab CP2 with locked provenance")
    admission.add_argument("--store", type=Path, required=True)
    admission.add_argument("--subject-run", type=Path, required=True)
    admission.add_argument("--policy", type=Path, required=True)
    admission.add_argument("--horizon-id", required=True)
    admission.add_argument("--root", type=Path, default=engine.ROOT)
    resolve = commands.add_parser("score", help="measure matured exact-horizon observations")
    resolve.add_argument("--store", type=Path, required=True)
    resolve.add_argument("--truth", type=Path, required=True)
    resolve.add_argument("--as-of", required=True)
    for name in ("summary", "propose"):
        sub = commands.add_parser(name)
        sub.add_argument("--store", type=Path, required=True)
        sub.add_argument("--as-of", required=True)
        sub.add_argument("--window-days", type=int, default=90 if name == "propose" else 30)
        if name == "propose":
            sub.add_argument("--minimum-issue-times", type=int, default=20)
            sub.add_argument("--minimum-failure-issues", type=int, default=3)
            sub.add_argument("--bucket-days", type=int, default=7)
    demo = commands.add_parser("demo", help="create an offline synthetic 20-issue fixture demonstration")
    demo.add_argument("--store", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "register":
            result = engine.register(args.store, args.subject_run, args.policy, args.horizon_id, root=args.root)
        elif args.command == "score":
            result = engine.score(args.store, args.truth, args.as_of)
        elif args.command == "summary":
            result = engine.summary(args.store, args.as_of, window_days=args.window_days)
        elif args.command == "propose":
            result = engine.propose(args.store, args.as_of, window_days=args.window_days,
                                    minimum_issue_times=args.minimum_issue_times,
                                    minimum_failure_issues=args.minimum_failure_issues, bucket_days=args.bucket_days)
        else:
            from .demo import run
            result = run(args.store)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, TypeError, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
