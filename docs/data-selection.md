# Choose the experiment from the evidence

**Decision, 11 October 2026:** use the collected **TraderHarness A-share panel**
for the first broad historical test of information use and forecast-skill learning.
It is the strongest ready joined corpus among those inspected. This is a data
selection, not an executed experiment or a claim of profitable trading.
Paid execution remains held under the operator's research-first instruction.

The practical question is: **given recent prices and dated company information,
does this reasoning graph forecast five-session market-relative returns better
than price-only controls, and does one bounded skill revision improve it on later
dates?** Five sessions is a pragmatic first horizon, not an empirically optimal
choice. A window of past evidence supports a forecast over a future window;
there is no assumption that one isolated snapshot explains the market.

## What we actually collected

The pinned [dataset release](https://huggingface.co/datasets/ANTICH/traderharness-ashare-5y/tree/3bf5151ab3e94851bb09dd8ade815563c44b15a6)
and [repository](https://github.com/HephaestLab/TraderHarness/tree/3e18369da5a2060f9c65b27c2a63f99edd93e167)
supplied six manifest-verified tables, **184,974,691 bytes** locally:

| Table | Observed contents | Admission limit |
| --- | --- | --- |
| Daily prices | 5,536,889 rows; 5,073 symbols; no duplicate symbol/date | Missing months in 2022; raw quotes require corporate-action handling |
| Company announcements | 2,088,367 titles, identifiers and source-PDF links | PDFs not collected; 83.872% of timestamps are midnight, treated as day precision |
| News | 766,022 rows; 598,976 derived headlines | 167,046 redacted rows excluded; full article prose and original text vintage unverified |
| Financial facts | 101,463 dated rows | Revision vintage unverified; omit from the first comparison |
| Corporate actions | 31,131 rows | Share/cash units inspected; complete wealth-label validation still required |
| CSI 300 | 1,254 daily observations | Evaluation reference; not an executable hedge |

The news has observations in every covered month, including 157,270 rows in
2024. Twelve calendar-spaced checks across 2024 joined the same ten stocks to
prices, prior facts and recent announcements. These checks establish useful
overlap, not complete per-episode admission for a frozen study.

The fixed universe uses the ten highest mean-turnover eligible main-board names
in May–December 2021, before study scores. All ten have all **711 expected XSHG
sessions from February 2023 through December 2025**. This observed-panel rule
does not establish survivorship-complete sampling. September–December 2022
prices are missing and January 2023 is partial. An extended check found ten
missing 2026 sessions for one name; never bridge absent bars into a false horizon.

An inspected BYD share distribution illustrates why labels matter: its raw
opening gap is −66.76%, while the recorded additional shares and cash imply a
gross mark change of +0.89%. This corroborates the source's per-ten-share units;
it is neither an investment result nor independent certification of every action.
See [exact sources, hashes and checks](data-selection-intraday.json).

## The smallest useful experiment

1. **Observe:** after a session closes, provide the last 20 sessions, admitted
   dated headlines and company-announcement titles. Use fixed text selection
   and token limits. Exclude redactions, future fields and unverified financial
   vintages. Day-only records become eligible next session; freeze the precise
   lag and retrieval rules before scoring. Publication metadata does not prove
   that the archived text was identical at that historical time.
2. **Reason:** one node interprets the evidence and names uncertainties; a second
   forecasts the return. Both do flexible language reasoning. The shared input
   projection, schemas and evaluator are fixed; the only initial learning variable
   is a short forecast skill. This explicit small-graph ablation leaves the native
   Lab graph intact.
3. **Measure:** forecast next-session open to the fifth exchange-session close,
   using a corporate-action-aware gross holding-period return minus the matching
   CSI 300 price-index return. That mixed benchmark basis must be disclosed;
   it is not a self-financing excess-return portfolio. Primary loss is squared
   error, averaged across stocks and then equally across issue dates. Use
   nonoverlapping outcome windows and purge outcomes across phase boundaries.
4. **Compare:** establish the unchanged graph against zero-excess, momentum,
   train-fitted ridge and a matched price-only graph. Then compare a fixed-budget
   skill update using training feedback with outcome-only and feedback-blinded
   updates. Retain rejected attempts, unchanged selections and a separate repeat
   control. Pick once on validation and report every scheduled case and missing
   forecast; never improve a score by silently dropping failures.
5. **Diagnose:** after training outcomes arrive, a separate review may inspect
   later reporting and propose an error explanation. Missing evidence, an invalid
   calculation and a failed hypothesis are distinct. Later news is review-only;
   a plausible story is not a causal label. An explanation earns confidence when
   its bounded intervention improves later matched cases.

February 2023–December 2025 is the proposed coverage interval; exact phase
boundaries, episode counts, cost cap and stop rule remain to be frozen after
the adapter and labels pass admission. Data-quality inspection has exposed
some historical prices and corporate actions. Later-trained model knowledge
is also unknown. A historical split can separate our fitting and selection,
but cannot establish globally unseen evidence; prospective capture is required
for that stronger claim.

The existing [two-node adapter](trading-study.md) implements next-session US
long/cash decisions, not this five-session China task. Do not reuse its trading
score unchanged. Validate China T+1, suspensions, price limits, lot sizes, fees,
taxes and execution before making any strategy-return claim. The first proposed
study measures forecast information and learning feasibility only.

## Why the alternatives wait

| Candidate | Actual inspection | Decision |
| --- | --- | --- |
| FinMultiTime AAPL | No 2024 news; only five articles across the proposed twelve test dates | Old rich-input schedule withdrawn; price/filing adapter remains tested |
| StockBench | Real cached news; native epochs repair shifted naive clocks; continuous SPY labels not established | Conditional US alternative after coverage repair |
| MTBench | Actual paired windows; future-derived fields, duplicate windows, some later boilerplate in dated text | Diagnostic source, not ready trading evidence |
| Official macro releases + ETFs | Seven ETF panels acquired, each 1,064/1,064 checked sessions; release samples and vintage differences inspected | Best next structural/sector extension; full release cohort still needs assembly |
| Issuer earnings releases | Primary prose collected; one Apple event independently clock-qualified | High-quality event direction, presently too few joined episodes |
| CN-Buzz2Portfolio / FinTradeBench | Sector raw release unverified here; accessible finance QA sample has reasoning answers | Method reference / auxiliary reasoning test, not future-return ground truth |

Inspection records: [news](data-selection-news.json),
[issuer events and ETF acquisition](data-selection-events.json),
[macro and prediction markets](data-selection-alternatives.json), and
[independent experimental-design review](data-selection-design.json).
Original data stay in ignored local storage. Research-only release terms and
upstream rights remain distinct from the repository's code license.
