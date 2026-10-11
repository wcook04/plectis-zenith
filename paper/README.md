# Zenith systems paper

The manuscript is [zenith.tex](zenith.tex), its bibliography is
[references.bib](references.bib), and paper-house-style.sty supplies shared
typography. This standalone Zenith implementation/evaluation paper does not
replace the Plectis system paper or the private strategy document.

The manuscript follows an empirical systems structure: problem, implemented
method, conditional formal contracts, assessment protocol, observed evidence,
related work and limitations. It claims no forecasting advantage, generalized
optimizer or established novelty.

Build from this directory:

    tectonic --keep-logs --reruns 2 zenith.tex

Tectonic runs the bibliography pass. Source/data and environment instructions
remain in the repository's docs/reproducing.md, docs/experiments.md and
docs/architecture-sources.json. Both native phases are complete, and the later
assessment is sealed under native-deepinfra-final-v1. The result table is a
projection of attributable native reports, with exact scores in
study-evidence.json. Both arms retained their frozen graph, policy, inputs,
model and provider identity. These small, previously examined historical
windows support pipeline feasibility and a descriptive comparison, not
significance, a learned update, prospective accuracy or profitability.
Report failed attempts, matched target support, model identity, calls,
reported/unknown cost and assessment exposure with any measured losses.

Compatibility calibration is supported by calibration-evidence.json, a
text-free snapshot of four excluded July pilots. It binds original receipt
and validation-sidecar hashes, requested/actual models and providers, native
outcomes and reported/unknown costs. For each pilot, every manifest
implementation hash is checked against the SHA256 of the corresponding Git
blob bytes. A matching revision describes content compatibility, not an
observed HEAD or a unique executed revision. Prompt-profile introduction is
recorded separately; the v2 HTTP 429 manifest matches aa2f8ec, while its
profile-introduction commit 7582bf1 differs in the paid adapter. Nova and Qwen
v1 responses failed format
or length validation. The unpinned DeepSeek v2 request returned HTTP 429 with
no response or usage record; its unknown charge and full reservation remain.
An authorized recovery preserved that history. A fresh DeepSeek v2 pilot,
requested through deepinfra/fp8 and reported as DeepInfra, completed both
reasoning nodes under the same validators. Native acceptance establishes
compatibility, not forecast accuracy or a matched comparison between models.
Calibration accounting is a subset of the shared, evolving production ledger;
reservations are distinct from reported charges.

The following command reproduces the original projection at its frozen source
revision (01522cc), with the original native artifacts available. The completed
export is an immutable historical snapshot; do not overwrite it for a later
study or a shared ledger that has since acquired new calls:

    python3 paper/export_study_evidence.py --study work/native-deepinfra-study --budget work/stocknet-native-five-dollar-budget/budget.json --output paper/study-evidence.json

The exporter uses the standard library and writes only the paper evidence
projection. It verifies the frozen source/input identities, binds source-file
hashes and excludes prompts, responses and market observations. It does not
execute models, evaluate forecasts, select a candidate or seal a study.
Comparison scores remain unavailable until the native evaluator records
complete common support. The shared-budget section includes all calibration
and study attempts, responses, reported costs, unknown charges and in-flight
requests, separately from each study arm's accounting. Re-export after the
native receipts settle before creating a new study's separate export; a live
source change during export causes an error rather than a mixed snapshot.
Use an explicit new output path, such as paper/learning-study-evidence.json,
for subsequent experiments.

Finance grounding is recorded in docs/finance-design.md,
docs/finance-related-work.json, docs/finance-adaptive-sources.json and
docs/finance-validation.md. The manuscript cites the closest mechanisms and
evaluation controls; these manifests retain acquisition, code-pin and
paper-versus-later-code details. QuantAgent (Wang et al., 2024) is distinct from
the later work renamed QuantHarness. FinRobot's current strategy loop is cited
as code, separately from its 2024 platform paper. No upstream stack is installed
as a consequence of these citations.

The 12 October revision assimilates three supplied papers: Huang et al.
(arXiv:2604.19476v2), Wang and Yeung (Frontiers 9:1722121), and Yu et al.
(arXiv:2306.11025v1). The annotated/original Yu uploads contain identical
decoded page contents and no distinguishable operator notes. Native parent
annexes preserve identities, source passages, critical findings and transfer
decisions. Citations occur at each adopted mechanism, economic motivation,
dataset or software use. Future-news ROUGE is not treated as explanation
fidelity, and financial network indicators are not mistaken for return targets.

The revised A-share section includes the actual negative development-only
text-control comparison from docs/ashare-development-controls.json. The LLM
study remains unexecuted. The first-learning profile retains all 48 assessment
dates and allows 572 total calls including capability checks; that plan does
not release the paid hold or expand the immutable budget.

Authoring owners used:

- ai_workflow/.agents/skills/route-human-authoring/SKILL.md and
  ai_workflow/.agents/skills/humanizer/SKILL.md for systems prose.
- ai_workflow/codex/standards/paper_register_rules.json, adopted rules
  REG-001 through REG-003 for literal register, genre and bounded verification
  reporting.
- ai_workflow/.agents/skills/mathematical-reasoning/SKILL.md for the existing
  metric definition and conditional reach of the Lean source. This document
  introduces no new mathematical result.

The typography is an exact copy of Will Cook's CC-BY-4.0 shared style at
ai_workflow/tools/meta/dissemination/plectis_intro/paper-house-style.sty,
SHA256 1b4630ead32bfb407a2f29f5953fbb8d4140a659f6500799282a4805ba54a883.
Its copyright/licence header is retained. The manuscript and bibliography use
the repository's Apache-2.0 licence. Prior-art sources are cited rather than
copied into the manuscript.

export-validation.json binds the actual complete development and sealed final
reports. Five rejected probes on deep copies cover missing issue, missing
target coverage, altered paired delta, altered aggregate mean and pending
state with nonnull scores. Final validation also rejects an unregistered
selected candidate and checks equality with the sealed state receipt. Native
source reports remained unchanged. Calibration's final ledger locator/hash
matches the settled study ledger; its four-pilot/six-attempt subset stays
separate from shared totals of 106 attempts, 105 responses and one unknown
charge.

The compressed manuscript keeps the completed manual-rule study distinct from
the proposed feedback-derived policy experiment. The original three receipt
exports remain unchanged; any later learning study needs a separate export and
source identities. The full reviewed bibliography is retained as metadata,
while the manuscript cites only sources needed for its actual argument.

Source owners formerly tabulated in the manuscript:

| Operation | Source owner |
| --- | --- |
| Native execution/planning | zenith/runtime.py; system/core/engine.py |
| Skill/context policy | system/lib/reasoning_policy.py |
| Forecast admission/truth | feedback/engine.py |
| Matched comparison/seals | research/cohort.py |
| Recorded diagnostics | research/diagnosis.py |
| Proposal compilation | research/reflection.py; research/reflection_cohort.py |
| Conditional formal model | formal/ZenithSemantics.lean; scripts/check_semantics.py |
| Source/data decisions | docs/architecture-sources.json; docs/data-sources.md |

Controlled routing validation uses the canonical
[repair-controls.json](../docs/repair-controls.json), bound to
benchmarks/repair_controls.py and the native context-policy source. Its finite
selector uses 20 training cases and 64 disjoint changed-range assessment cases
per scenario. The main paper reports numeric answers separately from valid
abstentions and identifies the faulty-operator negative control. This is
integration/control validation without model calls or a new market study.
[learning-protocol-audit.json](learning-protocol-audit.json) records the final
receipt/source hashes and interpretation boundaries; it does not duplicate the
canonical results or alter the original study exports.

The compressed main text reports all excluded compatibility pilots in one
paragraph; their full accounting, validation and implementation-match evidence
remain above and in calibration-evidence.json. The reviewed ATLAS v5 method
optimizes static instructions using prompt-performance history and outcome
summaries, while protecting runtime placeholders and output interfaces. A local
outcome-summary arm can borrow that information pattern without constituting
an ATLAS/StockSim reproduction. StockSim's public snapshot does not expose the
paper's complete optimizer configuration. The new executable-return learning
study is still being specified; this manuscript reports no results from it.

The later A-share study is compiled offline; model execution remains held.
The [protocol](../docs/ashare-study.md) and
[admission receipt](../docs/ashare-admission.json) bind 136 admitted issue
batches, separate forward/teacher/evaluator information, complete comparisons,
calendar provenance and a 1,213-call maximum core plan. No new learning result
is reported. The original study and calibration exports remain unchanged.
The selection rationale is
[data-selection.md](../docs/data-selection.md), with the independent cross-track
protocol recommendation in [data-selection-design.json](../docs/data-selection-design.json).
TraderHarness supplies the multi-session forecast panel from February
2023 onward after explicit warm-up, corporate-action and fixed-support checks.
Its earlier price coverage gaps prevent a min/max date range from establishing
continuous coverage. Unknown-vintage fundamentals are omitted; announcement
availability is conservative. No new paid learning study or result is reported.
