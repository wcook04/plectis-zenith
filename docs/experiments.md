# Frozen Zenith experiments

`research` wraps the extracted `tools.finance.historical_replay` evaluator. It admits forecast cards, resolves their precisely bound events from a local price tape, and computes the evaluator's Brier score. Candidates emit probabilities; they cannot submit a score or change targets, membership, horizon, benchmark, event keys, coverage, or the acceptance rule through the candidate interface.

The probability adapter evaluates mappings over frozen upstream forecasts. Its intervention tags record provenance and do not execute a graph. The separate cohort adapter below consumes complete native graph runs and their actual CP2 forecasts. Neither adapter learns model weights or silently changes live skills.

## Reproduce the offline experiment

Run from the repository root, with Python 3.11 or later:

```sh
python3 -m research freeze --spec examples/experiments/offline/spec.json --study work/research-demo
python3 -m research trial --study work/research-demo --candidate examples/experiments/offline/baseline.py --key baseline --hypothesis 'Establish the identity mapping reference' --change none --model offline-deterministic
python3 -m research trial --study work/research-demo --candidate examples/experiments/offline/shrink.py --key shrink-07 --hypothesis 'Shrink reduces overconfidence' --change 'Fixed probability shrink factor 0.7' --model offline-deterministic
python3 -m research status --study work/research-demo
python3 -m research final --study work/research-demo --key final-1
```

The invented fixture has four development weeks, one purged week, and two final weeks. The real evaluator computes baseline Brier 0.41 and shrink Brier 0.3284. This demonstrates executable admission, truth resolution, and experiment control. These synthetic numbers say nothing about market prediction, statistical significance, profit, or an investment strategy.

A frozen study cannot be overwritten. After editing evaluator or harness source, freeze a new study in a new directory. Frozen source hashes deliberately reject changing the evaluator halfway through an experiment.

## Spec and candidate contract

`examples/experiments/offline/spec.json` is the complete minimal specification. Paths resolve relative to its directory. Required fields are `schema`, `calculator_artifacts`, `price_history`, `truth_as_of`, `holdout_start`, `horizon_days`, `embargo_days`, `max_trials`, `timeout_seconds`, `minimum_improvement`, `minimum_resolved`, and `benchmark`. Unknown fields are rejected. The only optional field is:

```json
{
  "intervention": {
    "parameter_kind": "node_skill",
    "node_ids": ["oracle"],
    "incoming_edge_ids": ["calculator-to-oracle"],
    "source_artifacts": ["oracle-skill.md", "upstream-run-receipt.json"]
  }
}
```

`parameter_kind` accepts `node_skill`, `context_policy`, `topology`, `model`, or `probability_mapping`. Source artifacts are copied and content hashed along with forecast artifacts and price truth. Node and edge ids are provenance labels for the upstream intervention. The default intervention is probability mapping with empty upstream links.

A candidate is one Python source file. It reads a JSON list on standard input containing only `forecast_id`, `subject_as_of`, `direction`, and the frozen baseline `probability`. It writes a JSON list of probabilities in the same order. Numbers must be finite and within [0,1]. Changing the number of predictions fails the attempt. Examples demonstrate the full interface.

Only development events enter candidate input during trials. Provider prose, raw prompts, arbitrary extra calculator fields, price truth, and holdout rows are excluded from that projection. The evaluator receives the original frozen contracts plus candidate probabilities. Every selected event must be admitted and resolved, and comparison event keys must match the measured baseline. Missing truth and changed support fail rather than producing an opportunistic improvement.

## Frozen chronology and decision rule

Freeze runs before loading any candidate. It records content hashes for copied input artifacts and the evaluator/harness sources and Python runtime version, forecast ids, declared artifact availability, subject times, event ends, calendar-week clusters, split membership, horizon, embargo, truth cutoff, benchmark, trial budget, timeout, and objective.

A forecast's `identity.available_at` must be no later than its subject time. If the source lacks `available_at`, the adapter explicitly assumes the declared `as_of`; it cannot independently certify upstream historical availability. Events must mature by the frozen truth cutoff. All events in a calendar week stay together. A boundary splitting a week is rejected. Entire development week groups are purged when an event end plus embargo crosses the holdout boundary.

Run the identity mapping first. Subsequent candidates are kept only if native development mean Brier is lower than the current champion by more than the predeclared `minimum_improvement`, on identical common support. Ties are discarded. Failures count against `max_trials`. There is no post-hoc metric, threshold, exclusion, or favorable-subset selection.

`keep` creates a `promotion-proposal.json` with live mutation permission false. It does not alter Zenith dossiers, variant registry, prompts, probability mappings, or live skills. The existing replay envelope also keeps optimizer and calculator mutation permission false.

## Attempts, concurrency, and interruption

`trials.sqlite3` is the durable reservation and result authority. Atomic SQLite transactions reserve each attempt before candidate/evaluator execution, enforce the development budget, compare completed candidates against the current champion, and consume the one final evaluation. Different attempts can execute concurrently; champion updates serialize at completion, not reservation order. A stable `--key` returns the same reservation/result without consuming another attempt; reusing it with changed candidate bytes or declared provenance is an error.

Each `attempts/<id>/` retains start receipt, captured source and prompt bytes, candidate input/output, worker logs, baseline and candidate native envelopes, and final receipt. Hypothesis, proposed change, declared model, prompt hash, source commit, candidate hash, intervention links, and frozen spec hash are recorded. The model field is supplied provenance, not a verified provider response identity. Offline examples use local Python and make no LLM calls.

Crashes, invalid output, missing candidate files, mutated inputs or evaluator sources, and timeouts become error attempts. Process-group termination bounds the candidate/evaluator trial on supported POSIX systems. If the owning process disappears, `python3 -m research recover --study work/research-demo` closes its reservation as an interrupted error; it remains spent. Recovery refuses to interrupt a live owner. This local PID-based recovery is intended for a single workstation, not a distributed scheduler.

`final` uses the captured development champion and consumes the heldout budget before execution. A failed or interrupted final still spends the seal. Retrying the same key retrieves that attempt; a new key is refused. Reserving final also closes all further development trials. Final cannot start while development attempts remain running.

## Interpretation and trust

Trusted candidate code runs in a separate temporary directory with a strict input projection and no inherited application credentials. Python is **not sandboxed**: a malicious program can inspect local files or access the network. Keep heldout truth in an external isolated evaluation service if adversarial code or confidentiality is in scope. Content hashing detects ordinary drift; it is not a tamper-proof signature against someone who controls files and the SQLite ledger.

Historical LLM experiments may be contaminated by training data, remembered prices, or retrospective narratives. A frozen split cannot remove model-training contamination. Claim prospective prediction quality only from forecasts captured before truth with independently verified availability and provider identity. A synthetic replay or a modern LLM tested on old history does not establish that claim.

Calendar-week grouping prevents split leakage within a week; event outcomes can still be dependent across weeks, horizons, or assets. No confidence interval or significance claim is emitted by this small adapter. Selecting a champion across many development trials introduces selection bias. One final measurement reports historical error on the sealed support; it does not authorize repeated final tuning or establish investment performance.

## Sources and design transfer

The bounded edit/evaluate/keep-or-discard loop is inspired by Karpathy's [autoresearch README at commit 228791fb499afffb54b46200aca536f79142f117](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/README.md) and its [program instructions](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md). That project fixes its data/evaluator and training time, changes a bounded candidate, records every trial, and keeps improvements. Here the existing Zenith replay authority supplies the fixed evaluator. No autoresearch source is vendored: the inspected README states MIT, but the inspected tree has no standalone license file. See `third_party/skills/README.md` for the pinned prior-art record.

## Compare actual graph candidates

`research.cohort` binds admitted topology variants or reasoning policies to a fixed collection of native Lab runs. The entire native CP2 scope must complete, including provider receipts for every reasoning node. The objective comes from `feedback.engine`: relative target-price error, averaged first over each issue's declared targets and then over issues. No supplied score is accepted. Candidates can change node skills, incoming-context weights and budgets, or admitted topology; their output must retain exactly the fixed target/issue/horizon support.

This adapter is a **matured frozen cohort evaluation**. It requires every horizon to be at or before its fixed `truth_as_of` and copies the existing truth artifact. It can compare previously captured prospective runs or new historical graph replays; freezing this evaluation does not establish that their predictions were preregistered before truth. The daily `feedback` owner handles pending prospective observations and later maturity. Modern models replaying history may already know its outcomes.

Create a specification using schema `zenith_graph_cohort_v1`. Its exact fields are:

| Field | Contract |
| --- | --- |
| `issues` | Fixed list of issue records below; issue ids and times are unique |
| `candidates` | Fixed list of candidate records below, starting with `baseline` |
| `feedback_policy` | Native feedback policy JSON path |
| `truth_source`, `truth_as_of` | Existing exact dated truth JSON path and timezone-aware cutoff |
| `max_trials` | Maximum preregistered candidates, including baseline |
| `max_calls_per_run` | Audited provider-call ceiling per native run |
| `minimum_improvement` | Fixed decrease in the native relative-error objective |
| `embargo_days` | Nonnegative gap after the last development horizon before holdout issues |

Each issue has exactly `issue_id`, `feed_source`, `time_anchor`, `target_time`, `horizon_id`, `target_ids`, and `split`. `split` is `development` or `holdout`; a calendar week cannot span both. Horizon resolution uses the actual native engine. `target_ids` is a fixed nonempty list of unique uppercase symbols. Feed files and runtime context are copied and hashed; native manifests may refer to the original snapshot directory or its frozen copy only when all relative input paths and bytes match. Future feed evidence fails native forward admission.

Each candidate requires `candidate_id`, `hypothesis`, `change`, `source_commit`, `model`, `execution_kind`, `provider`, `graph_variant`, `reasoning_policy`, `context_profile`, and `prompt_sha256`. Its only optional field is `actual_model`, the fixed expected provider-reported model id; it defaults to the requested `model`. Use it when a concrete provider-reported name differs from the request identifier. Variant and policy fields are paths or null. The prompt hash and commit are declared proposal provenance; per-node execution prompt hashes remain in native receipts. Candidate ids are unique safe identifiers. Variant/policy payloads and full graph node hashes are frozen. Requested model declarations match across candidates; every supplied node receipt must match the identical frozen **actual** model expectation. An `openrouter/free` alias is insufficient when actual models differ. Agent-supplied model metadata is labeled as declared identity, captured replay metadata as replay identity, and API receipts as provider metadata; none is an independent identity attestation.

```sh
python -m research cohort-freeze --spec cohort-spec.json --study work/graph-study
python -m research cohort-next --study work/graph-study
# Run the returned native_argv through Zenith, or complete its agent packets.
# Captured providers additionally require their exact --responses source.
python -m research cohort-attach --study work/graph-study --candidate-id baseline --issue-id issue-0 --run work/runs/BASELINE_RUN
python -m research cohort-attach --study work/graph-study --candidate-id candidate --issue-id issue-0 --run work/runs/CANDIDATE_RUN
python -m research cohort-evaluate --study work/graph-study
# After all heldout runs and exact truth are available:
python -m research cohort-evaluate --study work/graph-study --final-key final-1
```

`cohort-next` returns argument arrays for missing native runs and attach operations, or native resume commands for pending runs. It makes no provider calls. Execution remains in Zenith. Call-budget checks happen at import, **not before spending**; do not treat them as a provider quota or spending limiter. Use the native provider's own keys and receipts. API call files count attempted calls, including failures; captured and agent runs count supplied responses.

Every preregistered candidate spends a trial slot before outputs are imported. Import errors, incomplete runs, and immutable successful-output hashes have separate durable receipts under `imports/`. Accepted runs are idempotent; their JSON output bytes cannot subsequently change. A pending manifest may accumulate results but cannot change its frozen identity. Native failures are errors; incomplete agent handoffs remain pending. Missing truth remains pending. A comparison with any missing issue, target, candidate, or observation returns no partial score: favorable subsets cannot win.

At least **20 distinct issue times** are required for a development candidate proposal. The number of calendar-week clusters is reported; that gate is not a significance test. Fixed loss improvement produces a proposal with `live_mutation_permission=false`. No dossier or skill is edited. For final evaluation, the best eligible development proposal is selected before opening heldout outcomes, and only it and the baseline are measured. The final key seals evaluation once, including when the result is pending, interrupted, or erroneous. Development comparisons and imports then close. Wait until heldout support is ready before deliberately spending that seal.

An executable twenty-issue fixture generates the complete native manifest/CP2/provider grammar and runs the consumer:

```sh
python -m examples.experiments.graph_cohort --destination /tmp/zenith-cohort-demo
```

It creates **synthetic output fixtures**; no reasoning node or model executes. Its invented target-price correction demonstrates the cohort consumer and 20-issue gate, not graph optimization or prediction skill. Real graph experiments use actual `zenith run/resume` outputs with distinct admitted policy/topology artifacts, as shown by the machine-readable commands. Freeze a new cohort after changing the evaluator, declared candidate set, truth, or membership; repeated historical development still introduces selection bias.

## From measured failures to one native candidate

`reflection-packet` reads a native `feedback propose` result file. It retains the
whole proposal, including successes, unresolved counts and source references;
it rejects mixed development/heldout membership instead of selecting favorable
rows. Source hashes and analysis/observation cutoffs are checked again when a
candidate is compiled. An agent reads that evidence and proposes one change.

```sh
python -m research reflection-packet \
  --proposal work/feedback/proposals/PROPOSAL_ID.json \
  --study work/graph-study --as-of 2026-10-11T15:00:00Z \
  --node lab_director \
  --output work/reflection.json
python -m research reflection-candidate \
  --packet work/reflection.json --edit proposed-edit.json \
  --study work/graph-study --source-commit YOUR_REVIEWED_SOURCE_COMMIT \
  --output work/proposed-candidate
```

These illustrative paths require actual existing evidence. The study must have
complete native attachments and an unconsumed final seal. The scope records its
development/heldout membership and hashes the study specification and attachment
state. Subsequent study-state changes require a fresh packet. Alternatively,
`--scope scope.json` accepts an explicit `zenith_reflection_scope_v1` object with
`as_of`, `development_run_ids` and `heldout_run_ids`. This is declared membership;
it does not prove that those observations were never used as heldout evidence.
Neither path is an OS boundary against another process reading local data.

The selected node defaults to `lab_director`. Its trace context contains up to
three failing and two successful distinct runs, selected deterministically by
issue time and forecast id. It includes node-output excerpts and, where present,
the actual handoff prompt, response and native import-validation binding. Fields
are capped at 2,048 characters and two exchanges per case, with source hashes,
sizes, omissions, missing evidence and truncation recorded. Compilation rechecks
the sources and excerpt contents. This is bounded search context; the complete
measurement evidence remains in the packet. It is not a statistically
representative sample or proof of causal responsibility.

The edit is small and explicit:

```json
{
  "node_id": "lab_director",
  "parameter": "skill_addon",
  "value": "Compare each target with the no-change baseline before finalizing it.",
  "hypothesis": "An explicit baseline comparison reduces target-price error on matched inputs.",
  "variant_id": "baseline-comparison"
}
```

This is an example hypothesis, not a learned rule or measured improvement.
Other supported parameters are `max_context_chars` and `incoming_weights`; the
latter requires one `edge_id`. Supply `--baseline-policy` and `--graph-variant`
when the measured runs used them. Every measured ancestor must match; the
compiler preserves the rest of the baseline policy and rejects effective no-ops.

The new directory contains `policy.json` and `candidate.json`. The first is
consumable by native Zenith and the cohort's `reasoning_policy` field. The second
records proposal/packet/policy hashes, hypothesis, exact change and review-only
status. With `--study`, it also emits `cohort-candidate.json`, an exact native
candidate row, and `cohort-review.json`, its separate review/provenance receipt.
The helper copies verified parent model/provider/context/graph settings; the
candidate id comes from the edit's `variant_id`. `--source-candidate-id` defaults
to `baseline`. The declared source commit is provenance, while frozen source
hashes remain the executable identity check. The helper requires a source-current
parent study; it cannot bypass changed evaluator or graph checks.

Existing outputs cannot be overwritten. No provider runs, study creation,
score or live promotion occurs here. Preregister the candidate in a **new** cohort
using the generated row and the usual fixed budget/support declarations. A frozen
study cannot gain a candidate after its results have been seen. Preserve parent
study/proposal receipts and failed trials across studies; repeated historical
search remains adaptive even when each individual study has its own final seal.
