# Data sources and the next experiment

The first published fixture is deliberately small enough to audit. Bigger datasets do not fix unclear availability times or contaminated evaluation.

| Source | What it adds | Admission requirement |
|---|---|---|
| [UCI Dow Jones Index](https://archive.ics.uci.edu/dataset/312/dow+jones+index) | Bundled, explicitly CC BY 4.0 historical weekly sample. | Pinned bytes, attribution, independently verified future labels and purged time split. Implemented. |
| [fredapi](https://github.com/mortada/fredapi) and [ALFRED](https://alfred.stlouisfed.org/) | Macro observations and their historical revisions. | Preserve observation date, publication/realtime interval and the vintage available at each forecast cutoff. Series-specific reuse rights still apply. |
| [SEC submissions and Company Facts](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) / [EdgarTools](https://github.com/dgunning/edgartools) | Filing events, fundamentals and reported facts. | Identify the requester as required by SEC; bind accession and acceptance time; avoid using a later amendment before it existed. |
| [Qlib](https://github.com/microsoft/qlib) | Larger experiment-management and evaluation conventions. | Adopt only when needed. Framework code licensing does not grant market-dataset redistribution rights. |
| [exchange_calendars](https://github.com/gerrymanoim/exchange_calendars) | Real exchange sessions, holidays and early closes. | Already used by the private collector; record the venue and calendar policy. |

Two small repositories were cloned for inspection on 11 October 2026: `mortada/fredapi` at `d0a0ba3001ebbbceafdcbdd3eb23828f0537cdff` (Apache-2.0) and `uci-ml-repo/ucimlrepo` at `66747cb189eddd5fc747c4bf74ed4985a2c17454` (MIT). Neither library is needed to run this demo. No framework code was copied into the benchmark.

New observation adapters should retain `observed_at`, `available_at`, `acquired_at`, `revision_id`, `source_id`, `source_sha256`, units, price-adjustment basis and reuse licence. A forecast cutoff admits only evidence available by that cutoff. Missing vintages remain unknown; downloading today's revised series cannot recreate the old information set.

The next useful evaluation is a longer, versioned time series with prospective frozen predictions, simple baselines and multiple independent evaluation periods. Keep every attempted model, timeout and failed parse in the denominator. Report measured calibration and coverage before making any broader performance claim.
