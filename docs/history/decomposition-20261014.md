# Structural revision and source-rule learning — 14 October 2026

Historical research record. References to “current” or “next” describe this stage; see [today’s findings](../status.md).

**The strongest delivered configuration is simple ordinary code with DeepSeek reasoning enabled.** It acquired correct predictors for all six fresh synthetic sources:144/144 on each of two frozen later panels, versus 120/144 for ordinary contracts with reasoning and 52/144 for contracts without it. Every winning global first proposal already passed; a second proposal added no measured benefit. This is useful source-rule acquisition, not a self-improving learning algorithm.

Seven completed studies made **122 calls for $0.177964589964**, approximately 18 cents. These are reported API inference charges, excluding local computation and labour; budget ceilings and conservative reservations are not invoices. All calls settled. [Machine-readable results](decomposition-20261014.json), [method](decomposition-study.md), [implementation](../../research/decomposition_study.py).

## What changed

The runner now compares unrestricted ordinary code, mechanically supplied local call context, equivalent function contracts and an optional fixed-interface diagnostic. It uses the existing executor, provider and shared budget. Every candidate receives actual execution feedback; rejected outputs remain available to the next proposal. Preparation freezes code, data, routes and later panels. Selection uses all visible measurements, never later labels. All original outputs and failed versions remain unchanged in the public bundles.

The first study follows the fifteen-return synthesis: can a model repair information-losing interfaces and missing history? The next studies test whether it can infer a source-specific computation from measurements when the exact rule is withheld. The final stage follows a positive reasoning-enabled result onto six new configurations and a repaired execution interface. It does not transplant an acquired learner or reuse a previous source's answer.

## Structural repair

| Qwen condition | Screen /96 | Confirmation /96 |
|---|---:|---:|
| Initial code |35|32|
| Fixed interface |35|32|
| Global ordinary code |88|88|
| Local call context |88|88|
| Ordinary contracts |96|96|

[Exact 32-call bundle](../../examples/decomposition/qwen-v1/manifest.json), reported cost$0.045607014. Four authored tasks include two sensor cases, a native SQLite allocator and synthetic keyed events. The correct sensor control stays correct in every selected condition. Unrestricted code learns sensor calibration and retains event keys/timestamps that the seed discarded. Fixed-interface failure includes invalid proposals and cannot be attributed entirely to information loss.

All differences among the unrestricted conditions arise on the single SQLite task. Global and contextual code track only a committed high-water mark. The final measurement uses the same connection, so pending inserts in an open transaction also matter. Both programs fit all 32 visible cases but fail 8/24 in each later panel. There were no open final transactions in the visible examples, despite their being legal under the public specification.

The contracts first proposal instead retains rolled-back maxima. Measured failures lead to a second proposal that updates a tentative maximum, saves it at begin and restores it at rollback. Its confirmation improves 14→24/24. A minimal retrospective witness is `begin; put 9`: native next-ID 10, global/contextual 1. For `begin; put 9; rollback`, native next-ID 1, contracts-first 10. These explanatory probes are not additional confirmation scores. The result supports bounded repair of state lifetime; one trajectory on one native source does not establish an architectural advantage.

## Harder rule induction

A supplied family contains 4,464 polynomial/interaction/cumulative-sum configurations. Twelve calibration observations uniquely identify each selected source within that family; the model receives 24 more development examples. The private oracle, reference, parameters and identification audit stay out of prompts. Source observations are synthetic integer arithmetic, not native software behavior. Later sequence lengths increase to 8–14 and 16–32 from at most 6 in development.

| Model and setting | Global /72 | Local context /72 | Contracts /72 | Calls | Reported cost |
|---|---:|---:|---:|---:|---:|
| [Qwen, reasoning off](../../examples/decomposition/state-qwen-v1/manifest.json) |0|24|0|18|$0.019720232|
| [DeepSeek, reasoning off](../../examples/decomposition/state-deepseek-v1/manifest.json) |0|0|0|18|$0.014218893824|
| [DeepSeek, low reasoning](../../examples/decomposition/state-deepseek-low-v1/manifest.json) |48|48|48|18|$0.035842590112|

These are confirmation totals; screening gives the same totals. They share source configurations and panels, so they are diagnostic comparisons, not independent replications. Reasoning-enabled runs have a larger 12,288-token allowance versus 6,144; costs are reported rather than calling this an equal-token effect. The code shows actual acquired rules: for example, an order-sensitive weighted sum of squares replaces an inadequate plain sum.

Many proposals fail delivery: the old executor rejects even the harmless `_` discard variable. We now permit exactly that local name while retaining the private-name, attribute and resource restrictions. Some unchanged old candidates become correct under this narrow correction; others still compute the wrong rule. That post-hoc diagnostic does not replace any frozen score. The next stage uses the corrected executor and explicit syntax examples for every condition.

## Following the promising configuration

Six fresh source settings balance no interaction, adjacent-value interaction and preceding-sum interaction, with cumulative depths 1–4 and signed polynomial coefficients. The three comparisons share exactly the same dataset, pinned per-source routes and two-proposal allowance. Each starts from an authored seed, so this is fresh acquisition across source settings, not transfer of previously acquired knowledge.

| DeepSeek configuration | First proposal /144 | Selected /144 | Calls | Reported cost |
|---|---:|---:|---:|---:|
| Contracts, reasoning off |25|52|12|$0.009420509928|
| Contracts, low reasoning |120|120|12|$0.0257931991|
| Global ordinary code, low reasoning |144|144|12|$0.0273621510|

The table uses confirmation; selected screening totals are identical. Initial code scores 4/144. [Off](../../examples/decomposition/binding-deepseek-none-v1/manifest.json), [low/contracts](../../examples/decomposition/binding-deepseek-low-v1/manifest.json), [low/global](../../examples/decomposition/binding-deepseek-low-global-v1/manifest.json). There are six configured members of one supplied family, not 144 independent tasks. A single model trajectory per setting/source cannot establish a universal ranking of prompts or models.

An authored exhaustive fitter also scores **144/144 with zero model calls**, using only the supplied family and public calibration measurements; it never reads private source settings. The machine-readable receipt records this competent reference for every state study. Thus the model result establishes acquisition of the rule, not improvement over the family-specific symbolic solver.

The global condition infers all six rules on its first proposal. Several implementations retain full transformed lists; one fits remaining parameters against embedded training receipts during each prediction. Thus correctness is not yet evidence of a compact, efficient persistent representation. Every query supplies the whole input sequence. No minimal-state, acquired-language, learning-policy or recursive-self-improvement claim follows.

## The system to keep

Keep one measurement-and-code loop: preserve observations, propose an executable source model, run it, retain counterexamples and useful alternatives, and test untouched cases. Give the model enough reasoning to fit the evidence and avoid unnecessary syntax traps. Permit ordinary refactoring across function boundaries. Explicit graph context remains an optional hypothesis, not a necessary runtime layer.

The next capability test should require persistent compact state: one new observation and a bounded candidate-owned record per step, checking every prefix and forked continuation against a correct ordinary reference. The next learning-method test should transfer only a model-derived investigation rule onto fresh sources and compare total acquisition cost with a competent pilot-tuned fixed rule. Neither mechanism is implemented or established by these results. Repeating successful one-shot compilation would not answer those questions.

## Reproduction

Every study above has an immutable manifest, original prompts/responses, candidate trajectories, individual later answers, numeric billing and a source archive. Exported replay reconstructs prompts, executes exact programs, repeats selection and checks both panels using its archived runtime with an empty environment and no provider calls. This matters because old studies intentionally retain the earlier `_` rejection. Current-runtime replay of an old work directory correctly refuses a source mismatch.

```sh
python scripts/build_decomposition_report.py replay examples/decomposition/binding-deepseek-low-global-v1
python scripts/build_decomposition_report.py campaign --output docs/history/decomposition-20261014.json
```

Campaign aggregation verifies manifest membership and hashes, derives counts from individual answer rows, and checks saved summary consistency. Different panels are never pooled into one accuracy. The exact traces and first-proposal controls are part of the result, including where repeated revision provided no benefit.
