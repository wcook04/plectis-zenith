# Actual graph diagrams

These SVGs are generated from the current native node JSON. Open the linked figure
and zoom to inspect the exact IDs. Each dependency panel shows a produced node and
all its immediate prerequisites. Repeated cards refer to the same artifact; each
declared edge appears once. Integrity's 20 inputs occupy two continued panels.

| View | Native nodes | Declared edges |
|---|---:|---:|
| [Full Lab](graphs/lab.svg) | 28 | 98 |
| [Full Oracle](graphs/oracle.svg) | 31 | 57 |
| [Evolve and daily review](graphs/evolve.svg) | 3 | 2 |

![Full native Lab dependency atlas](graphs/lab.svg)

![Full native Oracle dependency atlas](graphs/oracle.svg)

![Native Evolve and reviewed daily workflow](graphs/evolve.svg)

Solid arrows are exactly the `dependencies` fields under
`codex/substrate/nodes/{feeds,lab,oracle,refinement}`. They describe artifact
consumption, not every injected context item or execution-time source binding.
Lab binds feeds to its issue snapshot. Oracle binds `oracle_subject_*` tools to
the original Lab and `global_*` tools to later truth. Its subject-grounding rules
still govern reconstruction. See `zenith/daily.py::checked_run` and the engine's
tool hydration; the atlas does not invent dependencies for these bindings.

The Evolve figure separates the native dossier DAG from the daily controller's
reviewed policy path. Dashed arrows connect workflow steps, not native nodes.
`run_evolve.py::export_agent_handoff` exports pending analysis with source
bindings. `daily.py::compile_review` freezes a candidate or no-change decision.
The next development Lab may use that candidate; later `daily matchoff` and an
explicit `daily retain` decision govern retention. Neither an Oracle diagnosis
nor a candidate review establishes improvement. Native dossier mutation is a
separate explicit application path.

Regenerate without extra dependencies:

```sh
python3 scripts/build_graphs.py
```

The builder checks full node and edge coverage. Each SVG embeds the exact edge
inventory and SHA-256 hashes of the source node files in its metadata.
