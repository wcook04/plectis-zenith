# Bring your own provider key

Each person supplies their own OpenRouter or NVIDIA key. This repository includes no account credentials and does not load another checkout's environment. Keys stay in process environment or an explicitly selected local `.env`; they are not command arguments, model prompts, exported configuration, or durable provider receipts.

Install the project dependencies first. To use a private environment file:

```sh
cp .env.example .env
chmod 600 .env
```

Edit `.env` locally with your own key. `.env` is ignored by Git. Existing process environment takes precedence; values are not interpolated, and only the supported provider variables are loaded. Environment files are never discovered automatically.

Alternatively, set the key through your shell's secret input mechanism. For a one-command Python session, `getpass` keeps the value out of command history:

```sh
python -c 'import getpass, os; from zenith.cli import main; os.environ["OPENROUTER_API_KEY"] = getpass.getpass("Your OpenRouter key: "); raise SystemExit(main(["provider", "doctor"]))'
```

The key disappears when that process exits. To execute a mission in that same session, replace the final `main` arguments with the mission command you intend to run.

## OpenRouter: current verified free models

```sh
python -m zenith provider doctor --env-file .env
python -m zenith provider models --env-file .env
python -m zenith provider doctor --offline
```

The default check fetches the public model catalogue **without an authorization header**. It reports only whether a key is configured, the eligible model IDs, context lengths and supported parameters. It sends no inference request. `--offline` performs no network request. An optional `--check-key` explicitly sends the key to the official key-status endpoint; daily limits remain unknown unless that response supplies them.

A `:free` suffix is a candidate, not proof of availability. The exact requested ID must exist once in the current catalogue, prompt and completion pricing must both be present, and every present pricing field must be numeric, finite and zero. Missing, unknown or nonzero pricing blocks this free adapter. It supports no paid gate, paid fallback, or paid plugin. [OpenRouter free variant documentation](https://openrouter.ai/docs/guides/routing/model-variants/free).

Choose a listed ID using `--model`, or set `OPENROUTER_CHAT_MODEL` in your environment file. `openrouter/free` is a router alias: the receipt records the returned actual model separately. Catalogue availability is checked again before each new inference attempt. Context length is recorded; the input guard uses a disclosed characters/4 estimate, not exact tokenization.

```sh
python -m zenith run lab --run-id MY_LAB --feed-source MY_RECORDED_FEEDS \
  --provider openrouter_free --model CURRENT_CATALOGUE_ID \
  --env-file .env --context-profile compact_feeds --horizon next_us_close
```

This command sends the prepared mission prompts to the provider. Inspect and select your local feed inputs before executing it. Metadata checks and an available free model do not establish available quota or successful inference. [OpenRouter limits documentation](https://openrouter.ai/docs/api_reference/limits).

## OpenRouter: explicitly bounded paid trials

`openrouter_budgeted` is a separate opt-in adapter. It requires your own key, an explicit concrete model ID, maximum USD cost, maximum calls, output token cap, and one ledger directory shared by **every run in the batch**. The current trial ceiling is USD 0.25. Recurring free execution keeps using `openrouter_free`.

```sh
python -m zenith run lab --run-id MY_BOUNDED_LAB --feed-source MY_RECORDED_FEEDS \
  --provider openrouter_budgeted --model YOUR_CURRENT_TEXT_MODEL \
  --max-cost-usd 0.25 --max-calls 40 --max-output-tokens 1024 \
  --budget-dir state/budgets/my-first-batch --env-file .env \
  --context-profile compact_feeds --horizon next_us_close
```

Use the same `--budget-dir` and limits for additional run IDs in that batch. Limits are frozen in each run manifest and in the shared ledger; resume cannot raise them. Independent ledger directories represent independent budgets, so creating a new directory does not preserve a previous batch cap.

Before each new inference, a public unauthenticated catalogue lookup must confirm the exact text model, finite nonnegative prices, context length, and output limit. Prompt/completion prices are required; any present ancillary price must be known and zero, apart from a known request fee. Requests contain no tools, plugins, model fallbacks or routing aliases. The provider requires parameter support, disables provider fallback, and receives price ceilings for prompt/completion, request and image charges. [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection).

Before sending a request, the adapter takes a process lock and atomically saves its reservation. Input tokens are conservatively bounded by UTF8 prompt bytes **plus 4096 framing tokens**; the response bound is the selected output cap. The reservation includes both token prices and any request fee. All reservations remain charged against the client cap, including successful calls. Concurrent runs cannot reserve past the shared USD or call limit.

There is one network attempt per run/node. Original-engine repair prompts cannot make another paid call for that node. Successful exact responses are reused without inference or a key. Failed, interrupted or ambiguous requests are not resent. Missing/nonfinite actual cost, excessive reported tokens or cost, and transport failures halt the shared batch. Reservations remain held, and the response, requested/actual model identities, usage, reported cost and error remain auditable.

The USD limit is a **client reservation guard, not a server billing guarantee**. Token accounting, framing, provider behavior and the optional reported cost can differ from the client bounds. A response exceeding its reservation is recorded and halts further calls; the adapter cannot reverse an incurred charge. It does not infer a billed cost when OpenRouter omits `usage.cost`. [OpenRouter usage and cost fields](https://openrouter.ai/docs/api/reference/overview).

For a bounded research harness, inject `OpenRouterBudgetedProvider(run_dir, model, max_cost_usd, max_calls, max_output_tokens, budget_dir)` through the same provider interface. `ask_ai(prompt, config={"meta": {"node_id": "unique_case", "session_id": run_dir.name}})` returns the response text. Assign a unique node ID to each intended case; use one shared budget directory. `budget_status()` reports reservations and known cost, while `budget.json` contains every attempted identity and its full receipt. This harness does not establish native mission completion or forecasting accuracy.

## NVIDIA hosted NIM

```sh
python -m zenith provider doctor --provider nvidia_nim --env-file .env
python -m zenith run lab --run-id MY_NIM_LAB --feed-source MY_RECORDED_FEEDS \
  --provider nvidia_nim --model YOUR_SELECTED_NVIDIA_MODEL \
  --env-file .env --context-profile compact_feeds --horizon next_us_close
```

`NVIDIA_API_KEY` must be your own key. NVIDIA requires an explicit `--model`; no volatile model name or OpenRouter alias is supplied as its default. Select an available hosted model from [NVIDIA's official LLM API reference](https://docs.api.nvidia.com/nim/reference/llm-apis).

The connector uses only `https://integrate.api.nvidia.com/v1/chat/completions`. It records requested and returned actual model identity, usage and endpoint. Cost stays `null` when no verified cost is available. This integration does not create an account, provision paid access, check a free quota, or promise free inference. The doctor reports configuration and the official model reference; it does not contact an authenticated NVIDIA endpoint.

## Receipts and transport boundaries

Only the fixed official HTTPS API hosts receive credentials, and redirects are disabled. Error strings and persisted provider packets are redacted. Provider attempt and response receipts live under the local run's `handoff/`; API keys are not included. Every inference attempt starts with a durable receipt. An interrupted or failed exact attempt is not silently resent on resume; successful replies are reused, and original node validation still decides whether to accept them.

For execution without any provider key, use `--provider agent` and the packet/import workflow, or prompt-bound captured responses. These modes do not make network inference calls.
