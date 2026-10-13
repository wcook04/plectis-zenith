# Reasoning that can be inspected and tested

Zenith's unit of learning is a change to a reasoning step. A forecast can be
wrong because evidence was unavailable, a reader discarded a useful distinction,
a synthesis made an unsupported inference, or an otherwise defensible model
encountered an unpredictable outcome. Oracle must distinguish those possibilities
before Evolve proposes a repair. Predictive success on the first run is not the
condition for exercising that loop.

The `financial` task profile binds the existing full Lab, Oracle and Evolve
graphs to the historical basket task. It keeps their node identities and Lab edges, adds explicit subject-graph access to every Oracle reasoning stage,
replaces the domain prompts and validates a common reasoning ontology. The older
18-node basket mission is a separate pilot, not this full-graph experiment.

| Stage | Typed result | What can be checked |
|---|---|---|
| Inventory | Available views and missing inputs | Scope, cutoff and source identity |
| First-pass extraction | Evidence claims, distinctions and questions | Source references resolve; contrasts survive compression |
| Synthesis | Prioritised distinctions | Disagreements and dependence remain explicit |
| Orientation | Competing hypotheses and proposed tests | A test could distinguish the alternatives |
| CP1 plan | Six cross-universe numerical queries | Exact target coverage, available operations and lags |
| Directed pass | Candidate ID, verdict and reasoning | Candidate identity and cutoff-valid numerical receipt |
| CP2 decision | Selected candidate IDs and rationale | Numeric code supplies a complete forecast vector |
| Integrity | Issues across the saved reasoning | Schema validity and forecast mapping |
| Oracle lane review | Categorised failure hypotheses | Exact subject trace, later error and information boundary |
| Attribution and critique | Located failures and competing diagnoses | Earliest supported failure versus outcome noise |
| Evolve | One instruction change with predicted effect | Existing node, evidence reference, bounded instruction |
| Replay and later tests | Changed outputs and forecast errors | Frozen unaffected records, sampling control, later comparison |

Every reasoning response has `schema_version`, `node_id`, `stage`, `reasoning`
and `result`. The reasoning object contains typed claims, distinctions and
uncertainties. Claims have local identifiers (`C1`), a kind, statement, evidence
references and a stated epistemic status. A full identity is `node_id:C1`.
Distinctions (`D1`) ask a question with at least two explicit alternatives and
record whether it remains unresolved. These are inspectable assertions, not a
claim to expose a model's private internal computation.

Before a call, code assigns node-scoped evidence IDs (`E<namespace>_001`, etc.) to actual input values.
The API receives a strict JSON Schema whose reference enum contains only this node’s IDs. Upstream IDs belong to a different namespace. The model selects these IDs; every claim must cite at least one. Each persisted reference resolves through its
`evidence_catalog` to a source node, data-relative JSON Pointer and value hash.
Models do not manufacture source paths. Unknown IDs and changed bindings are
rejected. Resolving a reference establishes provenance, not that the cited
source logically entails the claim. `observed`, `supported`, `tentative` and
`unknown` are stated epistemic labels, not calibrated probabilities.
The executable schemas live in `zenith/financial_reasoning.py`;
`scripts/build_reasoning_schemas.py` exports them for the read-only API.

Current-role instructions are sent as a system message. The quoted graph's node instructions are input data for inspection, not commands to execute. This distinction matters particularly when Evolve reads the instructions of the Lab node it is meant to edit.

Each node has one provider attempt. A malformed response is preserved with its
exact input context and failure. It stops that execution; there is no automatic
repair prompt or retry. Fixing a prompt, evidence interface or schema is a
separate implementation change followed by a newly identified experiment.
Wrong but valid forecasts proceed to Oracle.

The six financial views contain constituent returns, basket breadth, market
indices, volume, cross-basket lag candidates and quote quality. Their legacy node
names remain stable; `events` does not mean news, and `interventions` does not
mean an observed economic intervention. All targets can query all baskets and
the shared history. Seed sees the inventory; source readers see their views;
the directed pass uses numerical tools against the preserved cutoff store.

CP1 freezes the record of the investigation, not a mandatory causal thesis.
CP2 can reject a hypothesis after testing it. Numeric code owns candidate-target
mapping, forecasts and defaults. Oracle receives the complete Lab graph: node
roles, instructions, dependencies, consumers, typed output contracts and any
applied instruction change. It also receives the original feeds, every saved
reasoning output and hash-bound input bindings. Those bindings reconstruct each
node's exact model-visible data without repeating every upstream record in full.
Later observations remain separate from this frozen subject record. It classifies evidence absent, evidence discarded, inference
error, numerical model error, irreducible uncertainty, or no supported failure.
Those classifications are hypotheses, even when supported by exact references.

Evolve stages a candidate policy without changing the source dossiers. Its updater receives the selected node’s actual instructions, original inputs and output when writing the candidate. A local
replay copies unaffected artifacts byte for byte and executes only the changed
node and its descendants. An empty-instruction replay gives a sampling control.
Both are development evidence: the outcome was used to choose the repair. The
frozen instruction is then compared with the incumbent on predeclared later
cases, with both forecasts committed before the outcomes are opened. This small
experiment reports changes and regressions; it does not automatically adopt a
policy or claim general predictive improvement.

Run `python -m zenith plan lab --task-profile financial` to inspect the graph.
`python -m research.graph_failure_study prepare --data <audited-panel> --study
<new-directory>` freezes the experiment; `run --study <directory> --env-file
<explicit-local-env>` executes it with the authorized provider. Private runtime
inputs and credentials are not part of the public API.

Provider requests use [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs), require supporting endpoints, and bind the response schema into the request identity. Local validation still checks target coverage, candidate ownership and reference hashes. The schema constrains format and identities; it does not certify claims or diagnose forecast errors.
