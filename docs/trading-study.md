# Rich-input forecast-skill study

The selected A-share experiment is now implemented by
[the five-session study](ashare-study.md). This document describes the earlier
US next-session adapter and its withdrawn AAPL schedule.

This is an executable, **unexecuted capability** while experiment execution is
on hold for data selection. No result or trading advantage is established here.
The AAPL schedule below is **not the selected next experiment**: the density
audit found no 2024 news and only five news records across its twelve test dates.
See [the data decision](data-selection.md) before freezing another study.
The owner is `research/trading_study.py`; follow [program.md](../program.md)
for the broader scientific workflow and [providers.md](providers.md) for budgets.

The experimental graph is dated evidence → shared interpretation → forecast.
Only the forecast node's natural-language skill, at most 1,200 characters,
changes. The protected instructions, input projection, output schema and return
evaluator stay fixed. This adapter shares the budgeted provider and research
serialization; it does **not** execute native CP1/CP2 or the full Lab graph.

The rich profile uses AAPL prices, news excerpts and filing facts from the five
locally admitted FinMultiTime leaves. It does not supply ETFs, macro releases,
prediction markets or stock-flow data. The release pin is
`72d4e97b9acb92651949b8efb22c55676ff633ff`; `source-manifest.json` binds bytes.
The release card's MIT label does not establish redistribution rights for
Nasdaq/publisher articles or Yahoo prices. Keep originals and run artifacts local.

Each issue occurs one minute after XNYS close. The target is the conditional
mean arithmetic return `next Close / next Open - 1`, with next-session open entry
and close exit. History contains 20 contiguous bars plus the preceding close.
The frozen long/cash rule invests only above its approximately 10bp round-trip threshold:
1bp fee and 4bp slippage per side. These are simulated fills, not orders.

News admits the latest five unique records in seven calendar days, up to 800
characters each. Day-only news and per-fact SEC `filed` dates become eligible at
the next XNYS open; same-day records are excluded. Filing facts retain accession,
period, concept and unit. Publication, SEC acceptance and acquisition clocks are
unverified; historical price adjustment vintages are also unverified.

The rich profile freezes these half-open issue intervals; the target session
must also end inside its interval. Calendar-spaced dates are selected without
consulting returns, news volume or filing values.

| Phase | Interval | Issue dates |
| --- | --- | ---: |
| Numerical fit | 2019-01-01 to 2022-06-01 | All eligible dates |
| Training | 2022-06-08 to 2023-06-01 | 9 |
| Validation | 2023-06-01 to 2024-01-01 | 6 |
| Final test | 2024-01-01 to 2025-03-29 | 12 |

Run from this checkout using its own installed Python environment. Prepare an
operator-authorized JSON file with a `budget` object containing `model`,
`provider_slug`, `budget_dir`, `max_cost_usd`, `max_calls` and `max_output_tokens`.
Use one existing shared ledger and identical caps throughout; do not reset a
halted ledger. Freeze does not authorize inference. The four subsequent actions
can make paid calls and require explicit execution authorization; the operator's
current instruction holds execution while the data choice is reviewed.

```sh
python -m research.trading_study freeze --profile finmultitime --dataset work/datasets/finmultitime --authorization work/trading-authorization.json --study work/rich-aapl-study
python -m research.trading_study development --study work/rich-aapl-study --env-file .env
python -m research.trading_study learn --study work/rich-aapl-study --env-file .env
python -m research.trading_study select --study work/rich-aapl-study --env-file .env
python -m research.trading_study final --study work/rich-aapl-study --env-file .env
```

Use a fresh study directory. The env file is explicit; never commit it. Freeze
writes `frozen.json`, `binding.json`, `inputs.json` and `packets.json`, including
source/data hashes, split membership, fitted ridge anchors and budget identity.
Forward packets exclude realized labels and review evidence. Subsequent actions
reject changed frozen sources, inputs or packets.

`development` evaluates the unchanged rich baseline and a price-only control
on training dates. `learn` attempts six skill proposals: two rounds for each of
`trace_feedback`, `outcome_only` and `feedback_blinded`. Accepted proposals are
evaluated on training dates. The trace arm receives complete scheduled support
with bounded state, interpretation and forecast excerpts, admitted context and
training-only later-news review. These excerpts are not complete thought traces.
Outcome-only receives aggregate/daily outcome summaries; blinded proposals see
input marginals and unranked prior skills, without outcome feedback or incumbents.

Later review spans at most six later sessions, clipped before training ends;
its latest-five/rolling-seven-day selection can omit relevant reporting. Later
articles support retrospective hypotheses, not causal market labels. Manual
investigator comments do not enter proposal generation in this implementation.

`select` requires every preregistered proposal attempt, evaluates the accepted
bank on validation and freezes one policy per arm in `selection.json`. A candidate
with any schema-rejected validation date is ineligible; unchanged wins ties.
`final` seals that selection before test calls and writes `result.json`. Unchanged
arms alias baseline observations; only `baseline_repeat` draws another baseline.
Final controls also include flat forecasting without interpretation, price-only,
zero, always-long, fit-only ridge, training-refitted ridge and training-fitted
forecast shrinkage. Failed forecasts remain cash allowances; complete-support
return MSE is unavailable when any forecast abstains or fails. All attempts persist.

[ATLAS v5](https://arxiv.org/abs/2510.15949v5) is the closest prompt-revision
comparator: it protects interfaces while updating instructions using scored
history and interaction summaries. Our outcome-summary arm adapts an information
pattern; it is not an ATLAS reproduction. See [trading-prior-art.json](trading-prior-art.json).
The sparse fixed schedule and descriptive dependent bootstrap do not establish
population superiority. Historical replay with later-trained LLMs also cannot
certify freedom from pretraining contamination, profitability or novel learning.
