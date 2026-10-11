# Repo-local research skills

The active agent instructions live under `.agents/skills/`. Each folder has
discovery metadata and a `SKILL.md`; select a skill by the task and read it
before acting. They work from this standalone repository's installed Python
environment and require no global skill installation, private checkout or
GPU. Retained third-party programs add no active runtime dependencies.

| Skill | Use it for | Native owner |
| --- | --- | --- |
| [Zenith Lab/Oracle/Evolve](../.agents/skills/zenith-lab-oracle-evolve/SKILL.md) | Inspect contracts, prepare agent packets, import responses, resume and inspect paired runs | `python -m zenith` plans, contracts and run receipts |
| [Point-in-time research](../.agents/skills/zenith-point-in-time-research/SKILL.md) | Availability, vintage, parent lineage, leakage and execution-time review | Selected native node contracts and evidence; `benchmark.run.load_samples` for the fixed UCI demonstration |
| [Evaluation/backtest validation](../.agents/skills/zenith-backtest-validation/SKILL.md) | Frozen inputs, baselines, search disclosure, holdout and claim review | Native benchmark validators and scientific study ledger |
| [Scientific experiments](../.agents/skills/zenith-scientific-experiments/SKILL.md) | Baseline, one declared change per trial, complete attempt records and final evaluation | [`program.md`](../program.md), `python -m research` and its immutable study artifacts |
| [Forecast feedback](../.agents/skills/zenith-forecast-feedback/SKILL.md) | Exact-horizon price/direction accuracy, rolling summaries and large-batch review proposals | [`docs/forecast-feedback.md`](forecast-feedback.md), `python -m feedback` and its locked evidence store |

## Graph operation

Start with `python -m zenith missions`, `python -m zenith validate` and the
selected `plan`/`inspect` operation. A prepared packet waits for an answer;
it is not a completed provider run. Use the packet's actual input and output
contracts, import a response with its model identity, then resume and inspect
the durable status. Run `python -m zenith --help` for the current command
surface; place global `--root PATH` before the command.
The runtime wraps `system/core/engine.py`; plans and validation use the
original topology and scope policy. Packet/response hashes and identity
checks live in `zenith/providers.py`, while imported output acceptance is
decided by the original engine and its contracts. `plan refinement` can
inspect the Evolve topology even when the current run CLI lacks an Evolve
execution choice.

Lab reasoning uses only the declared subject information. Oracle takes an
explicit subject/truth pair. Keep absent feeds and failed comparisons
visible. Evolve produces learning proposals for review; automatic changes to
live instructions and dossiers are outside this skill. If an Evolve executor
is not exposed by the current CLI, do not invent one or invoke an external
private checkout.

## Scientific improvement

Freeze the spec and hashes before comparing candidates. It specifies the
data cutoff, event-group splits/embargo, permissible candidate interface,
common evaluation support, metric, budget and stop rule. Baseline and every
trial produce an attempt record, including crashes and rejected changes.
Validation selects a candidate; the untouched final partition is consumed
once after selection. After seeing final evidence, continued tuning needs
a new study and new untouched evidence.

The scientific-experiments skill contains an executable offline walkthrough
using `python -m research freeze`, `trial`, `status` and `final`. Read
`program.md` and the command help for exact artifact and candidate contracts.
[`research/engine.py`](../research/engine.py) owns study validation, frozen
hashes, attempts and final-use budgets; [`research/worker.py`](../research/worker.py)
calls the native `tools/finance/historical_replay.py` evaluator and checks
finite probabilities and identical resolved-event support. Candidate Python
is trusted local code, not an OS sandbox; inspect it before execution.
The runnable intervention is a probability mapper over frozen forecasts.
Optional node/edge/skill/context/topology/model tags record the scientific
change's provenance; they do not execute or retrain the complete DAG.
Improvement proposals remain review artifacts.
This is a native evaluation workflow, not an instruction to alter the
evaluation harness until a score improves. Brier error remains an error
metric; the historical demo does not measure investment returns.

[Karpathy's autoresearch](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md)
is methodological prior art: immutable evaluation/data preparation, a baseline,
a bounded per-attempt budget, attempt outcomes and a preference for simpler
improvements. Zenith adds preregistered study boundaries, full provenance and
a separate final holdout. It does not inherit the upstream indefinite GPU
loop, untracked TSV as sole evidence, or automatic Git resets. The inspected
README declares MIT, but no LICENSE or LICENSE.md was present at the pinned
commit, so no original source is copied; the provenance manifest records
this reference-only decision.

## Retained source and rights

Two complete [Arthera skill folders](https://github.com/artherahq/skills/tree/825040f3cc7eb4179a8ee86e0158d9828f427f7b/skills)
are retained unchanged under `third_party/skills/arthera/`: point-in-time
research and backtest validation. The upstream Apache-2.0 license is included.
[`import_manifest.json`](../third_party/skills/import_manifest.json) records
the immutable commit, every retained file's SHA-256, adapter ownership and
disabled upstream execution. Local adapters and retained originals have
separate homes; the originals are not an active marketplace installation.

The original programs were statically inspected and have not been run. They
require unpinned numpy/pandas; the backtest CLI can write a caller-selected
JSON path, defaults trial count to one, and exits successfully for WARN.
The PIT example reduces filing timestamps to dates and uses weekday offsets
without an exchange holiday calendar. These examples cannot establish strict
acceptance-time or executable-time fidelity. Optional execution requires a
separate reviewed, isolated, pinned executor with constrained artifact paths
and meaningful numerical validation. Current native operation uses none of
these third-party dependencies.

Strict PIT claims require observed timestamp precision/timezone, historical
version information and lineage. Execution-aware claims additionally need
a named exchange calendar and explicit lag. Keep missing evidence visible.
The UCI dataset does not contain exact publication timestamps or establish
vintage/corporate-action correctness; its valid checksum, label and split
checks do not remove those limitations. See [`benchmark/README.md`](../benchmark/README.md).

Before updating an import, review the new immutable source, retain license
and complete resources, recompute hashes and inspect each adapter against
the current native contracts. Do not overwrite originals with local edits
or fetch a moving branch as though it were the audited pin.
