# Zenith research programme

Zenith studies whether solving one problem can leave behind a better way to investigate the next. The useful retained object is a program **and the experiments that reveal when it stops working**. Experience should change what the system can compute, distinguish or ask, then measurably improve later work.

The [PROGRESS synthesis](docs/history/progress-returns-20261014.md) covers the nineteen supplied returns, numbered 02–20. It supports one small loop: propose an executable operation or experiment; measure it against the source; preserve the evidence; revise the program and any affected interfaces; test further use. Lab, Oracle and Evolve are roles in this loop. They need not be separate agents. Ordinary code is the current executable representation.

## The promising connection

A useful distinction is defined by a possible future consequence. Two histories that look identical now may require different answers after another action. An experiment exposing that difference can therefore do two jobs: refute the current program and supply a new coordinate for a better representation. The acquired representation can then suggest the next discriminating experiment.

The separate continuation learner implements the observation-table part of this idea. Access histories index its rows; distinguishing continuations index its columns; measured answers fill the table. Counterexample refinement adds an access history together with a continuation that distinguishes it, then fits new transition and readout maps. [Worrell's weighted-automata notes, Proposition 1, pp. 2–3](https://www.cs.ox.ac.uk/people/james.worrell/MA-learning.pdf), explain why retaining both is required to increase the table's rank. The notes credit the algorithm to Beimel and colleagues. Our repair restores this established invariant. The algorithm and rational-linear model class are authored.

The notes assume exact membership queries and a global equivalence oracle that returns a counterexample whenever a candidate is wrong. Zenith uses a finite challenge sequence instead. A completed fit therefore establishes agreement on those challenges; exact rational arithmetic does not establish equality on unqueried inputs. Retaining acquired continuations can reduce later queries beyond caching the same answers in the controlled memory comparison. Initial acquisition cost and competent ordinary alternatives still determine whether that saving is useful.

[Predictive state representations, §2, Theorem 1 (2001)](https://proceedings.neurips.cc/paper/2001/file/1e4d36177d71bbb3558e43af9577d70e-Paper.pdf) provide conceptual context: probabilities of future action-observation tests can represent stochastic state. That construction assumes a known partially observable Markov decision process and uses normalized conditional updates. Learning the tests is left as a research prospect in the cited paper. Zenith's deterministic rational-linear learner is a weighted-automata diagnostic, not an implementation of that stochastic construction.

<a id="current-implementation"></a>

The live [native conformance experiment](docs/studies/native/conformance-study.md) tests the complementary model-driven part: choose an experiment, execute it, deliver its measurements and failed code, and repair a fresh program. Direct JSON actions now make the host responsible for validation, iteration and source access. The [new comparison](docs/progress-protocol-20261014.md) includes compiled selectors, direct batches, two-step investigation with and without outcomes, fixed tests, and repair without new investigation. It asks whether new evidence adds value over another repair call.

The maintained continuation learner now retains each new access history with its distinguishing continuation. The smallest bounded-deque failure fits in ten source calls, but an ordinary nonlinear counter solves that same task more simply. Across eight inspected native configurations, the corrected learner completes every finite fit; later panels still expose errors in UTF-8 and SQLite. A generic singleton-question control is slightly cheaper than its default refinement. The [offline demonstration](examples/continuation-memory/witness-preserving-v1/README.md) makes both the repair and its limits reproducible.

The [client investigation pilot](docs/client-investigation-protocol-v2-20261015.md) makes one connection executable: measured development investigations feed the preparation of a frozen reusable tester. Later clients test that artifact against ordinary code reuse and fresh investigation with the same history. The [working condition](docs/studies/client/client-investigation-v2-low-20261015.md) and [earlier v1 attempt](docs/studies/client/client-investigation-20261014.md) retain separate evidence. It is a known-interface, within-family test; the exact continuation learner remains a separate mechanism, not a component silently credited for the tester's behavior.

Three testing precedents suggest different controls. [ILF (CCS 2019), §§4–6](https://doi.org/10.1145/3319535.3363230) acquires a neural testing policy from expensive symbolic-execution demonstrations, then deploys it on withheld contracts in a random contract-level split. Its deployment throughput excludes teacher acquisition and weight training. [CoverUp (2025, v4), §§3–4](https://arxiv.org/abs/2403.16218v4) keeps the LLM and an authored feedback driver fixed while execution errors and missing source coverage guide regression-test refinement. Coverage against the existing implementation does not supply an independent correctness oracle. [Voyager (2023, v2), §§2.2–2.3](https://arxiv.org/abs/2305.16291v2) retains and composes executable skills using a fixed acquisition loop and evaluates their reuse within Minecraft. These are precedents for policy acquisition, measured refinement and code reuse respectively. Their differences must survive any comparison with Zenith.

<a id="relation-to-the-graph-ambition"></a>

## What the graph contributes

A graph can expose who produces information, who consumes it, and which obligation a node serves. Each node may return its ordinary result plus a compact proposal: a missing distinction, suspected assumption, useful experiment or more valuable operation. Its position and surrounding purpose must be supplied explicitly. The report is a hypothesis, not certified self-knowledge.

Before changing a boundary, distinguish three cases: information was discarded, it is retained but ignored, or the relevant behavior was never observed. The archived SQLite failures illustrate the second case; the original rows-only helper illustrates the first. A complete-input collision can justify changing an interface. A convincing narrative cannot. When several consumers depend on the same representation, revise and test their joint obligations; do not accept a locally improved node that breaks the end-to-end result.

The graph may grow, shrink or disappear into simpler code. Additional nodes, explanations or edges are not progress measures. The current witness comparison supplies context and optional notes without privileged routing. Any future claim for graph-aware routing requires implementing that routing and comparing actual outcomes.

## What counts as progress

Keep these outcomes separate:

- **Acquired computation:** observations determine a program that works on further cases.
- **Measured repair:** a failure changes code and improves later behavior while preserving measured prior successes.
- **Useful memory:** a retained program, test or procedure improves a later task beyond the same cached observations and ordinary alternatives.
- **Improved learning method:** experience changes how acquisition works, and that change helps fresh problems after all discovery costs are charged.

The first three can be valuable contributions without establishing the fourth. A new model call is not automatically a learning step. In the earlier six-source rule study, every winning global first proposal already worked; the second proposal added no benefit. Those exact artifacts remain in the [historical campaign](docs/history/decomposition-20261014.md).

## How to choose the next experiment

Use meaningful software obligations with independently executable success checks. Native emulation is a cheap mechanism diagnostic; useful client compatibility, exception atomicity and recovery are better eventual beneficiaries. A direct native call or an existing correct program is a serious baseline when the task permits it.

First establish headroom without selecting convenient failures. Then compare a candidate mechanism with the strongest simple alternative on the same starting code, observations, tools and declared allowances. Preserve invalid programs and unhelpful experiments. Distinguish a source query from a model call, and both from independent experimental subjects. Open later panels only after program and selection rules are frozen.

Pursue an advantage only if it survives its relevant ablation. For memory, retain the same raw answers and remove only the acquired questions or procedure. For node reports, keep ordinary reasoning and global refactoring available. For a changed representation, include continuation and recovery obligations; a correct reset-time model may still be unable to resume an existing process. Compare total cost as well as the cost of the next stage.

The client pilot asks whether behavior survives a changed implementation, interruption or recovery boundary. Recreating a fully documented library gives a capable model little need to investigate: three earlier Ling-generated programs already passed both panels. Its batch-import and transfer workflows make caller-owned transactions and post-failure continuation observable. A competent fixed tester already detects every authored faulty client, so this population cannot establish a detection advantage over that baseline. It can establish whether acquired code works and what reuse costs. A stronger next campaign needs independently sourced clients with genuine headroom, chosen before observing learned-policy outcomes. A retained question must identify useful new evidence, not merely replay an old answer or a known exact input.

A proposed preparation control adapts CoverUp's measured refinement to retained testing code. Execute a candidate on predeclared development fixtures, return its actual invalid output, duplicate-query rejection or measured failure, and allow a bounded revision. Give ordinary reusable code the same development observations and revision allowance; retain one-shot compilation as another control. Preserve every original candidate, rejection and charge. Select using development evidence, then freeze the tester before target execution. This requires a separate protocol and source freeze; the published one-shot attempts remain unchanged. It first tests delivery and progress through legal queries. A fixed test schedule can avoid duplicates without interpreting outcomes, so feedback use and useful later fault detection require their own comparisons. The opaque-client study must also retain its observation limits: source coverage or hidden implementation identifiers cannot be added as if they were already available.

The next advance would be a reusable investigative procedure that experience changes and that earns its cost across genuinely changed clients or mechanisms. The active implementation stays small enough to expose exactly which artifact changed, what evidence caused it, and which later behavior improved.

## Improving future improvement

The broader ambition is for an acquired capability to improve the work that produces subsequent improvements. One candidate is a procedure that chooses useful experiments, uses their outcomes to distinguish a representation defect from incorrect use of existing information, and changes the next investigation accordingly. The continuation learner and generated testers remain separate; this connection is proposed, not implemented or established as novel.

[STOP (COLM 2024, v3), §§3–5](https://arxiv.org/abs/2310.02304v3), directly precedes this ambition: a code-improvement scaffold is applied recursively to its own source, while the language model, utility and experiment controller remain fixed. [Hyperagents (2026, v1), §§3–5](https://arxiv.org/abs/2603.19461v1), makes both task-agent and meta-agent code editable. It evaluates an acquired meta-agent's ability to improve agents in a new domain while the main experiments retain fixed task distributions, outer parent selection and evaluation. Its stronger transferred-versus-fresh compounding comparison is statistically unresolved. Zenith has no acquired meta-agent or code-improvement scaffold of this kind yet.

A proposed evaluation would separate acquisition from a test of the frozen improver:

1. Produce a successor improver O₁ from O₀ on development families. Keep family splits, reference software, evaluator, legal outputs and budget enforcement outside the editable code. Select O₁ using development evidence and freeze its source hash before target work.
2. Give each fixed improver untouched copies of identical, valid starting solvers and the same available history on fresh target families. Hold the improver unchanged while it proposes up to a declared number of solver children or spends its allowance. Count invalid deliveries, unchanged programs and rejected children. Include ordinary reusable code, fixed best-of-budget sampling and iterative repair under matched tools and budgets.
3. Select a solver child using development cases only and preserve previously correct measured obligations where applicable. Freeze the selected child's source hash, then evaluate that child on withheld cases. Report its gain over the common starting solver; never choose a child by the maximum held-out score. Provide valid output interfaces before measuring semantic improvement so that a wrapper repair cannot stand in for it.
4. Report repeated acquisitions and independent families with their uncertainty. Charge all acquisition, rejected proposals, model tokens, source executions, evaluation work and human intervention. Report deployment and lifetime totals separately, and let ordinary controls spend an equivalent acquisition allowance. Remove only the acquired questions or investigation procedure while retaining the same raw observations and saved code to test their contribution.

Only after a useful frozen O₁ has been demonstrated should another experiment test reinvestment: compare a successor produced using O₁ with one produced using O₀ at matched lifetime cost and common new starts. A better final solver or self-edited scaffold alone does not establish a better improver or accelerating progress. First reproduce the relevant STOP and Hyperagents mechanisms, then test whether Zenith's proposed link from measured distinctions to subsequent investigation adds value. Any positive result would remain bounded by its tasks, model and budget.

## Mathematics as a possible transfer domain

The [Plectis mathematical corpus](https://github.com/wcook04/plectis-erdos) provides statements, proofs, partial results and remaining obligations. Its [argument-continuation exporter](https://github.com/wcook04/plectis-erdos/blob/main/scripts/export_argument_continuations.lean) suggests candidate theorems for a required hypothesis and records unsatisfied prerequisites. [Plectis Atlas](https://github.com/wcook04/plectis-atlas) supplies a reading route through OpenAI's mathematics release and attributed outside assessments. These are possible sources of tasks and evidence, with their own authorship and checking limits; they are not current Zenith runtime dependencies or a demonstrated combined learner.

A first experiment could compare concrete actions at authentic, source-pinned decision points: seek a prerequisite proof, try another argument or test a conjecture with an exact counterexample. Record what was known, the available action, measured outcome, cost and effect on the target. Collect comparable alternatives instead of reconstructing unobserved failures from finished papers. Withhold solution proofs and their derivatives, split related obligations together, and disclose pretrained-model exposure that cannot be excluded. Compare with ordinary retrieval and a capable simple coding agent before adding a learned selector.

Lean can validate a supplied proof. An exact witness can refute a conjecture. Failed search establishes neither falsehood nor irrelevance. Auxiliary lemmas need demonstrated downstream use or explicit expert assessment; accumulating correct statements is not a substitute for progress on the intended target. Software remains the cheap first test, with mathematics a possible harder transfer domain. This direction does not launch a pivot, model training or a paid experiment.

This programme is the author's current understanding, developed with AI coding agents while learning the field. Corrections and collaboration on the closest literature, evaluation design and useful external tasks are welcome through [issues](https://github.com/wcook04/plectis-zenith/issues) and [contributions](CONTRIBUTING.md).

## Source and evidence

- [Current results and historical record](docs/status.md)
- [Native conformance method and commands](docs/studies/native/conformance-study.md)
- [Nineteen PROGRESS returns: adoption and reproduction](docs/history/progress-returns-20261014.md)
- [Earlier ADVANCE returns](docs/history/advance-returns-20261014.md)
- [Earlier executable observation studies](docs/history/executable-investigations.md)
- [Three-page manuscript](paper/zenith.tex)
- [Reviewed source editions, claim locators and manuscript support](paper/references.json), checked by the [bibliography owner](scripts/build_paper_references.py)

Current model selection favors recent, capable, inexpensive Chinese-developed models with verified endpoint prices and working delivery. Independent calls may run with the host-wide bound of three and one per pinned endpoint. Every experiment freezes its own route, reasoning setting, runtime and dollar ceiling; old source archives retain their original behavior.
