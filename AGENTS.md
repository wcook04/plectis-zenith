# Working in Zenith

Read README.md and program.md. Preserve the original daily loop: historical
feeds, Lab predictions, later Oracle feedback, reviewed Evolve changes and
matched later comparison. The author requested a barebones repo and a paper
of at most three pages. Do not restore removed benchmark/survey/UI machinery.

The executable nodes, contracts and engine own behavior. Inspect their inputs
and outputs before changing them. Preserve the full Lab and Oracle paths,
evidence clocks, missingness, frozen forecasts and failed attempts. A diagnosis
is a hypothesis; a changed policy still needs later evaluation.

Use the native CLI. Agent responses go through import-response and validation.
Provider execution must be explicit and respect the existing immutable budget.
Never include credentials or private runtime artifacts in Git.

Run graph validation and the relevant offline tests. Run the full retained suite
after runtime changes. Regenerate graph diagrams with scripts/build_graphs.py;
keep extraction hashes accurate. Commit only owned changes and preserve other
work. Historical studies and private originals live in the research archive.
