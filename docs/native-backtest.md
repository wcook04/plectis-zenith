# Compact native backtest

The experiment runs `global_stock_feed → lab_decide → lab_director`, with the
stock artifact also entering the director directly. The existing engine and
CP1/CP2 validators execute this explicit price-only replacement. The historical
28-node Lab remains available. No website or separate inference engine is needed.

The canonical prompt templates are `FORWARD_RULE`, `CP1_RULE` and `CP2_RULE` in
`variants/predictor.py`. They declare unavailable lanes, constrain citations to
supplied evidence, and preserve the thesis/forecast schemas. Both reasoning
nodes use the same frozen source-context character limit. The candidate changes
only the director's `skill_addon`: justify movement size from supplied past
returns and shrink weakly supported magnitudes toward zero. It keeps the same
graph, model, input snapshots, targets and evaluator. New paid cohorts also
require the same exact upstream endpoint tag in both arms; the native manifest
and successful provider receipts must match that selection.

Compatibility calibration is separate from predictive evaluation. The first
profile's Nova Micro pilot failed CP1 length/reference validation; Qwen3.5 Flash
passed CP1 but missed CP2's rationale-length minimum. Profile `v2` requests
explicit margins above those same minima. Both original attempts remain in the
shared ledger and their original source revision; no forecasts were scored to
choose this prompt change.

The operator-selected `deepseek/deepseek-v4.1-flash` was then attempted with
profile `v2`. Its first CP1 call returned HTTP 429 without usage or cost, and
the shared budget ledger halted. Following the operator's provider-selection
instruction, an explicit audited recovery retained that failed call, its full
reservation, unknown cost and all budget limits. A new excluded-date pilot
pinned `deepinfra/fp8`; both reasoning nodes passed native validation, with two
reported charges totaling US$0.00237524. This verifies the selected route and
output contract, not prediction accuracy. The paper's calibration evidence
retains all six pilot calls, including the unresolved cost of the earlier 429.

`benchmarks/stocknet_native.py` prepares AAPL, MSFT and GOOG snapshots from the
pinned local StockNet files. Each contains past prices and a current quote;
future prices go into the separate truth source. The target is the next XNYS
session close, checked against the next recorded row. The protocol fixes the
first 20 common eligible development dates and five later dates, one candidate,
one attempt per reasoning node and at most 100 study calls. A July compatibility
pilot is outside both study windows. Missing or rejected episodes stop execution
and prevent partial ranking.

The evidence is historical replay. Original availability and price vintages
are unverified; a modern model may remember outcomes. Some development prices
were exposed in the earlier input study, and deterministic baselines previously
used the later window. The final-assessment seal prevents repeat access through
this study's API; it does not make those prices globally unseen. See
[the learning design](learning-design.md) for future selection safeguards.

The first pinned DeepInfra study completed all 50 native episodes and sealed
its later assessment. [Evidence status](status.md#native-comparison-11-october-2026)
and the [portable receipt export](../paper/study-evidence.json) record both
model arms, same-support deterministic references, coverage and the shared
budget.

## Run with one authorized budget

Install the editable checkout using [the reproduction guide](reproducing.md)
and acquire StockNet through its existing importer. The commands below are
examples of **paid execution**. Set a concrete currently verified model and
use an explicit private environment file or an already configured process key.
Metadata checks alone do not authorize spending.

```sh
python -m benchmarks.stocknet_native pilot \
  --dataset work/datasets/stocknet \
  --output work/native-july-pilot --model deepseek/deepseek-v4.1-flash \
  --provider-slug deepinfra/fp8 \
  --env-file /absolute/path/to/private.env \
  --budget-dir work/native-shared-budget \
  --max-cost-usd 5 --max-calls 128 --max-output-tokens 4096
```

Inspect `native-result.json`, the named native run and its provider receipts.
Only an accepted CP2 artifact establishes that the pilot completed. It does not
measure accuracy. If the shared ledger is halted, stop; creating another ledger
would bypass the budget. A successful pilot's returned actual model identity
must match the subsequent study declaration.

An explicit operator-authorized HTTP 429 recovery uses `zenith budget-recover`
with an evidence file bound to the exact failed call and prior ledger hash.
It retains the failed attempt, unknown cost, full reservation and every limit;
it does not resend the old run. Corrupt accounting, unfinished calls, cost
overruns and other unresolved failures remain blocking. See the recovery
contract in [provider setup](providers.md).

Preparation and planning perform no inference:

```sh
python -m benchmarks.stocknet_native prepare \
  --dataset work/datasets/stocknet --output work/native-study \
  --model deepseek/deepseek-v4.1-flash --provider-slug deepinfra/fp8
python -m benchmarks.stocknet_native plan --study work/native-study
```

If the returned concrete identity differs from the requested ID, supply the
verified `--actual-model` during preparation. Source, cohort and input hashes
are frozen. Do not edit Python or native sources during that experiment.

```sh
python -m benchmarks.stocknet_native run --study work/native-study \
  --phase development --env-file /absolute/path/to/private.env \
  --budget-dir work/native-shared-budget \
  --max-cost-usd 5 --max-calls 128 --max-output-tokens 4096
python -m research cohort-evaluate --study work/native-study/cohort
```

The same ledger and immutable limits cover the pilot and every study episode.
The call ceiling allows bounded compatibility probes; it is not a target to
consume. Reservations remain charged against the client cap even when reported
cost is lower. See [the provider contract](providers.md).

After complete development evidence, the heldout command executes the baseline
and the eligible development-selected candidate. The final key deliberately
consumes the final-assessment seal; retain its exact receipt.

```sh
python -m benchmarks.stocknet_native run --study work/native-study \
  --phase holdout --env-file /absolute/path/to/private.env \
  --budget-dir work/native-shared-budget \
  --max-cost-usd 5 --max-calls 128 --max-output-tokens 4096
python -m research cohort-evaluate --study work/native-study/cohort \
  --final-key native-study-final-v1
```

The native feedback loss averages absolute target-price error divided by truth
price, first across targets and then across issues. A lower candidate loss is a
descriptive result for that intervention, not a trading return, causal diagnosis
or proof of generalization. The [paper](../paper/zenith.tex) records actual
coverage, failures, costs and comparisons only from attributable receipts.
