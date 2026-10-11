# Reproduce from a source checkout

The verified distribution is an editable source checkout. Keep the authored
node JSON, contracts, skills and data next to the Python packages. A wheel
installation is not a verified substitute for this layout.

The [source reproduction receipt](source-reproduction.json) records a fresh
clone and Python environment at runtime commit `01522cc`: 16 passing checks,
including 85 targeted tests, without private parent imports or credentials.
It is a same-host check of that revision, not an independent-machine result.

Use Python 3.12 for the pinned environment. From a fresh checkout:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-test.lock
python -m pip install --no-deps -e .
python -m pip check
python -m zenith validate
python -m zenith plan lab
python scripts/build_node_skills.py --check
python scripts/check_extraction.py
python scripts/check_semantics.py
python -m pytest tests
python -m benchmark.run --output work/benchmark/benchmark.json
```

Dependency installation requires package-index access. The commands after
installation use repository sources and synthetic or included historical
fixtures; they require no market credentials or model calls. The benchmark
writes only to ignored `work/` and reports forecast error, not trading returns.
Its dataset attribution is in [data/historical/ATTRIBUTION.md](../data/historical/ATTRIBUTION.md).

Regenerate and check the authored-graph projection at
`data/graph/public-graph.json` with:

```sh
python scripts/build_demo_data.py
python scripts/build_demo_data.py --check
```

Serve the same reviewed graph through the local read-only API:

```sh
python -m zenith serve --host 127.0.0.1 --port 8765
```

In another terminal, read service readiness and a native mission scope:

```sh
curl http://127.0.0.1:8765/api/v1/health
curl http://127.0.0.1:8765/api/v1/missions/lab
```

Stop the service with Ctrl-C. It takes an in-memory source snapshot at startup;
restart after source edits. Service readiness describes the API, not completed
graph execution. This command reads graph metadata without opening runs or
calling a model. The repository contains the backend and no frontend.

For a separate frontend at `http://localhost:5173`, add
`--allow-origin http://localhost:5173`. Repeat the flag for each exact allowed
HTTP(S) origin; omit paths and credentials. Cross-origin browser access is
disabled by default. See [the frontend handoff](frontend-handoff.md) for response contracts
and the native CLI execution boundary.

`python scripts/check_semantics.py --lean` adds formal compilation and requires
the toolchain pinned in `formal/lean-toolchain`. Installing that toolchain is a
separate network step. The ordinary semantic check verifies finite declared
graph conditions; neither check proves that an LLM follows its skill.

For explicit feed or model execution, use [provider setup](providers.md),
[the native architecture](architecture.md) and the command's help. Acquired
data and provider outputs remain local. The software license does not settle
their redistribution rights.
