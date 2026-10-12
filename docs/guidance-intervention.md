# Does comparing earlier guidance improve the next forecast?

This experiment tests a specific part of Will's daily learning loop: change one
reasoning operation, keep its information fixed, and measure the downstream
consequence. It uses real historical inputs and paid model responses. It is a
component assay of the original NEWS instruction followed by a common quantile
forecaster, not a completed 28-node Lab or a replacement for the native graph.

The data come from the pinned [TraderHarness repository](https://github.com/HephaestLab/TraderHarness/tree/3e18369da5a2060f9c65b27c2a63f99edd93e167)
and [A-share dataset](https://huggingface.co/datasets/ANTICH/traderharness-ashare-5y/tree/3bf5151ab3e94851bb09dd8ade815563c44b15a6).
The existing `issuer_profit_state_v1` profile supplies ten stocks, 21 closing
prices, historical actions, CSI300 context and selected issuer titles. Five
other feed lanes are absent. Source revision vintages are unverified. The
underlying LLM may remember these historical events.

## Frozen comparison

The July 20, 2023 compatibility pilot is excluded from measurement. It tests
the NEWS tuple format and the numerical forecaster's existing quantile
validator. It does not certify the complete native CP1/CP2 contracts.

Two issues were selected by reading only the available titles and their dates:

| Issue | Issuer | New result and earlier guidance in the same input |
|---|---|---|
| August 3 | 600519 | H1 profit 359.8 versus approximately 356 yi yuan; about 1.07% higher |
| August 30 | 601919 | H1 profit decline 74.46% versus approximately 74.47%; essentially unchanged |

One yi yuan is 100 million CNY. These are title-level comparisons. Accounting
definitions remain incompletely certified; issuer guidance is not consensus.
Both results were published after the previous session close and are included
at the first subsequent close. The forecast concerns the **following** close,
after a session of possible price response has already occurred.

The baseline uses the authored NEWS node and its previously reviewed issuer
identity addon. The challenger adds a rule to compare the same issuer, profit
metric, fiscal period and units with earlier supplied guidance; retain both
source IDs; distinguish growth from revision; and preserve uncertainty about
consensus and price implications. It names no issuer, date, correct number or
desired forecast direction. The unchanged forecaster receives the same raw
snapshot in both arms, plus the respective miner output. A direct forecaster
receives that snapshot without a miner on August 3 only.

The model is explicitly `deepseek/deepseek-v4.1-flash`, routed to `deepinfra/fp8`,
with temperature zero and a 4,096-token output cap. Eleven attempted calls fit
the remaining capacity of the original shared USD 5 / 128-call ledger:
two pilot calls, five August 3 calls and four August 30 calls. No retries,
fallbacks, ledger replacement or limit increase are permitted. Invalid output
stops the comparison and remains recorded. Actual provider identity and costs
come from receipts, not from the requested model string.

All forecasts are frozen before either later price snapshot is opened.
August 30 is a later paired diagnostic, not a holdout chosen after optimizing
August 3: the same candidate is fixed before both. Neither date is claimed to
be unseen to the model. There is one realization per arm and no significance
or superiority claim.

## What is measured

Interpretation review asks whether each miner links the supplied prior and
current claims, computes the right comparison, distinguishes it from
year-on-year growth, and avoids treating guidance as consensus. This is a
source audit, not an automated causal judge. Tuple validation checks structure;
it cannot establish truth or useful reasoning.

Every forecaster emits q10/q50/q90 for the original ten stocks. The existing
`system/lib/judgmental_forecast.py` validator checks ordering, finite return
fractions and evidence references. Outcomes use exact next-session raw CNY
closes from the same pinned manifest. Scores report median absolute error,
mean pinball loss, interval coverage and width. Price-only historical quantiles
and a zero-median version with the same tails are controls. Quantile scoring
follows [Gneiting and Raftery (2007)](https://doi.org/10.1198/016214506000001437).

The ten stocks share each date's market conditions. They are not twenty
independent replications. A correct interpretation with no later score gain is
a useful result: the factual comparison and the remaining price effect are
separate skills. Any proposed change still needs a fresh native comparison
before admission to the full graph.

## Running the assay

The existing dataset must first be acquired with `--profit-state-memory` as
described in [the daily adapter](traderharness-daily.md). Use an explicitly
authorized existing budget ledger with capacity for eleven attempts and the
4,096-token cap; do not reset a used or halted ledger. Credentials stay in the
environment or an explicitly selected local file.

```sh
python -m research.guidance_intervention prepare --study work/guidance-assay \
  --dataset work/datasets/traderharness-profit-state --budget EXISTING_BUDGET
python -m research.guidance_intervention pilot --study work/guidance-assay
python -m research.guidance_intervention run --study work/guidance-assay
python -m research.guidance_intervention evaluate --study work/guidance-assay
```

The first command has no provider calls. The next two spend within that ledger.
The final command is the first operation that opens later truth. Requests,
responses, format failures, provider receipts, frozen inputs and forecast
seals remain in the local study directory. Do not resume this study after
changing its frozen implementation. Public results are recorded separately
without credentials or local funding/account details.
