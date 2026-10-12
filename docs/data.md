# Research data

## Selected and imported: NEPSE Open Data

The executable basket experiment uses [SocrateAI NEPSE Open Data](https://github.com/socrateai-official/nepse-open-data/tree/497e27238a107de00c6f435a4f4f76983205577d), pinned to `497e27238a107de00c6f435a4f4f76983205577d`. Its [MIT-form licence](https://github.com/socrateai-official/nepse-open-data/blob/497e27238a107de00c6f435a4f4f76983205577d/LICENSE) expressly covers “this dataset and associated documentation files.” The publisher grants use, copying, modification, publication and distribution subject to retaining the copyright and permission notice. This is the publisher's grant, not an independent certification of every upstream right. The import preserves the full licence and attribution.

The downloader retrieves only the pinned adjusted-instrument and index CSV directories. It does not execute scraping scripts. The experiment imports records through 31 December 2025, using 2023 development and 2024 test origins. A first strict import exposed conflicting duplicate records in March 2026; no conflicting value was chosen or averaged. Failed imports remain local diagnostic evidence and cannot be loaded as a completed panel.

| Import audit | Count |
|---|---:|
| Adjusted instrument observations | 447,243 |
| Index observations | 59,319 |
| Instrument identifiers / index identifiers | 420 / 17 |
| Invalid source rows quarantined | 2,319 |
| Missing optional volume values preserved | 26,994 |
| Instruments eligible at the fixed formation date | 147 |

Every source file has a checksum. Date/filename mismatches and conflicting duplicates stop ingestion. Exact duplicates are recorded and deduplicated. Missing or invalid close values are quarantined with their original rows; optional blank values remain missing. The database, licence, universe and per-cutoff numerical stores are hashed. A partial import without its final audit is rejected.

These are genuine historical financial observations. They have not been called synthetic. The baskets are constructed research indices with a disclosed formation rule; they are not actual ETFs. Price adjustment vintages and historical publication times are unavailable. Instrument types and historical sector classifications are not supplied. The evaluation is a retrospective replay of the published snapshot, not a certified point-in-time or survivorship-free trading backtest. Carried-forward quotes have explicit ages and are not treated as executable liquidation prices. See [the full basket protocol](baskets.md).

The earlier provider audit did not settle rights to Yahoo-derived data. This dataset-specific licence provides the selected route; yfinance, news feeds, macro releases and Polymarket are not used in the basket experiment. Source code licences for other repositories do not substitute for data permission.

## Existing public fixture

**Experimental research prototype.** The public example uses synthetic observations of a disclosed toy generator. No predictive improvement has been demonstrated.

The example describes an invented abstract System A. Every source observation is a synthetic view of the same disclosed toy generator; derived values are recomputed from these inputs. It is not a physically validated simulation.

| Feed | Contents | Origin |
|---|---|---|
| Measurements | Abstract `signal_a` and `signal_b` observations | Synthetic generator view |
| Subsystems | Additional views of the same abstract state | Synthetic generator view |
| Environment | External context such as `context_a` | Synthetic generator view |
| Events | Authored event records | Synthetic generator view |
| Interventions | Authored control records such as `control_a` | Synthetic generator view |
| Derived | Deterministic summaries of supplied observations | Computed |

Quantities such as `signal_a`, `signal_b`, `context_a` and `control_a` have explicitly arbitrary or dimensionless units. The feeds are multiple views of the same invented state, not independent physical models.

Each observable records `target_id`, `value`, `unit`, `observed_at` and `available_at`. A record's observation time and the time it becomes available are different clocks. Earlier packets must exclude any value unavailable at their cutoff. Later records evaluate the same declared target at its exact horizon. Do not infer causal effects from recorded interventions alone.

[Provenance](../examples/demo/provenance.json) identifies the authored inputs and hashes. Synthetic dates organize the teaching example, not actual events. Public examples are separate from historical private runs; no historical payload has been renamed as synthetic.

The disclosed toy recurrence is `x[n+1] = 0.7*x[n] + 0.2*context[n] + control[n] + seeded_noise`, with seed 17. All quantities are dimensionless. This prescribed recurrence produces the example; it is not learned by Zenith or evidence of predictive generalization. [Observation payloads](../examples/demo/observations.json) expose the synthetic views.

A feed is a perspective on a shared system, not an independent vote. Real observation sets may overlap, omit quantities, disagree or arrive late. Link records by system, entity and time before interpreting agreement. Applicability requires an explicit forecast target and horizon with later measurable truth. The toy recurrence is a protocol fixture; it does not establish that reasoning improves on direct or numerical prediction.

## What the reasoning must do in one case

At the earlier cutoff, `SIGNAL_A` is −0.4. The context feed reports a negative context; the event feed describes that same context in words. Those two records share evidence, so agreement must not count twice. The interventions feed records a planned control with a future effective time: an intention available now is different from an effect observed later.

Lab must turn the permitted record into a named target, a predicted value and a horizon, while retaining the support for that choice. In the later packet, `SIGNAL_A` has an observed outcome and `SIGNAL_B` is deliberately missing. Oracle can check a matching forecast of the first quantity; it must leave the second unresolved. These are properties of the authored example, not answers produced by a model. A simple predictor is a baseline the reasoning graph would have to justify improving on.
