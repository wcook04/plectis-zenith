# Skills, context, and graph semantics

The Lean model proves that contract-preserving skills compose, safe subject-side contexts can be joined, and any graph whose edges strictly increase a natural-number rank has no nonempty cycle. A new edge preserves that rank certificate when it points to a greater rank. An output check refines the original skill; it preserves the original behavior in both directions only when the checked condition was already guaranteed.

These are structural and conditional contract results. They do not prove that an LLM obeys a prompt, produces a correct forecast, or improves through a topology experiment.

## A small skill ontology

A skill is a parameterized nondeterministic relation:

```text
Skill Parameters Input Output = Parameters -> Input -> Output -> Prop
```

For fixed parameters θ, `skill θ input output` means that the modeled operation permits that input/output behavior. It can permit several outputs or none. Parameters can represent a skill rule, incoming-edge priorities, context budget, model choice, or other experimental controls; they need not be neural weights or differentiable quantities.

Input and output types represent contracts at ports. The Python projection records each canonical node's incoming output-schema labels as `input_sorts`, its own `output_sort`, source references and instruction hash, parameter declarations, and named pre/postcondition references. These labels and references are declarations. Connecting matching labels does not prove that the emitted bytes satisfy the schema, and a schema validator does not establish predictive truth. Runtime validators and dated evidence supply separate obligations.

`compose first second` permits an output precisely when there is a shared intermediate value permitted by both skills. Parameters are paired, so each operation keeps its own controls. `composition_contract` proves the usual handoff rule: if the first operation sends every input satisfying its precondition to an intermediate satisfying the second operation's precondition, and the second guarantees the final postcondition, their composition guarantees the final postcondition.

`Refines candidate reference` is behavioral inclusion: every candidate behavior is permitted by the reference. `composition_refines` proves that refining both stages refines their composition. This is a safety statement. An empty relation refines every relation, so refinement alone cannot establish liveness, useful output, accuracy, or improvement. Finite forecast scores measure a separate empirical property.

## Evidence available before a cutoff

An evidence record has an `availableAt` natural-number tick and a class: `subject_side_evidence` or `truth_side_evidence`. A forward-safe record was available at or before the frozen cutoff and belongs to the subject-side class. A safe context consists entirely of forward-safe records.

Lean proves that safe context membership implies availability before the cutoff and excludes truth-side evidence. `safe_context_append` proves that joining two safe contexts remains safe. This is the obligation for a new incoming edge in forward prediction: both its source records and the existing context must satisfy the same cutoff and class boundary.

The executable checker accepts integer ticks or timezone-aware ISO timestamps with whole nonnegative epoch seconds. It rejects future availability and truth-side records in forward mode. Oracle can inspect truth after it becomes available under its own hindsight cutoff; that does not make the same record available at Lab's earlier prediction cutoff. Oracle's subject-grounded CP2 evidence dictionary is also distinct from its permitted hindsight reasoning context.

Classes and timestamps must come from trustworthy capture. Declaring future truth to be subject-side evidence will not become an honest forecast because a structural checker accepted the declaration. The runtime and feedback lanes retain provenance, actual availability, and independent admission requirements.

## Topology changes

`Ranked edge rank` means that every edge from source to target has `rank source < rank target`. Along a nonempty path the rank strictly increases. A path returning to its source would imply `rank source < rank source`, which is impossible. This is the mechanism in `ranked_graph_acyclic`.

The finite rank certificate is:

```json
{
  "schema_version": "zenith_graph_rank_certificate_v1",
  "node_ids": ["feed", "lab", "check"],
  "edges": [
    {"dependency_id": "feed", "node_id": "lab"},
    {"dependency_id": "lab", "node_id": "check"}
  ],
  "ranks": {"feed": 0, "lab": 1, "check": 2},
  "condition": "rank(dependency)<rank(node)"
}
```

Adding `feed -> check` preserves this certificate. Adding `check -> feed` fails it; adding a self-edge fails it. The Python validator also rejects unknown endpoints, duplicate edges, missing ranks, negative ranks, and booleans presented as integers. An existing rank assignment is a sufficient certificate, not a claim that every rejected edge creates a cycle: some acyclic rewrites need a new rank assignment. The topology variant owner recomputes ranks from the changed graph before admission.

An inserted check models `skill input output AND post output`. `checked_refines` proves that this filters behavior; it can remove outputs. `checked_preserves_when_guaranteed` proves the reverse inclusion under the explicit hypothesis that the original skill always satisfies `post`. Inserting a meaningful new check need not preserve every previous outcome; rejection may be the intended change.

Splitting a node into two operations requires an intermediate contract and the same witness used by relational composition. Replacing a skill with those operations preserves behavior only when the proposed factorization establishes both behavioral inclusions. The current model proves composition and refinement rules; it does not infer a factorization from natural-language instructions. A topology experiment must supply the new contracts, runtime implementation, and empirical evidence.

## Check the actual extracted graph

From the repository root:

```sh
python3 scripts/check_semantics.py
python3 scripts/check_semantics.py --lean --output work/semantics/current.json
python3 scripts/check_semantics.py --spec work/semantics/current.json --lean
python3 scripts/check_semantics.py --rank-certificate work/variant-validation.json --lean
python3 -m unittest discover -s tests -p 'test_semantic_contract*.py' -v
```

The generator reads canonical node sources through the existing `PhysicalLoader`, obtains wave ranks through the existing governance implementation, and records source hashes. It verifies declared input ports against dependencies and upstream output sorts. Oracle-group outputs are conservatively classified as truth-side context; Lab nodes are forward-only. More detailed evidence-class and timestamp assertions belong to the actual artifact receipts and `--evidence/--cutoff` check, not this group-level approximation.

`--rank-certificate` accepts either the direct certificate or a topology validation receipt containing `acyclic_certificate`. `--evidence records.json --cutoff 2025-01-01T12:00:00Z` checks recorded context; add `--hindsight` only for a truth-permitted hindsight operation.

`--lean` uses the preinstalled `leanprover/lean4:v4.30.0` toolchain and never installs dependencies. It encodes each vertex as its exact canonical node index paired with its certified rank, appends the finite vertices and edges to `formal/ZenithSemantics.lean`, proves the finite boolean certificate with `decide`, and invokes the proven checker-soundness and acyclicity theorems. The temporary generated instance is compiled and its theorem axiom dependencies audited. The receipt binds the source and certificate hashes and reports Lean acceptance separately from Python validation.

All named model theorems have compiled without axioms or unproved placeholders. The generated graph checker emits `lean_accepted` only after its finite instance also compiles and passes the axiom audit. Pure Python test runs do not establish Lean acceptance; use the explicit `--lean` command for that evidence.

The checked-in `formal/verification.json` records acceptance of the canonical **71-node, 205-edge** instance. `formal/variant-verification.json` records the inserted-check **72-node, 206-edge** certificate passing Python validation, but its exact finite Lean invocation timed out after 120 seconds and remains unverified. The general rank/acyclicity proofs are accepted; that does not replace kernel acceptance of a particular generated certificate. No broader generated-variant acceptance is claimed.

## Source and propagation boundary

This is a small formal interface for the existing Zenith reasoning-node contract vocabulary, taken from the extracted `codex/standards/std_node_reasoning.json`, canonical node `meta.reasoning_contract` overlays, and their output schemas. The underlying relational composition, contract handoff, and increasing-rank argument are elementary mechanisms, not a claim of new mathematics.

The canonical definitions and proofs live in one Lean file. The executable consumer is `scripts/check_semantics.py`; `docs/semantics.md` explains the mechanism; tests exercise the concrete invalid edges, cutoffs, sorts, and axiom-audit boundary. Research and topology variant receipts consume the same contract vocabulary. No research paper, public mathematical corpus, external comparison platform, or hosted review submission is selected by this software-interface task. Those destinations remain outside its scope; compilation does not constitute external review or acceptance.
