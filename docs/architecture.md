# Follow one snapshot pair

> **This is not financial advice.** This is experimental research. Historical
> examples and model outputs are not investment recommendations and must not be
> used to make financial decisions. See the [research notice](../RESEARCH_NOTICE.md).

1. Give Lab the saved earlier feed directory. It reads all five source feeds and
   CALC, runs its two reasoning passes and saves the selected predictions.
2. Give Oracle the original Lab directory and the later feed directory. Code
   measures recorded outcomes; reasoning nodes propose explanations.
3. Evolve reads the paired record and proposes a versioned instruction or graph
   change. Preserve the old procedure and the exact proposed change.
4. Compare both versions on the same later inputs before retaining a change.

[The diagrams](graphs.md) show the operators and their dependencies. Five source lanes
are present: STOCK, ETF, MACRO, POLYMARKET and NEWS. CALCULATOR derives
summaries from stock, ETF and macro inputs. The saved feeds are inputs; replay
does not call live acquisition tools to replace their contents.

| Operation | Owner |
|---|---|
| Load and execute the original graph | `zenith/runtime.py`, `system/core/engine.py` |
| Score forecasts and selections | `feedback/engine.py`, `feedback/selection.py` |
| Build the paired Evolve handoff | `tools/refinement/run_evolve.py` |
| Freeze a reviewed successor policy | `zenith/daily.py::compile_review` |
| Compare later versions | `research/daily_matchoff.py`, `research/cohort.py` |
| Trace and aggregate failure hypotheses | `research/failure_windows.py` |

`zenith daily` is the existing controller for an adapter-backed sequence. The
FNSPID adapter supplies prices and news only; it is separate from the original
six-input mixed example. Direct `zenith run lab` and `zenith run oracle` accept saved
feed directories without inventing a new dataset or scheduler.

An execution failure, a forecast error and a proposed explanation are different
records. Keep all three. See [failure diagnosis](failure-diagnosis.md) for the
original evidence-location distinctions and repeated-window analysis.

The current [demo](demo.md) retains real stock/ETF/prediction-market inputs and
uses labelled replacements only for macro/news. CALC is recomputed.
