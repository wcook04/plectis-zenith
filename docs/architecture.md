# Architecture

**Experimental research prototype.** The active financial profile runs the full
Lab → Oracle → Evolve structure with the [shared reasoning ontology](reasoning-ontology.md).
It uses historical financial observations. The generic System A fixture and the
reduced basket pilot are separate profiles; their results do not transfer automatically.

Zenith is a language-model program for forecasting changing, partially observed systems. Its nodes read heterogeneous, incomplete, overlapping or delayed observations and save structured records. Reasoning reconciles semantics and clocks, distinguishes missing from conflicting evidence, proposes competing explanations and selects explicit targets. Intermediate records expose the support chain; source agreement is not a count of independent votes. The same system is observed through measurements, subsystems, environment, events and interventions. A derived feed computes summaries from supplied measurements, subsystem and environment records.

Lab inventories the cutoff-bound packet, analyses each feed, synthesises findings, forms competing explanations and freezes an investigation plan at CP1 in the financial profile (a thesis in the generic fixture). Directed miners revisit that thesis using the same permitted feeds; Director freezes predictions at CP2 and Integrity checks both passes. Node and edge counts come from `python -m zenith validate`.

Oracle reads the frozen Lab subject beside later evidence. Deterministic differences and lane reviews enter an evidence summary, attribution hypothesis and final review record. Evolve selects a located failure hypothesis and stages one reusable instruction. The financial profile runs its native three-node scope, freezes the resulting candidate policy, and tests it through local replay and later comparisons. Staging does not change source dossiers or accept the candidate. The generic dossier runner and daily comparison controller remain separate interfaces.

Runtime hydration binds global feeds to the earlier packet for Lab and later packet for Oracle. It does not add native edges. Exact definitions live under `codex/substrate/nodes/`; regenerate diagrams through `scripts/build_graphs.py`. The general interface establishes no universal predictive performance.

Applicability requires common system/entity/time linkage, a declared target and horizon, and later measurable truth. For example, a greenhouse could combine temperature/humidity sensors, soil or subsystem readings, weather context, door-event logs and planned/executed irrigation or ventilation controls to predict humidity or temperature six hours ahead. A missing sensor stream differs from contradictory readings; duplicate weather summaries supply overlapping evidence, not extra votes. Equipment networks and laboratory experiments are other candidate applications, without tested transfer claims. The public System A recurrence remains a separate protocol fixture, not a greenhouse simulator. Compare against direct and numerical baselines; the protocol assumes neither that a language model is necessary nor that it improves prediction.

## Physical problem setting

The proposed use is a partially observed dynamical system. Sensors expose different functions or aspects of state; available histories and known forces, boundaries and interventions condition its future. A position measurement alone need not reveal velocity or direction. History may help, but some state remains unobservable and identifiability is not universal. See Russ Tedrake's [Output Feedback](https://underactuated.mit.edu/output_feedback.html) and [System Identification](https://underactuated.mit.edu/sysid.html).

Heat transfer could combine temperature, heater power, weather and door/vent observations for a six-hour chamber or greenhouse temperature target. Damped vibration could combine camera position, accelerometer readings and force/calibration logs for a one-second displacement or acceleration target. Fluid transport could combine flow, pressure, dye and valve records for downstream concentration; geometry and boundary conditions are necessary inputs.

The graph's proposed job is to align clocks, units and dependent sources; compare sensor-fault with state/regime explanations; select or parameterise a suitable physical model or numerical tool; and freeze target, horizon and uncertainty. Narrative cannot replace equations. Solver integration and transfer to these applications are unimplemented and untested. The disclosed System A recurrence remains a separate protocol fixture, without physical interpretation. Common entity/time linkage and later measurable truth remain required.

The reasoning DAG represents computational dependencies, not physical causality. A physical system may have feedback; an acyclic per-forecast graph coordinates its analysis and tools.
