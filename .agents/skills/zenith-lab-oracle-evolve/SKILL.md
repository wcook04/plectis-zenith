---
name: zenith-lab-oracle-evolve
description: Operate the repo-local Zenith feed, Lab and paired Oracle graph through native plans, contracts, captured responses and agent handoffs; review Evolve proposals without automatically promoting live instructions or dossiers.
compatibility: Python 3.11 or newer; run commands from repository root. Use --root PATH before the command to select configured state.
---

# Zenith Lab → Oracle → Evolve operation

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
