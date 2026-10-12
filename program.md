# Zenith daily learning programme

Develop a financial reasoner that identifies useful economic changes and learns how to act on them. Establish a competent base before asking whether reasoning updates improve it. The graph, retrieval, prompts, evidence sources, numerical mapping and task definition are development choices. Retain each materially different version and what informed its selection. Evaluation supports this objective; completing an experiment protocol is not evidence of a capable reasoner.

The active product is the existing **historical daily Lab → Oracle → Evolve loop**. Reconstruct a trading day's available feeds; run Lab and retain its actual forecasts; advance the historical clock to obtain outcomes and later evidence; use Oracle to score and diagnose; let the lead agent or a worker with fixed instructions propose a reviewed, versioned improvement; continue on later days. Reuse the native graph, provider, contracts, run records and refinement machinery. Dataset adaptation serves this loop. It does not replace the product with a new quarterly-forecast benchmark.

Use the [TraderHarness daily adapter](docs/traderharness-daily.md) for richer native inputs: ten stocks, OHLCV, issuer headlines, announcement titles, historical corporate actions and CSI300 context. It reuses the acquired A-share source without running the separate five-session study. The forecast targets raw CNY close; rebased wealth is context only. XSHG sessions govern daily progression and matched evaluation. Observation close, reconstructed packet availability and Evolve maturity remain distinct. Source vintages and market expectations remain unverified. The [InvestorBench panel](docs/investorbench.md) retains three equities, 291 shared dates and 4,990 delayed date-bucketed summaries; [FNSPID](docs/daily-replay.md) retains full timestamped article bodies for a small AA slice. All preserve missing lanes and the full authored Lab. Earlier A-share and compact price-only comparisons remain development evidence. Full Lab execution, later Oracle and a real Evolve change must each be demonstrated through native receipts; preparing data alone is not completion.

The [returned research audit](docs/fundamental-research.md) is supporting analysis and an unselected alternative. Its scorer and numerical findings remain valid; the proposed fundamental-forecast pivot is not adopted. The remaining programme-budget authorization persists, with existing costs, unknown reservations and immutable limits preserved.

The repeatable entry is `python -m zenith daily init`, then `daily next`, native
`import-response`, and `daily review`. Read `docs/daily-replay.md`. The lead agent
or a fixed-prompt worker performs the reasoning; the controller handles source
binding and progression. It never fabricates completion or purchases inference.

The [two-issue empirical pilot](docs/empirical-forecasts.md#the-completed-two-day-sequence)
now demonstrates an actual reviewed procedure change reaching a later full Lab.
Both Labs and Oracles completed. The shrinkage candidate lost to unchanged-rule
arithmetic on the later issue and remains unselected. Do not turn this wiring
result into a financial-learning claim or spend a large cohort merely to repeat
a price-only formula through many reasoning nodes. The next useful question is
whether the admitted issuer news supports a reproducible forecast input beyond
recent prices. Require cited underlying facts, explicit missing expectations,
a declared numerical mapping and a direct-reasoner/price-only comparison.
The same native graph remains the development owner; no replacement benchmark
is selected. The [Herculean audit](docs/herculean-audit.md) records why its richer
historical news cannot presently supply that input.

Use [generations](docs/generations.md) to distinguish experimental adoption from
selection: `daily matchoff` freezes a reviewed challenger and incumbent on the
same later situations, the existing cohort executes and scores them, and
`daily retain` binds the reviewed choice to all comparison evidence. Initialize
the next generation with `daily init --retention`; its first issue must be after
the comparison's final truth cutoff. Repeated development selection is still
exposed historical research, not independent self-play or an untouched test.

The rules below govern individual controlled comparisons. They do not make one mutable field, one proposal, two nodes or a fixed data archive permanent project constraints. Coherent development revisions may change several components when needed; record their combined effect and use later ablations if attribution matters. Never modify a frozen study in place or rename repeatedly inspected development data as an untouched test. Read `AGENTS.md`, `docs/experiments.md`, the affected node skills, incoming edges and output contracts first. Native CP2 experiments still execute through Zenith and use its existing feedback authority.

For the explicit two-node financial experiment, use
[`research.trading_study`](docs/trading-study.md). It has its own typed expected-return
contract and long/cash evaluator; it is not a CP2 cohort. Its owner commands are
`freeze`, `development`, `learn`, `select`, and `final`. The FinMultiTime profile
adds dated news and filing facts to trailing price windows. Later review evidence
is training-only; manual investigator notes remain a separate audit. Freeze
runtime source through completion and preserve all proposals and provider calls.

1. State one hypothesis and the affected skills/edges. Prepare an admitted reasoning policy or graph variant. Record the proposed change, source commit, proposal prompt hash, and candidate artifact hashes. Check topology ranks, typed ports, subject/truth boundaries, and availability before expensive reasoning. The Lean interface proves contract-model properties, not that an LLM obeys a skill.
2. Declare the complete cohort before comparing results: fixed issue ids, feed snapshots, issue times, targets, horizons, development/holdout membership, week clusters, embargo, price basis, truth cutoff, loss, improvement threshold, candidate budget, and audited call ceiling. The cohort consumer evaluates matured frozen data; it does not establish prospective preregistration. Use `feedback` for live forecasts and their later maturity.
3. Run `python -m research cohort-freeze --spec <spec.json> --study <new-directory>`. Include baseline first and every bounded candidate in the immutable specification. Every preregistered candidate spends a slot, including candidates that fail. Do not add a candidate, change the evaluator, or revise membership after seeing scores in that study.
4. Run `python -m research cohort-next --study <directory>`. Follow its exact native argument arrays through `zenith run/resume`; complete agent handoff packets through native import. This command emits actions and makes no model calls. Use explicit provider/model identities and own-key native execution. The cohort audits its call ceiling after execution. The paid adapter additionally enforces its shared immutable call/token limits and reserves conservative cost before each request; all authorized probes and study runs must use that same budget. Inspect native attempts and provider quota independently.
5. Use each returned `cohort-attach` command to import its native manifest and full CP2 scope. Preserve all import receipts, including errors and pending runs. Complete node receipts must disclose comparable actual models; a routed alias alone is insufficient. Pending manifests retain their frozen identity. Accepted output bytes cannot change. Do not replace accepted runs with favorable samples.
6. Run `python -m research cohort-evaluate --study <directory>`. The feedback evaluator derives relative target-price error from actual CP2 forecasts and exact dated truth. All preregistered issues, targets, horizons, and candidates must have complete equal support. Missing truth and incomplete handoffs remain pending without partial scores. At least 20 distinct issues are required for proposals; the reported calendar-week count is not a significance test.
7. Retain all results. Fixed development improvement produces a candidate proposal with no live mutation permission. Read its native errors, model/call provenance, and context receipts before interpreting which intervention helped. Structural ancestry is not causal blame. New hypotheses use a new explicitly bounded candidate set/study; repeated historical selection still creates bias.
8. Finish heldout runs before deliberately invoking `cohort-evaluate --final-key <stable-key>`. The consumer selects the development champion before opening heldout outcomes and compares only it with baseline. A pending, interrupted, or failed final spends the seal. The same key returns the same receipt; another key is refused. Development comparisons and imports then close. Promotion requires separate review; do not automatically edit live skills or dossiers.

To derive the next hypothesis from development failures, use `reflection-packet`
to bind a complete native feedback proposal and the selected node's available
traces. Read the evidence, then `reflection-candidate` compiles one declared skill,
context-budget or incoming-edge change. With a verified parent `--study`, it also
emits a native candidate row preserving the measured model and graph identity.
Preregister that row in a new study; these commands neither run nor accept the
candidate. Follow the exact arguments and evidence boundaries in
`docs/experiments.md`.

For a probability-only hypothesis, the smaller replay adapter uses `freeze`, identity-baseline `trial`, bounded candidate `trial`, `status`, and once-only `final`. It wraps the actual admitted-event historical replay and native Brier score. Its candidate changes probabilities over frozen upstream forecasts; naming a node or topology in its provenance does not execute or optimize that graph. `recover` closes an interrupted local reservation only after its owner disappears. Candidate Python is trusted local code, not an OS sandbox.

Historical model training, remembered prices, retrospective narratives, dependent weeks/assets, and repeated development selection can contaminate apparent improvements. Synthetic fixtures establish executable contracts, not forecasting ability, significance, investment returns, or causal conclusions. Instant syntax/PIT/graph checks and historical measurements do not remove the waiting horizon for live truth.

The complete contracts, CLI commands, and twenty-issue consumer fixture are in `docs/experiments.md`. The bounded edit/evaluate/keep-or-discard pattern is adapted from [Karpathy autoresearch](https://github.com/karpathy/autoresearch/tree/228791fb499afffb54b46200aca536f79142f117); its code is not copied here. GEPA or other proposal methods may supply explicitly preregistered candidates; the evaluator and acceptance rule remain fixed.

The native [judgmental quantile branch](docs/judgmental-forecasts.md) supports
rich-evidence numerical beliefs without an identified cause. Freeze median and
uncertainty before truth, retain the full Lab/Oracle, and compare the actual
predictions with earlier-price controls. Evolve is the reviewed reasoning step
performed by the lead agent or a fixed-prompt worker; the controller carries its
accepted skill into later issues. Neither acceptance nor a single better day
establishes that the update procedure learns.
