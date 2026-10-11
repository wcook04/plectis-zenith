---
name: zenith-scientific-experiments
description: Improve Zenith through source-bound failure reflection, one declared node-policy change, and frozen comparisons of actual graph outputs. Retain all attempts and keep development selection separate from the final assessment.
compatibility: Python standard library; repository-local research CLI. Read program.md before conducting trials.
---

# Zenith scientific experiments

Read `program.md`, `docs/skills.md`, the proposed experiment spec and the
native `research` command help. Choose the owner for the actual hypothesis:

- `research/ashare_study.py` owns the five-session TraderHarness forecast
  experiment. Read `docs/ashare-study.md`. `compile`, `plan` and `report` are
  offline; execution remains held until an explicit hash-bound release uses
  one immutable shared budget and exact provider tag. Keep stock wealth labels
  distinct from executable portfolio returns. Outcome and hindsight teachers
  receive identical forward traces; only subsequent reporting differs. Always
  reconstruct stage projections and selection from recorded responses before
  using them downstream. A self-hash alone is not response provenance.
- `research/trading_study.py` owns the experimental interpretation → forecast
  graph and bounded forecast-skill learning on executable next-session returns.
  Follow `docs/trading-study.md`; rich inputs and training-only hindsight are
  separately projected. An unchanged selected policy aliases baseline results;
  only the declared repeat control draws another baseline sample.
- `research/cohort.py` compares newly executed native graph runs with fixed
  issue times, targets, horizons and model identities. Use this for node skills,
  incoming context, or graph changes.
- `research/reflection.py` turns a complete development feedback proposal into
  a hash-bound evidence packet and one validated node-policy candidate. It
  makes no provider calls and does not change the baseline.
- `research/engine.py` and `research/worker.py` compare probability mappings over
  frozen forecasts through `tools/finance/historical_replay.py`. Use this only
  when the mapping itself is the hypothesis.

The reference-only Karpathy source pin is recorded in
`third_party/skills/import_manifest.json`; no GPU training dependency or
upstream autonomous shell loop is installed.

1. Freeze a falsifiable question, candidate interface, evidence/data cutoff,
   source hashes, chronological event groups, purge/embargo, metric/common
   support, budget, stop rule and validation/holdout split **before** trials.
   A change to the frozen contract starts a new study, not an in-place edit.
   Before choosing that study, inspect actual records and count usable evidence
   per issue date and per split. Earliest/latest dates, file presence and a paper's
   release claim do not establish continuous source coverage. Preserve timestamp
   precision, source-body vintage, missing lanes and post-outcome fields. Let the
   verified information and executable decision determine the target and horizon.
   Qualify the final per-asset packet, including entity-link uncertainty, not
   only archive density. Calendar-day clipping must not silently shorten an
   exchange-session teacher interval. Test corporate-action entitlement at
   entry and historical features independently of future labels. Match identity
   cues across information treatments. Bound serialized Unicode context before
   a paid cohort, and include every scheduled control in the call plan.
   Before adding historical state, verify repeated missing comparisons in
   training inputs. Pair original dated claims, not asserted expectations;
   compound headlines require period/year scope within the relevant clause.
   Text baselines and retrieval must fit representations on eligible training
   evidence only. Keep column order explicit, bind numerical-library versions
   and normalize persisted receipts to JSON types before replay comparison.
   Do not rank memories by hindsight outcomes. Preserve assessment coverage
   when narrowing a declared budget profile and remove omitted-arm claims.
   Keep raw failure coverage separate from any preregistered fallback system.
   Cite borrowed mechanisms at their use, retaining source contradictions and
   target differences in the source manifest; a bibliography entry is not
   evidence that a method was reproduced.
2. Establish the baseline. Then change one declared factor per trial; record
   the hypothesis and exact change, candidate identity/hash, requested/actual
   model identity where applicable, elapsed resources and outcome. Record
   failed and rejected attempts as well as successes. A syntax repair is a
   recorded attempt, not permission to erase a failure.
3. Select using development evidence under the frozen evaluator. Native graph
   candidates produce new forecasts from frozen subject-side inputs; mapping
   candidates emit probabilities through the permitted forecast interface. Do
   not give either candidate labels, final metrics, future evidence or a revised
   split.
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

The example above uses the probability-mapping adapter. Its intervention tags
do not execute graph changes. For the graph itself, follow `cohort-freeze`,
`cohort-next`, native execution/import, `cohort-attach`, and `cohort-evaluate`
in `program.md`. Candidate skills must produce new forecasts on matched inputs;
renaming old output is not an experiment.

Before proposing a change, read the cited source cases, including successes,
and the selected node's implementation and context receipts. A node's ancestry
establishes participation, not causal blame. Keep the entire declared feedback
batch; reject mixed heldout evidence rather than selecting convenient failures.
Compile one parameter change, then preregister it in a new study. Do not add
candidates to a frozen study after seeing its results. Keep packet, exact diff,
source pins and unsuccessful attempts so another agent can audit the inference.

Use a fresh study path/key for a fresh run. Read the CLI result and durable
ledger, not merely process exit status. The probability mapper receives JSON
rows containing `forecast_id`, `subject_as_of`, `direction` and `probability`,
then emits one finite probability in [0, 1] per input row. Candidate Python is
trusted local code, **not an OS sandbox**: the input projection and isolated
working directory do not prevent filesystem or network access. Inspect the
candidate before executing it. Run the repository tests after changing the
native evaluator or candidate contract.

Run from this checkout with its own Python environment. When an external
repository launches validation, clear its inherited `PYTHONPATH` before
`python -m pytest tests`; a parent checkout's regular `system` package can
otherwise shadow this checkout's modules. Freeze runtime/evaluator source
edits for the duration of the suite: cohort tests deliberately reject source
changes between freeze and evaluation. Documentation edits remain independent.

Report the selected/rejected candidate, validation result, final result if
consumed, all-attempt count and remaining limitations. Improvement on this
fixed research score does not authorize automatic live prompt/dossier
promotion, a public deployment, or a trading performance claim.
