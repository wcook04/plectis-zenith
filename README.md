# Plectis Observatory

Inspect the evidence behind a market-model experiment: where the data came from, what was available at prediction time, and how its errors compare with simple baselines.

This is a standalone, dependency-free research demo. The first benchmark uses the licensed UCI Dow Jones Index dataset from 2011. It measures next-week direction probability with Brier scores, not investment returns. Its small, fixed historical sample does not establish a profitable strategy. The private prospective collection system is optional and separate.

## Reproduce and run

Python 3.11 or newer; no packages or API keys required:

```sh
python3 -m benchmark.run --output web/data/benchmark.json
python3 -m unittest discover -s tests -v
python3 -m observatory.serve --port 8768
```

Open http://127.0.0.1:8768. Select a model or week to inspect the measured score; select a stage of the pipeline to see its evidence. The JSON and per-prediction CSV are downloadable from the page.

To connect an existing private collector locally:

```sh
python3 -m observatory.export --source-root /path/to/ai_workflow --output web/data/operations.json
python3 -m observatory.serve --port 8768 --source-root /path/to/ai_workflow
```

The bridge exports aggregate feed health, experiment counts and model identities. It excludes current asset probabilities, recommendations, raw market records, prompts, provider responses, credentials and private repository text. The server binds to localhost by default and serves only `web/`.

On macOS, keep the local preview available after login with `python3 scripts/preview_service.py install --source-root /path/to/ai_workflow`. Inspect it with `python3 scripts/preview_service.py status`; remove it with `python3 scripts/preview_service.py remove`. This only serves the local site. The collector owns the exchange schedule and API calls.

## What is here

- `benchmark/`: frozen historical protocol, independent label checks and deterministic baseline evaluation.
- `data/historical/`: pinned input, source manifest and dataset attribution.
- `observatory/`: allowlisted aggregate export and local preview server.
- `web/`: static interface, benchmark results, evidence pipeline and source disclosures.
- `tests/`: leakage, reproducibility, provenance and export-boundary checks.
- `docs/research-boundary.md`: UK primary-source research and public-release considerations.

The historical benchmark and the private live experiment answer different questions. No historical LLM score is presented: a modern model may have seen these old observations during training. The live loop freezes predictions before later truth, records the actual OpenRouter model rather than merely the router alias, and retains failures.

## Data and release status

The UCI input is CC BY 4.0; see its attribution and source manifest. Software licences do not grant rights to redistribute a provider's market data. Additional SEC or macro-vintage sources need their own availability, revision and reuse checks.

This is a local preparation repository, not a publicly deployed financial service. It offers factual historical experiment results and no investment recommendations. A disclaimer alone cannot determine UK regulatory status; review the actual interface, distribution and marketing before a public launch. The working name has not undergone a trademark search.
