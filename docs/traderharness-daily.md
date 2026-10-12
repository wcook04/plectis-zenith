# Richer historical days through the original graph

The TraderHarness adapter connects ten stocks to the existing **Lab → Oracle →
Evolve → later Lab** controller. It reuses the acquired A-share source and its
clock/selection helpers without executing or changing the separate five-session
study.

Sources: [TraderHarness at `3e18369`](https://github.com/HephaestLab/TraderHarness/tree/3e18369da5a2060f9c65b27c2a63f99edd93e167)
and [dataset at `3bf5151`](https://huggingface.co/datasets/ANTICH/traderharness-ashare-5y/tree/3bf5151ab3e94851bb09dd8ade815563c44b15a6).
Five hash-verified tables total 175,370,961 bytes: daily OHLCV, announcement
titles/links, derived news headlines, corporate actions and CSI300 OHLCV.
The ten-name universe was fixed using 2021 turnover. Downloaded data stays in
ignored local storage under upstream research-use terms. No upstream code is
executed. These are different evidence types from one archive, not independent
vendor confirmations.

The pinned source supports **696 complete trailing-price snapshots and 695
adjacent next-close pairs** from 22 February 2023 through 31 December 2025.
There are 211 usable snapshot dates in 2023, 242 in 2024 and 243 in 2025.
These are coverage counts, not a declared train/test cohort; a chronological
split must still exclude any target crossing its boundary. Text coverage varies.

## Run it

```sh
python -m pip install -e '.[test,study]'
python -m benchmarks.traderharness_daily acquire
python -m zenith daily init --dataset work/datasets/traderharness-daily \
  --work-dir work/ashare-daily --start 2023-04-27 --end 2023-04-27 \
  --policy examples/daily/sparse-policy.json
python -m zenith daily next --work-dir work/ashare-daily
```

This prepares the full 28-node Lab with April27 inputs and an April28 close
target. Answer real pending prompts through `zenith import-response`; the same
controller later runs Oracle and emits the Evolve review. Follow [the daily
commands](daily-replay.md). Use a new programme directory after source/runtime
changes. `acquire --cached-source PATH` reuses pinned `harness_*.parquet` originals.
Neither command buys inference or manufactures responses.

## Packet boundaries

| Input | Representation |
|---|---|
| STOCK quote | Raw CNY close and 21 consecutive sessions including the preceding close; missing/invalid bars fail rather than forward-fill. |
| STOCK context | Twenty separately rebased gross-wealth bars, already ex-dated actions, CSI300 history. The index is context, not an ETF target. |
| NEWS | Latest four issuer items and two common headlines per issuer from seven days, plus up to two prior same-period profit comparisons from 187 days. Stable source/evidence IDs survive selection. |
| Announcements | Titles and PDF links, not document contents. Midnight/date-only timestamps become eligible at the next session's open. |
| Other five native lanes | Explicitly unavailable; no invented macro, ETF or flow observations. |

News uses source epoch seconds; timed announcements assume Shanghai local time.
Text is capped at the observed close. Packet availability is reconstructed as
close plus one minute. The forecast targets the actual next session close;
Evolve maturity uses later availability. Omitting the extra minute's text from
both snapshots prevents Oracle from explaining a close with a subsequent
headline. XSHG is a common-session proxy for this Shanghai/Shenzhen panel, not
an issuer exchange identifier. Stock codes retain leading zeros; feedback
requires the exact CNY raw-close basis.

Wealth is rebased separately per window and includes gross cash receivable
without reinvestment. It is context only. Future ex-date terms are excluded even
when final archive status says implemented. A future ex-date can therefore
affect a quote without being announced in this restricted action context; quote
forecasts are not economic-wealth or trading-P&L claims.

The financial-fact table is excluded because revision state and accounting
definitions remain unresolved. Timestamps and fixed bytes do not certify
original text/price vintages. Entity templates are candidate associations;
bounded, truncated retrieval is incomplete. Modern models may remember these
historical events.

## The reasoning question

On the input-selected April27 training date, retained headlines allow comparing
Tongwei's 66% year-on-year profit growth with its earlier 60–68% guidance, and
Moutai's 20.59% growth with its earlier approximately 19% estimate. These are
issuer-guidance comparisons, not market consensus or proof of what was priced.
Tongwei's proposed raise of at most CNY16 billion is a separate financing claim
without a final issue price or dilution estimate.

Adapter completion alone is not useful forecasting or learning. Improvement
requires new native outputs and later matched comparisons with unchanged
reasoning and price-only controls. Existing [generation comparisons](generations.md)
also use this source's calendar and separate observation/availability clocks.

## Completed native episode

The April27 → April28 episode completed all 28 Lab and 31 Oracle nodes using
32 accepted primary-agent responses. One Oracle artifact-handle syntax error
was rejected, retained and corrected. Lab issued ABSTAIN; Oracle compared all
ten quotes but assigned no hit rate or forecast loss. Evolve created a reviewed
NEWS-miner candidate making claim-owner, corporate-entity and listing checks
explicit. This codifies a useful procedure; its benefit over the existing
reasoner has not been tested on later days. No generation was promoted or new
paid provider call made. The [receipt](traderharness-native-receipt.json) binds
the original runs, snapshots, source coverage and review.

A separate external audit confirms the identity concern: a later headline
tagged `002594` reports 154.85% profit growth for an electronics-named entity.
The corresponding [27 April 2023 HKEX filing](https://www1.hkexnews.hk/listedco/listconews/sehk/2023/0427/2023042702913.pdf)
identifies BYD Electronic, stock code 285, and that growth figure. A shared
brand/tag cannot make its earnings or share-price move the A-share issuer's own
observation. This verification did not enter the frozen native grounding.

Rebuild the receipt against original local evidence and pinned sources:

```sh
python scripts/export_traderharness_pilot.py \
  --work-dir work/traderharness-native-20261012 \
  --output docs/traderharness-native-receipt.json
```

The next development task is a forecast interface that can test a declared
rich-input hypothesis on this calendar. The existing numerical control is
XNYS-only; copying it would remain price-only. Separately compare claim-owner
accuracy and unsupported association rates for the NEWS candidate. The current
generation scorer requires complete forecasts, so an abstaining candidate
cannot win that gate by avoiding difficult cases.
