# Data in this edition

**This is not financial advice.** [Research notice](../RESEARCH_NOTICE.md).

| Lane | Actual computation input | Public display |
|---|---|---|
| Stocks | Saved real input | Provenance only |
| ETFs | Saved real input | Provenance only |
| Prediction markets | Saved real input | Provenance only |
| Macro | Independently authored synthetic replacement | Complete invented example |
| News | Independently authored synthetic replacement | Complete invented example |
| CALC | Recomputed from real stocks/ETFs and synthetic macro | Provenance only |

The three real inputs are copied byte for byte. Their hashes are recorded in
[the manifest](../examples/demo/provenance.json). The original macro values and
news text are not read to generate the replacements. Fictional examples are not
observations of the historical market. A mixed-input result would test that
particular construction; it would not establish performance on real news and
macro data.

The stock and ETF collector uses [yfinance](https://github.com/ranaroussi/yfinance)
with Yahoo data. The prediction-market collector uses the
[Polymarket market-data APIs](https://docs.polymarket.com/market-data/overview).
These links identify sources and software; they do not establish redistribution
or AI-use permission. Real-payload reuse remains under review. Software licences,
data licences, API access and permission for a particular use are separate.

The default public API contains only the manifest, synthetic replacements and
preparation receipt. It excludes real tables, articles, prompts, model outputs
from private runs and derived CALC tables. Explicit local inspection can expose
private content: keep those views out of public screenshots and recordings.
Do not upload old private research bundles as if they were public release files.

Saved collection clocks do not certify when every underlying observation became
available. The synthetic examples borrow the packet's clock for alignment, not
as a claim that their invented events happened. Any future predictive experiment
must state its information cutoff, source rights and model-contamination limits.
