# Native adaptive investigator

`financial_investigator_v1` is a new, explicitly named profile in the existing Zenith engine. It keeps the financial universe and historical profiles. One Lab investigator chooses inspect, compare or commit after receiving each preceding result. One combined Oracle/Evolve response diagnoses the recorded computation and proposes an exact replacement procedure, or no change.

## What executes

The native loader expands eight bounded action/result slots plus a cutoff feed and final commitment. Each active action runs through the existing engine provider, schema validator, failed-attempt capture, and artifact lifecycle. An early commitment makes the remaining slots explicitly inactive without model calls. The maximum graph is an execution scaffold, not a claim that all slots reasoned. Each successful Lab exports `execution_graph.json` for its actual actions and `artifacts/context/` for exact provider requests, active instructions and response schemas.

Every turn can use the whole universe. Inspect returns fixed-share contribution accounting, participation, quote freshness and constituent features, or index observations. Compare adds one registered summary to the all-feature ridge; it preserves the original feature-count denominator, alpha, scaling, target baskets, label-maturity rule and eight validation origins. It reports paired rows and gains against both ridge and the selected reference. The supported summaries are positive value weight, top-three absolute-contribution share, and value weight with fresh endpoints. These are representation experiments, not market-causality tests.

Ridge, zero and mature-training mean are explicit options. The deterministic default is the lowest past-validation MSE for each basket, with fixed tie order. All arms share this apparatus. The engineering change in baseline is not attributed to learning. Historical outputs are untouched. New receipts distinguish the last validation label from the last training label.

Commit requires one existing candidate ID for each of six targets. Code owns target mappings, numbers and executed recipes. Missing targets or malformed output end the attempt; they do not become reference forecasts. Comparison IDs are global within the episode and the six-comparison allowance does not restart on a later turn.

## The learned object

The editable object is one versioned procedure of at most 4,096 characters. It replaces the incumbent exactly. The legacy 512-character addon contract is unchanged. The reviewer sees original model contexts, numerical receipts, actual dependencies and a separately labelled later outcome. It may decline to diagnose a repairable defect.

A proposal supplies a witness, an alternative account, the exact replacement, a predicted first action signature, a valid counterexample and a disconfirmer. Code stages the exact text. The study reruns the complete Lab from the same snapshot under unchanged and candidate procedures. It measures action sequences, executed recipes, forecast values and losses separately.

The exact measured repair receipt enters the next actual reviewer request. The coordinator verifies both the structured input and its serialized presence in the provider prompt. Failures and adverse results remain evidence. Candidate retention is a recorded recommendation for further evaluation; nothing is automatically adopted.

## Run a small first episode

From the repository root, with the research dependencies installed:

```sh
python -m zenith plan lab --task-profile financial_investigator_v1
python -m research.investigator_study prepare \
  --data work/data/nepse-through-2025-final \
  --study work/investigator-development --smoke
python -m research.investigator_study run \
  --study work/investigator-development --env-file /path/to/local.env
```

Preparation makes no inference call; automatic model selection checks the live catalogue. An explicit allowed model can be supplied for an offline preparation. The runner freezes input hashes, runtime implementation and source archive, model, procedure, budget and schedule. Run uses one shared $0.25 maximum and, in the shown smoke mode, at most nine calls: Lab then one review, without candidate replay. Omit `--smoke` for the full 26-call schedule. The schedule is subject → review → unchanged control → candidate if proposed → receipt-bearing review. Invalid responses are terminal and never automatically resampled. Reinvocation consumes already completed artifacts; a failed attempt stays failed.

Native direct run/prepare and agent handoff also support this profile. Whole-Lab procedure replay uses `--replay-from <subject> --replay-node investigator_entry`. The old financial local-node replay keeps its original rules.

Preparation also calculates an earlier cutoff-only worked example using the actual tools and labels it as Type A teaching. A separate code-only comparator enumerates all 21 legal summary/source contrasts and selects by past validation. Its larger search allowance is explicit; its score is not a matched-compute architecture comparison.

One paired development replay tests integration. It cannot isolate a stochastic treatment effect, establish semantic correctness, or prove predictive benefit. Signature occurrence is a deliberately limited observable, not an automated semantic judge. February, May and August are exposed development material. Transfer and feedback-use claims need independent cases and appropriate controls; a no-change episode does not demonstrate a learned repair.

## Measured execution and interface revision

The [evidence receipt](investigator-evidence.json) records the first 12-call real episode and a separate one-call engineering continuation. Original, unchanged control and candidate action sequences differed, but their six forecasts were identical. The initial reviewer misread numerical ordering and repeated its diagnosis after measured feedback. The revised interface elicited withdrawal and rejection, while leaving unsupported claims about mandatory defaults and the candidate commit step. No procedure was adopted.

The current review contract gives initial diagnosis and feedback different decisions, supplies code-owned numerical ordering, and restricts expected signatures to executable actions. These checks constrain structure; they do not establish semantic correctness. An explicitly versioned interface continuation over a completed old episode can be run with:

    python -m research.investigator_study continue-review \
      --previous work/investigator-development \
      --study work/investigator-review-interface-v2 \
      --max-cost-usd 3 --env-file /path/to/local.env

It makes at most one call, preserves the old evidence, freezes the new interface and never reruns or adopts a Lab procedure. It tests an engineering change on exposed material, not a fresh learning claim. Failed attempts stay terminal.

## Source ownership

- `zenith/basket_panel.py`: numerical calculations and cutoff snapshots.
- `zenith/investigator_contracts.py`: action/review contracts and starting instructions.
- `zenith/investigator.py`: native profile and actual execution evidence.
- `zenith/runtime.py`: profile registration, frozen policy and replay boundaries.
- `system/lib/reasoning_policy.py`: exact replacement identity.
- `research/investigator_study.py`: the complete controlled episode and feedback dependency.
- `tests/test_investigator.py`: synthetic engineering witnesses, never model-learning evidence.

The ten further responses agree on the adaptive loop and measured feedback. They differ on numerical recipes and whether diagnosis/proposal need separate calls. This version takes one coherent representation-comparison family, keeps one numerical implementation, combines diagnosis and exact edit in one response, and records the programme that actually executes. It does not merge ten independent frameworks.


## Model policy and review context

The [model repair report](model-repair-20261013.md) records the subsequent cheap-model runs and their limitations. All live adapters enforce the model allowlist; paid requests verify tariff ceilings and interface capabilities. Automatic selection prefers the newest eligible release. One host-wide lock serializes inference; unavailable endpoints stop without a model fallback. Pin a verified endpoint with `--provider-slug` when an experiment needs fixed hosting. These controls apply even to old study protocols if someone attempts to execute them again.

Review contract `zenith_investigator_review_v4_capability` uses a lossless evidence bank with reconstructible original requests, explicit legal source/summary combinations and comparison allowance. It distinguishes observed defects from future preventive ideas. A larger context or a valid schema does not guarantee a correct diagnosis.

A new, explicitly versioned review of an already completed Lab can be prepared and run without repeating the Lab:

    python -m research.investigator_study review-only \
      --previous work/investigator-development --study work/review-new-version \
      --env-file /path/to/local.env --max-cost-usd 0.08

The previous failure remains recorded. A separate component calibration costs at most $0.01 and permits one attempt:

    python -m research.decision_audit --output work/decision-audit \
      --env-file /path/to/local.env

This is an interpretation and format check on supplied facts. It is not a forecast or learning benchmark; code already supplies its perfect reference. Do not promote its answer key into the provider's input or repair malformed output invisibly.
