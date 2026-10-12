---
id: "feeds_mission"
kind: "mission"
summary: "Mission doctrine for deterministic six-lane feed generation and artifact contracts."
focus_paths:
  - codex/substrate/nodes/feeds/global_stock_feed.json
  - codex/substrate/nodes/feeds/global_etf_feed.json
  - codex/substrate/nodes/feeds/global_macro_feed.json
  - codex/substrate/nodes/feeds/global_news_feed.json
  - codex/substrate/nodes/feeds/global_polymarket_feed.json
  - codex/substrate/nodes/feeds/global_calculator_feed.json
  - run_tools6.py
  - tools/stock/stock.py
  - tools/macro/macro.py
  - tools/calculator/calculator.py
doc_links:
  - codex/doctrine/components/data_feeds.md
  - codex/doctrine/operations/codex_change_protocol.md
  - codex/doctrine/components/codex_nodes.md
last_verified_at: "2026-05-16"
---
<!-- DOCTRINE_STRUCTURED_BLOCK -->
## Purpose
Mission doctrine for deterministic six-lane feed generation and artifact contracts.

## Scope
- This doctrine file is `codex/doctrine/missions/feeds.md`. [focus:codex/substrate/nodes/feeds/global_stock_feed.json]
- Source of truth includes `codex/substrate/nodes/feeds/global_stock_feed.json`. [focus:codex/substrate/nodes/feeds/global_stock_feed.json]
- Source of truth includes `codex/substrate/nodes/feeds/global_calculator_feed.json`. [focus:codex/substrate/nodes/feeds/global_calculator_feed.json]
- Source of truth includes `tools/stock/stock.py`. [focus:tools/stock/stock.py]
- Source of truth includes `tools/macro/macro.py`. [focus:tools/macro/macro.py]
- Source of truth includes `tools/calculator/calculator.py`. [focus:tools/calculator/calculator.py]

## Claims
- Canonical claim path: `codex/substrate/nodes/feeds/global_stock_feed.json`. [focus:codex/substrate/nodes/feeds/global_stock_feed.json]
- Canonical claim path: `codex/substrate/nodes/feeds/global_calculator_feed.json`. [focus:codex/substrate/nodes/feeds/global_calculator_feed.json]
- Canonical claim path: `tools/stock/stock.py`. [focus:tools/stock/stock.py]
- Canonical claim path: `tools/macro/macro.py`. [focus:tools/macro/macro.py]
- Canonical claim path: `tools/calculator/calculator.py`. [focus:tools/calculator/calculator.py]

## Interfaces
- Focus paths:
  - `codex/substrate/nodes/feeds/global_stock_feed.json`
  - `codex/substrate/nodes/feeds/global_calculator_feed.json`
  - `tools/stock/stock.py`
  - `tools/macro/macro.py`
  - `tools/calculator/calculator.py`
- Related docs:
  - `codex/doctrine/components/data_feeds.md`
  - `codex/doctrine/operations/codex_change_protocol.md`
  - `codex/doctrine/components/codex_nodes.md`
<!-- END_DOCTRINE_STRUCTURED_BLOCK -->
# Feeds Mission Theory

Source basis: feed node JSON under `codex/substrate/nodes/feeds/`, tool modules under `tools/`, and generated bundle `codex/derived/compiled/feeds.json`.

---

## Mission, In One Line

Feeds are the deterministic substrate: generate stable, lane-specific market state artifacts that every upstream reasoning mission depends on.

Feeds are **not reasoning agents**. They are data programs. They do not interpret; they acquire and structure. If a feed node produces garbage, the Lab and Oracle missions above it have no recovery mechanism — they will reason over garbage with full confidence.

---

## Why This Construct Exists

- Force a clean separation between data acquisition and interpretation. Data collection errors and reasoning errors require different debugging strategies.
- Keep raw state reproducible and auditable before LLM reasoning starts. A Lab run should be replayable by re-feeding the same artifacts.
- Give each lane its own identity, scope, and failure surface. A stock feed outage should not contaminate macro outputs.
- Make downstream reasoning traceable to explicit feed artifacts, not transient API calls that may have changed between runs.

---

## Topology (How It Is Constructed)

```
Wave 0 (parallel):
  global_stock_feed
  global_etf_feed
  global_macro_feed
  global_news_feed
  global_polymarket_feed

  global_calculator_feed  ← runs after stock/etf/macro complete (dependency)
```

Six feed nodes. Five base feeds are root nodes (no dependencies). `global_calculator_feed` depends on stock + macro + ETF feeds, making it the last feed to execute in wave 0.

The dependency pattern is: **independent raw lanes first, derived analytic lane second**.

---

## Lane Identity Map

| Lane | Node | Tool Module | Config | Epistemic Role |
|------|------|-------------|--------|----------------|
| STOCK | `global_stock_feed` | `tools.stock.stock` | `codex/substrate/configs/stock_default.json` | Raw price and momentum; realized tape |
| ETF | `global_etf_feed` | `tools.stock.stock` | `codex/substrate/configs/etf_default.json` | Cross-asset sector flows and rotation signals |
| MACRO | `global_macro_feed` | `tools.macro.macro` | `codex/substrate/configs/macro_default.json` | Hard economic constraints and rate/credit regime |
| NEWS | `global_news_feed` | `tools.news.news` | `codex/substrate/configs/news_frequency.json` | Contextual and narrative; usually lagging |
| POLYMARKET | `global_polymarket_feed` | `tools.polymarket.polymarket` | `codex/substrate/configs/polymarket_scan.json` | Pre-pricing probability sensors |
| CALCULATOR | `global_calculator_feed` | `tools.calculator.calculator` | `codex/substrate/configs/calculator_default.json` | Derived cross-feed analytics, regime classification, normalization |

**Stock vs ETF split:** Both use the same base `tools.stock.stock` module but operate on separate instrument universes. This separation is intentional to prevent mixed-lane ambiguity when a Lab miner annotates a signal — it must be clear whether an observation is individual-equity vs sector/cross-asset.

**Calculator as a derived lane:** Calculator does not pull raw market endpoints. It ingests the structured outputs of stock, macro, and ETF feeds and computes normalized regime metrics: `Energy`, `Directional_Concentration`, and other cross-feed aggregates. These metrics are what Lab uses for regime-conditioned emphasis decisions (see `lab.md` § Regime-Conditioned Emphasis).

---

## Semantic Design Choice

Feed nodes intentionally have minimal narrative semantics:
- `teleology`: deterministic tool execution
- `mechanism`: Python module execution
- `instruction`: empty or near-empty

Meaning is carried by configuration and module wiring, not prompt prose. This is by design — feeds should not require LLM judgment to produce their outputs.

---

## Runtime Identity

All feed nodes are:
- `type: tool`
- `is_artifact: true`
- `meta.is_feed: true`
- `platform: chatgpt` (execution wrapper), with work delegated to Python modules

This makes feeds operationally "data programs," not reasoning agents.

Operator runners must treat `codex/substrate/nodes/feeds/*.json` as the lane
inventory. `run_tools6.py` discovers every node with `meta.is_feed = true`,
orders those targets by declared dependencies, and only falls back to its
embedded list if the graph is unavailable. The embedded list is not a scope
definition. A runner that says "six feeds" or omits `global_etf_feed` is stale.
Dependent feeds are readiness-gated: if an upstream feed returns a non-green
artifact status, the runner records the downstream node as `skipped` with the
upstream reason unless `--ignore-dependency-status` is explicitly used.
Each run also writes `artifacts/feed_readiness_summary.json`, a compact machine
surface with `ready`, per-status counts, dependency edges, per-feed rows, and
blockers. Always-on monitors, Station cards, and Oracle preflight checks should
read that summary before trying to infer readiness from missing individual
artifacts.

---

## Failure Handling

Feed failures propagate silently if not handled at the feed artifact level. The engine marks a feed node as `error` and continues, but downstream miners will receive empty or stale artifact content.

| Failure Type | Symptom | Effect on Lab |
|---|---|---|
| Tool module exception | Feed node `status: error`, artifact not written | Miner for that lane receives no input; may produce empty `tuples` |
| Partial data (some tickers missing) | Feed artifact written with gaps | Miner may hallucinate completeness; produces tuples that cite data that wasn't fetched |
| Stale data (window mismatch) | Feed artifact written with old timestamps | Lab reasons over T-2 state instead of T-1; systematic directional error |
| Calculator dependency missing | Calculator feed waits; if deps fail, calculator fails too | Lab loses regime classification; cross-feed analytics unavailable |

**Rule:** When investigating a degraded Lab run, start at the feed artifacts — not the Lab prompts. A structurally green feed artifact is the prerequisite for meaningful Lab reasoning.

---

## Feed Artifact Structure

Each feed node writes a standard artifact envelope:

```json
{
  "node_id": "global_stock_feed",
  "status": "ok",
  "timestamp": "2026-03-05T16:00:00Z",
  "data": {
    "lane": "STOCK",
    "snapshot_time": "...",
    "assets": [ ... ],
    "metadata": { ... }
  }
}
```

The `data.lane` field is the canonical lane tag referenced by Lab miners and Oracle diff nodes.

---

## Why This Matters to Lab and Oracle

- **Lab's CP1/CP2 quality is bounded by feed coverage and cleanliness.** A miner that receives an empty feed produces empty tuples. An empty tube into `lab_cross_corr_v1` creates a structural gap that cannot be recovered downstream.
- **Oracle's diff/evaluate/attribution quality is bounded by feed determinism and replayability.** Oracle compares Lab Phase 2 outputs against realized lane state — it needs the realized feed artifacts to be present, correctly timestamped, and structurally consistent with what Lab saw at T-n.
- **If feeds are unstable, every higher semantic layer degrades**, regardless of prompt quality. Feed stability is the floor of system quality.

## Temporal Interface

- Feeds define the deterministic baseline at `T-n`.
- Lab converts that baseline into CP1 and then forward CP2.
- Oracle later reads realized data at `T` plus the same `T-n` lineage to audit what actually happened.

That means feed changes are not local. They alter the baseline shared by both predictive and hindsight layers.

---

## Practical Refinement Axes

1. **Universe curation**: Coverage breadth vs noise. Too many assets increases miner cognitive load; too few reduces signal coverage. Per-lane tuning in `codex/substrate/configs/`.
2. **Snapshot timing and window policy consistency**: All lanes should use consistent T-n window definitions per run. Mismatched windows (e.g., stock at T-1, macro at T-3) produce artificial divergence.
3. **Missing/stale/null handling per lane**: Each module should emit explicit null markers rather than silently omitting fields. Silent gaps create harder-to-diagnose downstream errors than explicit missing-data signals.
4. **Calculator normalization and imputation**: When upstream feeds have missing values, Calculator must have a defined imputation policy rather than propagating nulls into regime metrics.
5. **Runtime failure signaling**: Feed artifacts should include metadata on fetch success rate, API response codes, and any partial failures, so Lab miners can conditionally adjust confidence on signal-sparse lanes.
6. **Config governance**: `config_ref` defaults should be versioned. Inline overrides in node definitions should be rare and explicitly commented.

---

## Living Notes

- Treat feed changes as infrastructure changes, not prompt tweaks. A feed module change can break every downstream mission simultaneously.
- Preserve deterministic behavior first; optimize expressive semantics only in downstream Lab/Oracle missions.
- Feed config files (`codex/substrate/configs/*.json`) are not generated — they are authored. Changes to them require scratchpad validation.
- When changing a feed node, tool, or config, follow `codex/doctrine/operations/codex_change_protocol.md`.
- When adding a new lane, read `codex/doctrine/skills/kernel/add_lane.md` first.
