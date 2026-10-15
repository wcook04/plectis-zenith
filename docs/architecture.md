# Active and historical architectures

The active implementation studies how to investigate and repair ordinary programs. It reuses the provider, budget and source-custody layers. The financial investigator and graph below are retained historical profiles with their original interfaces and evidence.

## Current source owners

| Source | Responsibility |
|---|---|
| `research/conformance_study.py` | Freeze native tasks, make fresh parent programs, compare investigations, select repairs on development evidence, then open later panels |
| `research/direct_investigation.py` | Validate direct query plans, execute native measurements, retain typed receipts and control what later model calls can see |
| `research/native_conformance_tasks.py` | SQLite, LRU and UTF-8 contracts, public examples, fixed tests and later cases |
| `research/client_investigation_study.py` | Acquire an investigation history, compile two rival testers, freeze them and compare later client investigations |
| `research/client_investigation_tasks.py` | Opaque SQLite client workflows, public query grammar, native measurements and withheld implementation custody |
| `research/continuation_learning.py` | Fit rational linear models from measured histories and continuations, preserving the witness that motivates refinement |
| `zenith/investigation_program.py` | Run proposed Python under explicit syntax, acquisition and resource limits |
| `zenith/budgeted.py`, `zenith/provider_policy.py` | Pin an eligible model route, reserve costs and bound host/endpoint concurrency |
| `zenith/source_snapshot.py` | Archive the exact implementation used by a study |
| `scripts/build_conformance_report.py` | Publish allowlisted evidence and replay the archived runtime without inference |
| `scripts/continue_conformance_budget.py` | Preserve a terminal funding stop, verify exact settled responses and continue only unattempted calls under an explicit larger reservation ceiling |
| `scripts/export_site_snapshot.py` | Derive static public API responses, assets, `llms.txt`, the agent map and route index from the existing read-only backend; publish each mission/profile without browser execution |
| `scripts/build_client_investigation_report.py` | Export exact client-study records, derive lifecycle costs and replay the archived runtime with strict or explicitly behavioral comparison |
| `scripts/analyze_progress_campaign.py` | Check paired comparisons and reconstruct scores and costs from recorded outputs |
| `scripts/demo_continuation_learning.py` | Reproduce the learner repair and eight authored native configurations without API access |
| `examples/continuation-memory/witness-preserving-v1/` | Finite learner results and source hashes |

An investigation returns queries, not asserted answers. The host measures the native source and executes the parent independently. A verified disagreement becomes evidence for whole-program repair. The repair is selected using only public examples and that arm's measured observations; each previously correct measured case must remain correct. Source and selections freeze before later evaluation. This preservation rule is finite: it cannot guarantee correctness on new inputs.

The direct interface lets the model spend its response on experiment choice instead of implementing a cursor in Python. A batch arm gets one call; paired adaptive and outcome-masked arms share the same first response, then differ in the outcomes visible at the second call. Each arm reexecutes and pays for its own native measurements. Fixed tests and repair without new tests remain simpler controls. See the [prospective comparison](progress-protocol-20261014.md).

The continuation learner is a separate exact-arithmetic mechanism. A history is represented by what selected future continuations reveal about it. When a finite challenge refutes the fitted model, both the history and its distinguishing continuation must survive refinement. Its authored linear hypothesis class and finite challenge set limit what a successful fit establishes. Placing this learner beside model-driven investigation does not establish learned transfer between them.

The client pilot tests a concrete connection between investigation and reuse. A development transcript supplies both a retained diagnostic procedure and an ordinary reusable tester. Their executable code freezes before later client measurements. Fresh investigators with and without that transcript, and a fixed tester, provide controls. Every arm receives the same public target contract and native measurement interface. Source hashes and SQL work counters belong to the audit record and never enter model context. The pilot uses authored batch-import and transfer clients within SQLite; its later panel characterizes client defects, not an investigator's prediction accuracy. The [v1 result](client-investigation-20261014.md) preserves the failed compiled reuse. The [v2 protocol](client-investigation-protocol-v2-20261015.md) separately clarifies permission to propose unmeasured questions. The [working low-reasoning condition](client-investigation-v2-low-20261015.md) retains two constant-query testers: both detect three of four faults, while fixed tests detect all four. This is code reuse, with no acquired adaptive policy advantage.

# Architecture

**Historical architecture.** The financial profile runs the full
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
