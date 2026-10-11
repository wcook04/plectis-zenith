---
name: zenith-scientific-experiments
description: Run bounded, reproducible scientific comparisons of Zenith probability candidates through an immutable study spec, complete attempt ledger, validation selection and single-use untouched holdout. Use when improving a model or research method experimentally.
compatibility: Python standard library; repository-local research CLI. Read program.md before conducting trials.
---

# Zenith scientific experiments

Read `program.md`, `docs/skills.md`, the proposed experiment spec and the
native `research` command help. The source owners are
`research/engine.py` (`freeze`, `verify`, `trial`, `finalize`) and
`research/worker.py` (`evaluate`), which calls the actual
`tools/finance/historical_replay.py` evaluator. This is the active native workflow. The
reference-only Karpathy source pin is recorded in
`third_party/skills/import_manifest.json`; no GPU training dependency or
upstream autonomous shell loop is installed.

1. Freeze a falsifiable question, candidate interface, evidence/data cutoff,
   source hashes, chronological event groups, purge/embargo, metric/common
   support, budget, stop rule and validation/holdout split **before** trials.
   A change to the frozen contract starts a new study, not an in-place edit.
2. Establish the baseline. Then change one declared factor per trial; record
   the hypothesis and exact change, candidate identity/hash, requested/actual
   model identity where applicable, elapsed resources and outcome. Record
   failed and rejected attempts as well as successes. A syntax repair is a
   recorded attempt, not permission to erase a failure.
3. Select using validation evidence under the frozen evaluator. The candidate
   reads the permitted forecast input interface and emits probabilities; do
   not give it labels, final metrics, future evidence or a revised split.
4. Prefer a simpler candidate when the preregistered comparison supports it.
   Preserve the evidence and rejected alternative rather than resetting
   unrelated working files. Stop on the declared trial/resource budget or
   invalid inputs.
5. Freeze the selected candidate before the final command. Evaluate the
   untouched holdout once. Further tuning after final evidence requires a
   new study with a new untouched evaluation set; do not relabel the same
   holdout as validation.

Repository-local offline workflow:

```sh
python -m research freeze --spec examples/experiments/offline/spec.json --study work/research-demo
python -m research trial --study work/research-demo --candidate examples/experiments/offline/baseline.py --key baseline --hypothesis 'identity map baseline' --change 'none' --model offline-deterministic
python -m research status --study work/research-demo
python -m research final --study work/research-demo --key final-1
```

The runnable candidate intervention currently maps frozen forecast
probabilities. If a spec includes `node_skill`, `context_policy`, `topology`
or `model` intervention tags, those tags record provenance; they do not
cause this runner to execute or retrain the complete DAG. Review native
plan/packet traces separately for claims about graph or prompt changes.
Retain `promotion-proposal.json` as a review artifact when a trial improves.

Use a fresh study path/key for a fresh run. Read the CLI result and durable
ledger, not merely process exit status. The probability mapper receives JSON
rows containing `forecast_id`, `subject_as_of`, `direction` and `probability`,
then emits one finite probability in [0, 1] per input row. Candidate Python is
trusted local code, **not an OS sandbox**: the input projection and isolated
working directory do not prevent filesystem or network access. Inspect the
candidate before executing it. Run the repository tests after changing the
native evaluator or candidate contract.

Report the selected/rejected candidate, validation result, final result if
consumed, all-attempt count and remaining limitations. Improvement on this
fixed research score does not authorize automatic live prompt/dossier
promotion, a public deployment, or a trading performance claim.
