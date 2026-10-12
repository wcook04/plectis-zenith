# Get the original information back

The original system acquired stocks, ETFs, macro series, Stockgrid, prediction
markets and news, then derived calculator summaries. Saved original snapshots
contain hundreds of stocks, ETFs and macro series. The recent A-share studies
used ten stocks and mostly titles; they do not test that information set.

The retained [FNSPID adapter](../benchmarks/fnspid.py) supplies raw AA prices and
articles from a pinned [GitHub source](https://github.com/Zdong104/FNSPID_Financial_News_Dataset/tree/4054842ec476953b30ee874d4b7e8eea786a21fa).
It is a starting slice, not the complete historical universe. Next join ETF
history and archived macro releases at the same daily cutoff, then widen the
assets and dates. Preserve original article bodies and publication clocks.

A saved SPY price file and the original December 2023 Fed statement are in the
private research packet. The January 2024 CPI page could be inspected but direct
original HTML acquisition returned 403. Its original bytes remain missing.

Historical Polymarket marks need verified old questions and availability times.
The inspected archive backfilled its catalog in 2026 and supplies no observed
volume. No inspected source reproduces Stockgrid's original position/strategy
fields. Use explicit missingness or a labelled partial proxy; FINRA short-sale
volume is not a position series.

Audit a few actual daily snapshots before expanding. Even original saved news
has post-cutoff items. Keep publication, observation and receipt times distinct;
current revised data cannot silently become historical evidence. More source
names do not establish useful information or point-in-time validity.
