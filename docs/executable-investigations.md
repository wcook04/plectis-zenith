# Executable observation learning

Zenith retains an executable account of how a source responds to interventions, together with the observations that support it. A model proposes an experiment, the host executes it, and a measured discrepancy becomes evidence for revising the program. Later questions should benefit from that retained computation. This is the current synthesis of [ten frontier returns](frontier-returns-20261013.md), all independently audited, rather than a larger mandatory graph.

## One object, one loop

The retained record contains a source identity, immutable program version, its claimed scope, host observation receipts and measured counterexamples. The code predicts a requested quantity from a fresh action sequence and may acquire the source's calibration history. It returns an integer when supported, or an explicit unresolved result. A scope statement remains a model claim. A source hash establishes custody, not semantic correctness or continued validity.

The loop is concrete: propose discriminating actions; execute them against a disposable source; record the observations; author or revise a program; replay all observed development cases; retain a candidate under the declared selection rule; freeze and evaluate new combinations. Lab, Oracle and Evolve describe these functions, not three compulsory model agents. The existing provider, acquisition logger and restricted executor implement the loop.

Search state and selected code are separate. The next request sees the actual last candidate, including rejected candidates and measured execution errors. Selection compares complete development accuracy, records every regression, and permits a neutral revision when the new executable program ties the current score. A tie is a revision, not measured improvement. This replaces the old campaign's universal empirical no-regression veto; it does not relax execution constraints or turn development evidence into a proof.

## Native source and independent feedback

Each experiment starts with an empty SQLite table and two writing connections. The public interface allows insertion, update, deletion and transactions. The configured source varies ordinary conflict handling, insertion instrumentation and the counter it emits. A separate read connection measures committed item count and sum. SQLite itself supplies every measured outcome. Counter increments can survive effects that disappear from committed state, and a connection-local counter need not reflect another connection.

The model receives descriptions of available actions, the allowed source family and past measured receipts. The public contract names the three insertion policies, absent versus one insertion-log trigger, and three native counter choices. The actual configuration, candidate programs, source implementation and protected query labels stay private. It writes ordinary restricted Python rather than selecting a supplied solver. The three goals—emitted channel, committed count and committed sum—are supplied by the study; this does not claim autonomous invention of useful quantities.

A remaining ambiguity can affect one goal without affecting another. The evaluator enumerates the disclosed native family compatible with the observed receipts and executes the requested sequence on those configurations. A goal is identified only if all compatible outcomes agree. Disclosing this support criterion makes the requested answer achievable from the supplied context; a hidden hypothesis class would unfairly penalize reasonable unresolved answers. This is a conditional guarantee within that family, not evidence that no other software could fit the same history. Correct answers outside the family, future source drift and arbitrary SQLite behavior are not established.

## A comparison capable of choosing the simpler system

The predeclared campaign uses six distinct source configurations, balanced across conflict handling, counter selection and trigger presence, within an 18-member family. Each source has three episodes. An independent model planner proposes three calibration experiments per episode; the host also executes one predeclared challenge that does not depend on candidate agreement. Invalid probes are retained as failures, not silently replaced. The resulting exact receipts are shared by every condition.

| Condition | Evidence and retained state | Coding allowance per source |
|---|---|---:|
| Incremental | Growing common history, selected program and last challenger with measured errors | Two proposals in each of three episodes |
| Execution-enabled archive | Same growing history, all previous proposals and their execution feedback; may refactor or compose | Two proposals in each of three episodes |
| Fresh compiler | All final common history at once; builds from scratch with its own full repair archive | Six proposals |

Every condition uses the same model, executor, candidate interface, development labels and selection rule. Each receives six proposals in total; the fresh compiler does not receive an artificially smaller allowance. Input lengths and actual token costs can differ and must be reported. The archive is an executable competitor, not a prose-only baseline.

Only observed calibration outcomes are development labels. Matching those observations by lookup can therefore pass development while failing new combinations. Independent evaluation contains 16 further action compositions per source, with three goals each. All model construction across all sources ends before any protected scoring. There is no protected feedback or best-of-heldout selection. The primary unit is the configured source, not each of its correlated queries.

The first incremental checkpoint is also frozen and evaluated with the final raw history. If that program equals the final one, a stable interpreter plus additional evidence can explain the improvement; continued program revision has not earned a separate claim. Removing history from the final program measures dependence on supplied evidence. A compiled model can legitimately retain knowledge after history is removed, so this is not presented as deleting everything learned. The cold abstaining program supplies an additional reference.

Checkpoint evaluations use prefix-specific identifiability keys. They describe the joint trajectory of evidence and program, not a pure program-learning curve. Final paired comparisons and freeze-and-grow use identical final evidence and keys. A paired bootstrap over configured sources is descriptive; six variants of one designed software family are not six independent domains.

## Execution, cost and custody

`research/observation_world.py` owns the actual source and private evaluator. `research/observation_learning_study.py` owns preparation, model-proposed acquisition, comparison and end-only audit. `zenith/investigation_program.py` runs the model's exact code in a fresh process, with a finite JSON answer contract, logged table acquisition and wall/CPU/memory limits. It supports ordinary local state operations, including closure updates, container deletion and dictionary updates. It permits no imports, ambient files, network access or arbitrary attributes. This restricted research harness is not an operating-system security sandbox.

Preparation archives executable sources and freezes dataset, protocol, model route, reasoning setting, output allowance and total budget. A separate receipt binds the complete frozen program set before protected evaluation. Raw returned content is saved before response-schema validation; rejected, unchanged, malformed and interrupted attempts remain in custody. No automatic retry or provider/model fallback occurs within a campaign. Deliberate changes start another version.

The default design allows 18 shared planning calls plus 108 program proposals: 126 calls. Its $2 ceiling is a maximum, not expected spend. After the first round across all six sources (at most 30 calls), every active request settles before the engineering checkpoint. Continue only if every source has an executable candidate and a valid model-proposed observation, and at least one candidate across the cohort answers an observed query correctly. Keep difficult sources with zero correct answers: their learning success is an outcome, not an admission requirement. This gate uses development execution, never protected outcomes or a preferred arm. The complete pilot is audited before deciding whether a separately frozen confirmation is informative. Actual billed tokens and cost are reported separately from conservative reservations. The model policy selects recent capable inexpensive Chinese-developed models, verifies actual endpoint prices and runs an execution canary. Recency alone cannot establish suitability. Independent worlds use at most three concurrent calls across the host and one per pinned endpoint. All conditions within a world use the same route, preventing provider differences from confounding its paired comparison. Dependencies remain sequential. Failure stops new admission while already active calls settle; their charges and outputs remain recorded.

## OpenRouter design evidence

The implementation applies the official [OpenRouter skills](https://github.com/OpenRouterTeam/skills/tree/33597a44e38b0cdc38ea1256ef8bcf50c2704e3d/skills), inspected at the 29 September 2026 revision, to the existing Python adapter. The SDK examples are guidance; they do not require adding a TypeScript stack. The upstream tree did not declare a licence when inspected, so no upstream code was vendored.

- [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection): pin the exact endpoint, require supported parameters and prohibit fallback. Cheap model identity alone does not cap a host's price.
- [Limits](https://openrouter.ai/docs/api_reference/limits): concurrent output reservations can exhaust an in-flight spending budget even with account credits. Classify the returned limit source; extra API keys do not create capacity. Keep local reservation and settlement atomic and distinct from actual charges.
- [Reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens): hidden reasoning still consumes billed output and the output cap. Hiding it does not disable it. Check executable quality and latency when changing reasoning settings; preserve failed or truncated attempts.
- [Latency and caching](https://openrouter.ai/docs/guides/best-practices/latency-and-performance): keep stable instructions first and measure the selected route. Do not assume a cache discount or a latency improvement from streaming. Retried requests in SDK recipes are inappropriate for this study's immutable attempts.

These are operational controls, not evidence for a special learning mechanism. Model plans and repairs remain causally ordered even when independent sources overlap.

## Run and reproduce

```sh
python -m research.observation_learning_study prepare work/observation-run --model deepseek/deepseek-v4.1-flash --provider deepinfra/fp8 --providers deepinfra/fp8 baidu/fp8 morph/fp8 --workers 3 --reasoning-effort none
python -m research.observation_learning_study run work/observation-run --env-file /path/to/local.env
python -m research.observation_learning_study replay work/observation-run
python scripts/build_observation_report.py replay
python -m pytest tests/test_observation_world.py tests/test_observation_learning_study.py tests/test_investigation_program.py
```

The local replay verifies unchanged prepared source. Published evidence should replay the archived source, so later engineering changes cannot silently alter historical results. [Status](status.md) distinguishes completed measurements, failed attempts and running work.

The completed V5 comparison made 126 calls for $0.12947251224. Incremental construction scored 244/288 protected answers, archive 187/288 and fresh compilation 230/288. The early incremental program with final history also scored 244/288, tying on all six sources. This control rules out a measured benefit from continued code revision in this run. The source-level comparison intervals against archive and fresh compilation span zero; neither the aggregate ranking nor a functioning feedback loop establishes recursive self-improvement.

## Small tests of the combined mechanism

The follow-on screens retain the same code/evidence/source/dependency object and native executor. They separate three possible improvements: obtaining a useful observation, repairing a wrong computation, and reusing a learned computation in a larger one. A failure to fit any observed history calls for revising the program, not simply collecting more of the same observations.

The repair screen selects three failed V5 programs retrospectively. Generic repair, explicit counterexample emphasis and fresh reconstruction receive the same native measurements and two proposals each. Prefix and minimized-witness measurements are shared; only the treatment of prior code and feedback differs. Entire action structures are held out, rather than merely changing constants in the original templates. Screening selects an approach; a separately frozen pool tests the selected frozen programs without another model call. This confirms those repairs on those sources, not a general repair policy or model ranking.

The candidate-pool screen combines complementary programs without splicing their numerical answers. Each source receives four proposal slots: two from each model, or four from either model. Every pool chooses one executable program using development accuracy, then source-hash order; no protected score selects an individual program. The mixed slots reuse original restart attempts, while each single-model pool adds two continuations. This matches proposal counts but not histories or token costs. A predeclared screening rule selects the primary pool; all three frozen pools and unchanged seeds then face the same separate confirmation panel. All actual V5 discovery and evaluation structures, not just the initial fixture, are excluded from these panels.

The active-selection assay purchases no more code. It freezes all eight current attempt slots per source and compares fixed versus disagreement-directed acquisition, crossed with unchanged initial selection versus development-based reselection. Each policy measures exactly two native probes; its two selection conditions share those receipts. Candidate predictions for unchosen probes use public contexts without executing hidden labels. Invalid predictions do not vote, and byte-identical programs vote once. A separate reference selects from all 18 same-source V5 proposals, using only development evidence and the same fixed-policy receipts. Its larger historical search budget is disclosed. This guards against crediting new generation for knowledge the old archive already contained.

Selection ends before any final scoring. The primary active-selection measure is correctly resolved supported answers on a fixed final-query denominator. Wrong numerical claims, unsupported commitments, abstentions and execution errors remain separate. This prevents a change in what is identifiable from being mistaken for better numerical prediction. The acquisition rule is authored; this is a test of information and selection, not an LLM learning how to investigate.

The composition screen learns ordinary state-transition and readout functions, then asks models to extend behavior to nested savepoints. Graph, flat-library and fresh-library assembly have identical primitive code, receipts, linking facilities and three proposal allowances. The flat program may inline or rewrite everything. Actual child invocation is recorded separately from the effect of replacing a child with a neutral function. A first caller that already solves later cases establishes compilation and reuse; it does not establish continued learning. The no-library single-shot diagnostic has fewer proposals and is labelled separately.

Every screen freezes code, native datasets, model settings and comparisons before inference. Screening and confirmation remain distinct, all failed proposals remain in the record, and the public replay executes the archived runtime with network access disabled. The original V5 comparison remains immutable.

Completed screen bundles replay without API credentials:

```sh
python scripts/build_observation_report.py replay-screen --bundle examples/observation-learning/screen-repair-deepseek-v1
python scripts/build_observation_report.py replay-screen --bundle examples/observation-learning/screen-candidate-pool-v1
```

The [follow-on index](observation-screens-20261013.json) binds each campaign separately and counts reused calls only once. Reservation limits are not measured charges. A new campaign must prepare fresh immutable output; do not rerun inference in an earlier directory or edit a frozen proposal to make it pass.

## Historical experiments

The earlier operational campaign used supplied active-time, elapsed-time and billed-work contracts. It established useful model-authored compilation and some measured repair, but its direct/prose controls lacked execution and its strict promotion gate could stall. Its [versioned receipt](investigation-learning-20261013.json), frozen code and `scripts/build_learning_report.py replay` remain available unchanged. The financial investigator, full graph, basket pilot and System A fixture retain their own evidence boundaries. None establishes forecasting or causal advantage.
