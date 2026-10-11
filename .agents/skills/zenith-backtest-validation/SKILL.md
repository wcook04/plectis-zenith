---
name: zenith-backtest-validation
description: Audit Zenith evaluation claims against frozen inputs, disclosed trials, chronological splits, baselines and missing checks. Use when comparing variants, reviewing backtest claims or deciding whether a historical result supports a stated conclusion.
compatibility: Repository-local Python commands; retained third-party programs are illustrative and disabled.
---

# Zenith evaluation and backtest validation

Read `docs/skills.md`, `benchmark/README.md`, and the native study/run
contracts before judging a result. The complete upstream method lives in
`third_party/skills/arthera/backtest-validation/`, pinned and attributed in
`third_party/skills/import_manifest.json`; its completion wording does not
override native policy.

1. Identify the actual claim and metric. The UCI benchmark reports forecast
   Brier error on a frozen historical split; it does not measure portfolio
   returns. Reproduce it with `python -m benchmark.run --output
   web/data/benchmark.json`; verify through `python -m unittest discover -s
   tests -v`. Preserve dataset/code hashes, baselines and exclusions.
2. Apply `zenith-point-in-time-research` before judging a result built from
   data joins. Keep time precision, vintage, calendar and corporate-action
   limitations explicit.
3. Require the actual trial ledger and frozen spec. Count all attempts,
   failures and rejected variants; unknown trial count is unknown selection
   risk. Never silently assume the upstream CLI default of one trial.
4. Compare the same eligible forecast IDs, evaluator, metric and cutoff.
   Chronological validation selects the candidate; an untouched holdout
   evaluates the frozen selection once. Repeated holdout inspection is not
   another validation trial. Preserve clustered/event-level comparisons,
   purges/embargo and the simple baseline.
5. State failed or unavailable checks with their effect on the conclusion.
   Candidate process success, schema validity and evidence of improvement
   are different outcomes. Do not turn WARN or exit code zero into an
   unconditional acceptance claim.

If the task actually simulates trading, additionally require declared
gross/net conventions, units/frequency, turnover, transaction and borrow
costs, execution assumptions, out-of-sample stability and uncertainty. These
checks are not implemented by the current Brier demonstration; do not invent
them or convert its scores into profits. Selection corrections must match
the disclosed search and assumptions.

Do not execute retained `validation_gauntlet.py` or add its unpinned
numpy/pandas dependencies in the native workflow. Its arbitrary JSON output
path, default trial count and PASS/WARN exit convention require separate
executor review. Use `zenith-scientific-experiments` for the actual native
trial workflow and record the strongest supported claim, including negative
findings, without automatic live prompt/dossier promotion.
