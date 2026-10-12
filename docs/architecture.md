# One daily loop

`zenith/daily.py` freezes historical snapshots and advances Lab → Oracle →
reviewed Evolve. It uses the original engine in `system/core/engine.py` and the
nodes in `codex/nodes/`. The Lab contains seven feed nodes and 21 reasoning
nodes. Oracle runs against the original Lab and later observations.

The six acquired feeds are STOCK, ETF, MACRO, STOCKGRID, POLYMARKET and NEWS.
CALCULATOR derives cross-asset summaries. Feed tools and contracts are retained;
private universes and credentials are not distributed.

Lab selects assets and freezes predictions. `feedback/engine.py` measures dated
outcomes; `feedback/selection.py` separately scores selection and full-universe
loss. Oracle's analysis informs a proposed change; it does not establish cause.
`tools/refinement/run_evolve.py` and the daily controller retain the reviewed
change as a successor policy. Evolve may be the lead agent or a fixed-prompt
worker using the same packet.

`research/daily_matchoff.py` binds incumbent and candidate to identical later
snapshots. `research/cohort.py` executes no model calls: it gives the native
commands, checks completed run evidence and compares results. Retention records
the review and enforces that the next generation follows the comparison cutoff.

`variants/graph.py` supports explicit graph changes. Keep the original graph as
the baseline. Compare changed inputs separately from changed reasoning when
attributing a result. Runtime records remain under ignored `state/` and `work/`.
