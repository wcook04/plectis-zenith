# Frozen reasoning graph variants

The canonical JSON nodes remain the source. A variant overlays a cloned graph and passes a `FrozenGraphLoader` to the existing `GodModeEngine`. Scheduling, group closure, artifact persistence, provider prompts, CP1/CP2 validation and failure handling remain the engine's operations.

```sh
python -m variants --variant examples/variants/lab_evidence_check.json
python -m zenith plan lab --target lab_decide --graph-variant examples/variants/lab_evidence_check.json
```

The example adds `lab_evidence_check` after `lab_orient` and reroutes the orient→decide edge through that check. All other Phase 1 dependencies remain. Lab gains one reasoning node and one wave; CP1, CP2 and integrity output contracts remain intact. The check's actual emitted artifact enters CP1's prompt. Its effectiveness is an experimental question, not a claimed improvement.

A file has exactly `schema_version`, `variant_id`, `base_graph_sha256`, `base_node_hashes`, `operations` and `variant_sha256`. The variant hash uses canonical sorted compact UTF-8 JSON excluding its own hash field. Base identity covers all hydrated nodes, including contract metadata, instructions, configuration, dossier injection, grouping and dependencies. A changed source graph requires a newly bound experiment.

Typed operations are:

- `add_reasoning_node` with a full canonical `node` and `meta.reasoning_contract`.
- `add_edge` or `remove_edge` with `dependency_id` and `node_id`.
- `remove_experimental_node` with the id of a node added by this variant, after its dependent edges are removed.

New skills declare every input, inherit the source reasoning-contract vocabulary, use an existing validated output schema or `text`/`json`, and permit no external actions, commits or tool calls. New instructions are limited to 2,048 characters. Learned rule addons belong in frozen reasoning policies and are limited to 512 characters. A graph variant changes topology; a reasoning policy changes prompt context weights and short takeaways.

Validation rejects unknown fields, malformed contracts, duplicate/dangling edges, cycles, base-node replacement/removal, tool/feed topology changes and lost base dependency ancestry. A removed base edge is allowed only when another dependency path retains that source's ancestry. All Oracle/refinement ancestry is excluded from forward Lab and surveillance nodes, including through intermediaries. Output schema and other base contracts cannot be changed by these operations.

The receipt records source/variant/effective graph hashes, added nodes/edges, rerouted edges, waves and a rank certificate. It does not authorize source writes or infer that a model will obey its contract. Runtime output validators still decide acceptance.

```sh
python -m variants --variant examples/variants/lab_evidence_check.json > work/variant-receipt.json
python scripts/check_semantics.py --rank-certificate work/variant-receipt.json --lean
```

The generated finite rank witness connects these exact topology edges to the Lean acyclicity checker. The formal result covers the stated graph/contract model; it does not prove market predictions, learned-rule usefulness or provider compliance.

## Explicit compact predictor

`variants/predictor.py` owns a distinct `zenith_predictor_replacement_v1`
contract. Its admitted profile is `stocknet_price_only_cp1_cp2_v2`.
It binds the complete source graph identity, then retains `global_stock_feed`,
`lab_decide` and `lab_director`. The stock tool is unchanged; CP1 and CP2 retain
their native schemas, with standardized price-only instructions and explicit
dependencies replacing references to removed miners and feed lanes. The
resulting loader still executes through `GodModeEngine`.

This is a declared ablation, not a new permission to remove arbitrary base nodes
through ordinary graph variants. Its receipt lists removed nodes, effective
node hashes, waves and a finite rank certificate; `base_ancestry_preserved` is
false. Each reasoning node has one attempt and no tool calls. A separate frozen
policy can vary one short skill rule while keeping the profile fixed. See
[the native backtest protocol](native-backtest.md). Empirical refinement of the
default Lab and compilation of this exact replacement's Lean instance are not
implied by its Python topology checks.

The original `v1` instructions are retained in Git at `c4c051c`, together with
their failed compatibility-run provenance. Profile `v2` makes the existing
minimum lengths and bracketed citation format more explicit in the prompts.
The validators and required outputs are unchanged; old attempts are not
rewritten or resumed against the new profile.

After an intentional canonical source change, maintainers can regenerate only
the checked-in teaching example with `python scripts/build_example_variant.py`.
The script uses the graph owner's identity and validation functions. Frozen
experiment variants must retain their old source pins; initialize a new
experiment instead of applying this operation to historical evidence.
