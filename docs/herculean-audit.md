# A fuller daily source that failed content admission

Herculean initially looked closer to Zenith's desired historical multi-feed
snapshot: eight equities with OHLCV, daily news and filing sections. We inspected
the public DuckDB at Git commit `7e4e9cf82a6affd77124e0e17ec9b915719eff9f`.
The 30,158,848-byte file has SHA256
`da5aa069afbb66efa2cce31d16b48bd9b7c263111305934cb3d368d584caf7e2`.
The [pinned database](https://github.com/xueqingpeng/trading-analysis/blob/7e4e9cf82a6affd77124e0e17ec9b915719eff9f/env.duckdb)
is independently inspectable; the [dataset card](https://huggingface.co/datasets/TheFinAI/Herculean)
describes the release. It was not admitted to Zenith's forward input.

Actual queries found 2,656 price rows, 3,888 news summaries and 73 filing excerpts.
All eight issuers share 332 expected XNYS sessions from December 2, 2024 through
March 31, 2026. That complete calendar did not establish that the text was safe
for historical reasoning.

A fixed inspection of the earliest three MSFT trading dates found:

| News row | Dataset date | Content problem | Primary-source cross-check |
|---|---|---|---|
| 2432 | December 2, 2024 | Attributes $77.7bn revenue, $38.0bn operating income, $27.7bn net income and $3.72 EPS to September 2024 | Those figures match Microsoft's [October 29, 2025 release for September 2025](https://www.microsoft.com/en-us/Investor/earnings/FY-2026-Q1/press-release-webcast). |
| 2433 | December 3, 2024 | Explicitly describes FY2026 Q2, including $81.3bn revenue and $5.16 EPS | These results were announced [January 28, 2026](https://www.microsoft.com/en-us/Investor/earnings/FY-2026-Q2/press-release-webcast). |
| 2434 | December 4, 2024 | General capital-return and volatility discussion | No concrete incremental operating development identified in this bounded inspection. |

These are two direct temporal counterexamples, **not an estimate of the corpus's
contamination rate**. A one-day delay cannot repair future-year information.
This also does not invalidate every price or filing record. The earlier MSFT
filing row 50, dated October 30, 2024, contains substantial MD&A/risk sections;
its inspected earnings figures agree with the [contemporaneous issuer release](https://www.microsoft.com/en-us/Investor/earnings/FY-2025-Q1/press-release-webcast).
The complete filing has not been authenticated against an original accession.

The source schema retains date-only records without article source URLs or
filing acceptance timestamps. All 3,888 highlights lack HTTP URLs; repeated
phrases indicate templating, not an independently measured corruption rate.
The immediate decision is to quarantine NEWS, retain the audit, and continue
with the already admitted InvestorBench development stream. Individual price
and filing records may be reconsidered after their own source checks.

The [machine-readable audit](herculean-audit.json) records custody, actual queries,
selected row identities and source links. Downloaded texts stay in ignored local
storage; this public report paraphrases the relevant counterexamples. A separate
work-directory environment supplied DuckDB; Zenith's runtime dependencies did
not change.

To inspect the counterexamples independently, download the pinned file, verify
its SHA256, open it with DuckDB in read-only mode and run:

```sql
SELECT id, symbol, date, highlights FROM news WHERE id IN (2432, 2433, 2434);
SELECT id, symbol, date, document_type FROM filings WHERE id = 50;
SELECT symbol, COUNT(*), MIN(date), MAX(date) FROM prices GROUP BY symbol;
```

The reusable lesson is specific: inspect dated content against original releases
before trusting synchronized table coverage or a provider's historical label.
