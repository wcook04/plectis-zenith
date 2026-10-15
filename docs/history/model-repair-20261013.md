# Model, cost and task repair — 13 October 2026

Historical research record. References to “current” or “next” describe this stage; see [today’s findings](../status.md).

The original high cost came from explicit selection of GPT-4.1 and very large requests. It was not evidence of a provider overload forcing a model fallback. The twelve-call episode used 635,022 input tokens and 3,411 output tokens, served by Azure, for $1.243572. Two reviews each consumed about 180,000 input tokens. A separately versioned correction cost another $0.375084. The [machine receipt](model-repair-20261013.json) is rebuilt from the retained ledgers by `python -m research.model_repair_report`.

## Enforced operating policy

New inference allows only inexpensive Chinese-developed models. GPT-4.1 and all non-allowlisted model developers are rejected before metadata lookup or transport. Automatic model selection uses the newest eligible release in the live catalogue, within 180 days, with the required text and structured-output interface. Current ceilings are $0.50 per million input tokens and $1.50 per million output tokens, including conditional endpoint tariffs; per-request fees are disallowed. Catalogue and pinned endpoint rates are verified separately. The reservation uses the larger relevant tariff, rather than mistaking the catalogue's cheapest host for every host's price.

A host-wide process and thread lock permits one Zenith inference request at a time across updated checkouts. There is no expensive-model fallback or automatic retry. An unavailable or incompatible selected endpoint stops the attempt. Free automatic routers and unpriced NVIDIA adapters are disabled. This governs experiment API traffic, not the model running the development chat. Historical paid-model receipts remain evidence.

## What the new calls established

The modern-model investigations used **13 charged calls for $0.046824887272**, across different workloads and interface versions. This is not an equal-workload overall comparison.

| Condition | Calls | Reported cost | Result |
|---|---:|---:|---|
| DeepSeek V4.1 Flash, original reviewer request unchanged | 1 | $0.0089158404 | Correct numerical ordering; still proposed a preventive change without establishing an observed defect |
| DeepSeek, fresh native Lab | 8 | $0.014634650472 | Completed investigation; six zero forecasts, unchanged MSE 0.000642668662; review input exceeded the byte cap before another charge |
| DeepSeek, lossless review of that Lab | 1 | $0.0041206164 | Completed; incorrectly treated three used recipes as exhausting the 21 legal source/summary combinations |
| Qwen 3.8 Omni Flash, component calibration | 1 | $0.00045104 | All 16 answers semantically correct, but returned an array instead of the required object: retained as a format failure |
| DeepSeek, same component calibration | 1 | $0.0003066 | Valid format and 16/16 correct |
| Qwen, review with explicit capability inventory | 1 | $0.01839614 | Returned no change; still incorrectly described neutral zero forecasts as directionally correct for falling baskets |

Two other calibration preparations stopped before inference: Baidu was unavailable when checked again, and the direct DeepSeek endpoint did not advertise the required strict-output capability. Neither triggered an expensive fallback. The successful DeepSeek calibration used DeepInfra. Endpoint availability is time-dependent; these pins are observations, not permanent defaults.

## Context and evaluation repairs

The reviewer previously received nested copies of the same observations, tool outputs and full prompts. A lossless evidence bank now stores each value once and supplies exact references. The inspected subject shrank from 2,115,068 to 258,745 serialized bytes; every original context round-trips exactly and altered hashes are rejected. The resulting review request was about 268 KB. This fixes duplication, not semantic overload or model comprehension. The reviewer also receives the legal source/summary inventory, used recipes and remaining allowance. New study protocols archive the runtime source before inference.

The separate calibration asks four tractable questions: rank supplied validation errors, match forecast and outcome intervals, determine whether a selection-only action set can express a negative forecast, and distinguish mandatory rules from advice. A deterministic reference already solves these typed cases. Sixteen correct answers therefore establish only this component's basic interpretation under this input format. They establish neither a need for an LLM nor transfer to long unstructured investigations, useful learning or forecasting advantage. The scorer ignores harmless comma whitespace but retains schema failures and exact serialization separately.

The ten supplied research returns were previously assimilated and tested: the [audit](research-returns-20261013.md) remains their authority. Their diagnosis of restricted action expressivity remains relevant. In the older February catalogue all 720 permitted target-query forecasts were positive; a selection-only repair could not produce negative forecasts. A bad result may reflect missing information, inadequate tools, an inexpressive action family, faulty interpretation, or an unsuitable task. These are distinct testable explanations.

## Next research boundary

The immediate learning target should be an information-sufficient, useful decision with a verifiable outcome: for example selecting an investigation, ranking evidence-backed risks, or deciding which forecast to trust. These are candidate task families, not a selected new benchmark. Tiny arithmetic checks are calibration, not the final ambition. A research proposal must identify where language adds value over code and what evidence the agent actually has when deciding.

No modern-model procedure was adopted; no better forecast or protected-case learning was demonstrated. The next experiment needs a justified task, simple competitive baselines, a frozen budget and feedback intervention, and fresh cases protected from proposal selection. The old market case is retained as a stress test, not treated as proof that the broader programme is impossible. Further architectural complexity must earn its cost.
