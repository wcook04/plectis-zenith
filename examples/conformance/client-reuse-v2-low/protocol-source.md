# Client investigation v2: prompt delivery check

**Status:** separately versioned engineering follow-up on the already exposed SQLite client population. No v2 provider result is asserted here. This is a delivery check, not an independent efficacy comparison or evidence of transfer. The [v1 protocol](client-investigation-protocol-20261014.md), original responses, source archive and results remain v1 evidence and must not be overwritten or pooled with v2.

## Changed instruction

The v1 preparation prompt said “Use only that measured evidence.” A model could interpret this as requiring a target receipt before proposing any target experiment, even though the prospective target contract and full query grammar were supplied before compilation. The v2 prompt distinguishes two operations:

- Claims about observed client behavior require measured receipts. An old exact answer is not a measured answer for a new target.
- Proposing a new legal experiment may use the public contract and full query grammar, including when no target receipt exists. Development evidence may motivate questions; new target measurements may guide later choices.

Both the retained procedure and ordinary reusable tester receive the identical permission in their preparation system prompt. The direct investigators receive the same distinction, including during development. The function may emit its first legal query with an empty `target_receipts` list. Returning a null query or an empty direct query list still stops; the host neither suppresses a stop nor rewrites the response. The change supplies no particular query, target answer or implementation label.

## Fixed comparison and evidence boundary

The [v1 protocol](client-investigation-protocol-20261014.md) continues to define the tasks, grammar, native measurement, five arms, scoring, invalid-delivery treatment and accounting. V2 changes the prompt and its recorded version only. It repeats all five development batch clients and all five transfer clients, including the correct clients, with six query slots and one-query feedback cadence. The maximum remains 92 provider calls, including two preparation calls, under the same shared $2 hard ceiling. All arms retain their existing tools, budgets and observations. The evaluator, native task source, restricted executor and provider budget implementation are unchanged by this amendment.

Freeze the v2 protocol, source, full prepared population, model, pinned endpoint, reasoning setting, output limit and current official price evidence before inference. The v2 manifest uses `zenith_client_investigation_study_v2`, records `prompt_version: v2`, hashes both actual system prompts and this protocol, and retains a runtime source archive. Every provider attempt, raw output, delivery error, legal or invalid query, stop, native cost and elapsed time remains recorded. There is no retry or manual repair. A transport or budget failure leaves an incomplete study and keeps the protected panel sealed. A changed response or further prompt amendment needs another version and output directory.

The provider accounting remains the existing metered callback and shared budget ledger. Report development, preparation, target and full-lifecycle calls, all billed tokens and cost; count native work and policy executions separately. Preserve unsolved targets and their consumed allowances. Open the finite target panel only after the complete study is frozen. Exact replay uses recorded provider replies and archived source, with zero network calls.

## Interpretation

The engineering question is whether a model-generated artifact can select and execute a legal target query without already having a target receipt, while keeping factual claims source-bound. Report both preparation arms, every target, errors and stopping behavior. Offline fixtures establish delivery and custody behavior only; provider results are needed to observe the model's actual response to this prompt.

The tasks and earlier results have already been inspected. A v2 success would establish working delivery under the revised instruction on this known population. It would not be a fresh replication, an independent estimate of effectiveness, a learned-method advantage or transfer to a new project. A difference from v1 cannot isolate the prompt's causal effect because model responses and acquired development histories can also differ. Keep v1 and v2 tables and costs separately labeled.

## Commands and compatibility

Select the version before inference; `prepare` defaults to v2:

```sh
python -m research.client_investigation_study prepare /absolute/new-v2-output \
  --prompt-version v2 --model MODEL --provider-slug PROVIDER \
  --reasoning-effort none --max-output-tokens 12288 \
  --max-cost-usd 2 --model-evidence /absolute/checked-model-evidence.json
python -m research.client_investigation_study run /absolute/new-v2-output
python -m research.client_investigation_study replay /absolute/new-v2-output
python -m research.client_investigation_study open-panel /absolute/new-v2-output
```

`--prompt-version v1` selects the exact original system prompts and original protocol for a new freeze. This compatibility option does not make current source identical to an old source archive. Existing v1 evidence must replay with its frozen runtime; source verification must continue to reject replay against changed live code. V2 uses a fresh output directory and keeps its own complete archive.

The source owner is [`research/client_investigation_study.py`](../research/client_investigation_study.py); offline delivery, compatibility and replay checks are in [`tests/test_client_investigation_study.py`](../tests/test_client_investigation_study.py).
