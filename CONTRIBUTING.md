# Contributing

Read [AGENTS.md](AGENTS.md) and [the architecture](docs/architecture.md),
then use [the reproduction guide](docs/reproducing.md) to check your setup.
Make a focused change with a concrete problem and the commands that verify it.
Runtime changes need the offline test suite. Graph or contract changes also
need `python -m zenith validate`, the node-skill check and the semantic check.

Keep failures, missing data and pending agent packets visible. A synthetic
test does not establish market performance. Experimental changes follow
[program.md](program.md): declare the hypothesis, freeze inputs and evaluator,
record every attempt, and keep development selection separate from final
assessment. Do not automatically promote a favorable result into live policy.

Use synthetic fixtures for regression tests. Do not submit credentials,
runtime state, private prompts or provider data. Retain upstream licenses,
notices, attribution and immutable source pins. Review changes to imported
originals separately from changes to native adapters.
Contributions to native software use the repository's Apache-2.0 license;
dataset and retained third-party licenses remain separate.

The backend projection is generated from the authored graph. Change its source
and regenerate `data/graph/public-graph.json` through
`python scripts/build_demo_data.py`, then run the same command with `--check`.
Do not edit generated graph JSON by hand. The local read-only API runs with
`python -m zenith serve --host 127.0.0.1 --port 8765`. API changes need
`python -m pytest tests/test_graph_api.py tests/test_demo_export.py`.
A local contribution requires no provider call or deployment. A separate
frontend can use [the frontend handoff](docs/frontend-handoff.md); this repository
ships no frontend.

For a public contribution, use a pull request on the repository that supplied
this checkout. The project does not yet specify a canonical public remote.
Security reports follow [SECURITY.md](SECURITY.md).
