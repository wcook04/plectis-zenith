---
name: zenith-lab-oracle-evolve
description: Operate the repo-local Zenith feed, Lab and paired Oracle graph through native plans, contracts, captured responses and agent handoffs; review Evolve proposals without automatically promoting live instructions or dossiers.
compatibility: Python 3.11 or newer; run commands from repository root. Use --root PATH before the command to select configured state.
---

# Zenith Lab → Oracle → Evolve operation

Historical adapters must preserve opaque issuer IDs (including leading zeros),
quote currency/basis and separate observation/availability clocks. Daily and
matchoff calendars belong to the source. Text used to explain an outcome must
not extend beyond that outcome's timestamp, even when its feed is available
later. Keep rebased wealth context separate from raw quote targets. The richer
native A-share adapter is documented in `docs/traderharness-daily.md`.

Start with `AGENTS.md` and `docs/skills.md`. Read the actual mission and
artifact contracts selected by the CLI. Disk receipts determine whether a
run completed; a prepared packet is pending work.
`zenith/runtime.py` wraps the original `system/core/engine.py` and
`system/core/governance.py` topology validation; `zenith/providers.py`
verifies packet and response identity. Read
`codex/doctrine/missions/{lab,oracle,evolve}.md`,
`codex/doctrine/flows/temporal_contract.md`, and the selected files under
`codex/substrate/contracts/` when reasoning about a mission's semantics.
`system/lib/schema_validator.py` owns CP1/CP2, Oracle quartet and evidence-ID
checks called by the engine. `zenith validate` checks topology; it is not a
substitute for those output validators or temporal evidence.

```sh
python -m zenith missions
python -m zenith validate
python -m zenith plan feeds
python -m zenith plan lab
python -m zenith plan oracle
python -m zenith plan refinement
python -m zenith inspect <node-id-from-plan>
```

Use `python -m zenith --help` and the selected command's `--help` for exact
required inputs. Global `--root PATH` goes before the command. Run IDs and
sources below are explicit operator-selected inputs, not default examples
of available market data.

For agent handoff, prepare Lab using a validated feed run and declared time
boundary:

```sh
python -m zenith prepare lab --run-id <id> --feed-source <source-run> --time-anchor <ISO-time> --horizon <ISO-time>
python -m zenith status <id>
```

Open the packet emitted under that run's `handoff/` directory. Answer only
from its admissible inputs and selected contracts. Preserve evidence IDs,
missingness and uncertainty. Import the response with truthful model identity
and resume:

```sh
python -m zenith import-response --packet <packet-path> --response <response-path> --model <model-name>
python -m zenith resume <id>
python -m zenith status <id>
```

Captured-response replay uses `python -m zenith run lab --run-id <id>
--feed-source <source-run> --provider captured --responses <responses-file>`;
read its help for time inputs. Never fabricate a captured provider response.

Oracle prepare/run takes an explicit `--subject-run <path> --truth-run
<path>` pair; use its command help before execution. Lab must not access
later truth. Keep feed readiness distinct from model error, and stop learning
from a BLOCKED subject/truth comparison. Inspect durable quartet/critique
outputs before making Evolve proposals.

Evolve proposals are review artifacts. Confirm the current CLI exposes an
Evolve operation before attempting execution; if it does not, report that
runtime boundary instead of inventing a command or invoking a private
checkout's tools. No successful experiment or critique automatically changes
live prompts, dossiers, doctrine or deployment state. Scientific comparisons
use the separately governed `zenith-scientific-experiments` skill.


For historical daily work, prefer `zenith daily init/next/review` described in
`docs/daily-replay.md`. This wraps the same native missions and original Evolve
packet, not a second reasoner. Read all bound sources before reviewing a candidate;
exact quotations and schema acceptance do not certify its reasoning. Explicit
no-change is valid. Preserve prior skills when replacing an addon, retain rejected
attempts, and test accepted development changes on later episodes. Programme
identity freezes authored graph/contracts/configuration as well as Python code.

For repeated generations, use `daily matchoff/retain` and `docs/generations.md`.
Trying a reviewed successor on the next development day is not competitive
selection. Require complete matched native outcomes before retaining a version;
carry the selection with `daily init --retention`, including its final truth
cutoff. A detached policy file loses that evidence chronology. Do not reuse
historical pending runs after changing their frozen implementation. InvestorBench
and FNSPID source adapters have different clock precision; retain those limits
and never turn excluded filings or unavailable feeds into factual evidence.

Use the explicit native `ABSTAIN` branch when no supported forward thesis exists;
never manufacture a forecast to satisfy an old example. Oracle may classify a
cause as `UNRESOLVED` and report evidence-bound `NO_FINDINGS`; Evolve may retain
`no_change`. These are meaningful decisions, not performance wins. Cohorts
count abstention as missing coverage and retain it without resampling. If a
contract change is needed during a pilot, preserve its source-bound attempt and
start a new programme. Disclose any exact response reuse as replay rather than
independent reasoning or unseen performance evidence. See `docs/abstention.md`.

For a predictive hypothesis without an identified cause, use the explicit native
EMPIRICAL branch in `docs/empirical-forecasts.md`, not a fabricated causal story
or an epsilon directional call. The initial supported rule is a price-history
control within the full graph. Freeze its inputs, parameters and target set in
CP1; independently checked target arithmetic and Oracle's no-refit boundary
remain binding. Distinguish interface repairs from a learned policy improvement.

For evidence-conditioned numerical beliefs without causal identification, use
`docs/judgmental-forecasts.md`: the native JUDGMENTAL branch freezes q10/q50/q90
simple-return quantiles at CP1. q50 is a median, not a mean; an exact zero median
is not a no-call or a point mass. Preserve the whole object through Director and
Oracle. Evolve receives the original quantiles and deterministic pinball loss.
Do not judge uncertainty by interval coverage alone or treat one covered event
as calibration. Compare the frozen judgment with earlier-price controls before
claiming that text reasoning helped; do not change the cohort objective silently.
