# Observations in this edition

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
