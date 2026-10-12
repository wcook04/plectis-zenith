# Observations in this edition

## Selected research data route

The [active programme](../program.md) requires histories for a shared universe of constituents and research baskets. Source observations stay private unless their licence permits publication. Each imported dataset needs its provider, product, retrieval date, terms reference, adjustment convention, availability rule and hashes recorded. Historical membership and delistings need explicit treatment; choosing today's survivors does not recreate the historical universe. Source dates alone do not establish point-in-time availability.

GitHub and provider checks on 12 October 2026 found reusable infrastructure, but did not clear a downloaded price panel:

| Source | Use and boundary |
|---|---|
| [Qlib](https://github.com/microsoft/qlib/tree/54355232463878d2eebb91fe0ee5fa7fa1f5976c) | Reusable feature, model and evaluation workflows. Its MIT code licence is not a licence for linked price data or Yahoo collection. |
| [MASTER](https://github.com/SJTU-DMTai/MASTER/tree/de8f58557096abde4216a701b35fc4368158d111) | A relevant cross-stock numerical comparator. The README documents earlier validation/test preprocessing defects. Its cross-section-normalised labels are not directly calibrated basket-return targets; reproduce our target and split rules when adapting it. |
| [FinTSB](https://github.com/TongjiFinLab/FinTSB/tree/a48fef9baf368160b23abd8e91935910140f445f) | Its README directs users to Eastmoney QuantAPI for data. The repository does not itself settle permission for our processing or publication. |
| [Twelve Data](https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage) | Individual plans explicitly include academic research and prohibit redistribution. This article does not establish permission to transmit the chosen feed to a hosted model. |
| [Norgate EULA 20261002](https://norgatedata.com/subscribe/eula.php) | Explicitly permits personal academic research and third-party processing on the subscriber's behalf, provided the processor receives no independent-use rights. Public extracts require express permission. A model endpoint's own data terms must satisfy that condition. |

Norgate is the clearest conditional hosted-processing route among those checked; Twelve Data is another explicit research-use route. Neither is a selected or purchased dataset. Check the exact product's coverage, costs, retention and processing terms before acquisition. No financial data was downloaded or sent to model providers for this audit. A derived statistic does not automatically become unrestricted data.

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
