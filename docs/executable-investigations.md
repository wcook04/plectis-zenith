# Executable investigations

Zenith now tests whether a language model can turn a measured failure into a reusable computation. The retained object is executable source, its stated scope, the counterexamples used to repair it, and exact dependency hashes. A future case should benefit from that object without buying the same reasoning again.

The useful output is a set of supported findings together with unresolved checks. Finding duplicated telemetry does not imply that latency stayed constant. Missing coverage can prevent a latency conclusion while leaving duplicate delivery and workload shift established. This composition is the central change from a single terminal diagnosis.

## From the five returns to one mechanism

All five supplied prototypes reproduced locally: 198 tests, ten successful verification/reproduction commands. They demonstrate finite searches through researcher-authored components. Their reported query costs are synthetic effort measures, not API dollars. The [assimilation receipt](breakthrough-returns-20261013.json) binds the archive hashes, commands and outputs.

| Return | Retained contribution | Boundary |
|---|---|---|
| Representations | A useful representation separates cases that require different decisions | A finite authored grammar is not model-discovered semantics |
| Investigation | A reusable procedure can acquire evidence before computing an answer | Query availability does not establish learned acquisition value |
| Learning from failure | Repair the computation under an explicit scope, then replay the whole investigation | A wrong outcome alone does not identify its cause |
| Cumulative memory | Retain counterexamples and dependencies with the executable object | Small witness sets preserve only the hypothesis class actually checked |
| System synthesis | Use operational time-series investigations and preserve simultaneous findings | A single-action fault label loses compound evidence |

The new campaign crosses the main missing boundary: actual model-authored Python rather than selection from a researcher-written recipe catalogue. It still uses a designed task, synthetic data and an engineered evaluator. It does not claim an invented scientific ontology or general self-improvement.

## The task and the learned object

Raw child-operation intervals describe requests before and after a deployment. Natural-language source documentation identifies the fields. A quantity contract asks for one of three meanings: active time, elapsed time including idle gaps, or billed worker time. Overlap must be counted differently for those quantities. Population tables include all requests and supply the workload proportions for a standardized comparison.

The investigator returns a numerical after/before ratio and a latency conclusion when the evidence supports it. It also reports independent duplicate-delivery and workload-shift findings, plus incomplete-coverage, unknown-unit and conflicting-event obligations. The task supplies these concepts and decision thresholds. The model must author their executable realization and composition.

`zenith/investigation_program.py` executes a restricted Python subset in a separate process with a wall timeout, CPU limit and monitored memory usage with an empty environment. There are no imports, ambient files, network calls or arbitrary attributes. This is a restricted research harness, not a general operating-system sandbox. Tables enter only through the logged acquisition callback; candidate context excludes generator labels, hidden tables and sequential case IDs. Acquisition receipts bind the table and returned data hash.

The process is Lab → Oracle → Evolve in concrete terms: execute the current program; compare its answer with the independent evaluator; give the model measured witnesses and the incumbent; execute the replacement against the complete development set. A proposal enters that learner's local memory only if its score improves (exact findings and unresolved sets; ratio tolerance 1% relative or 0.005 absolute) without breaking any previously correct development case. This is experimental selection, not deployment approval or proof of universal correctness.

## Frozen campaign

The runner prepares all cases, hashes the dataset, and archives the executable source before inference. Three repeated learners use the same cheap model and temperature-zero settings; they are not independent model samples. The initial version permits three proposals; the corrected runner permits six and stops early when development is perfect. Every candidate and rejected attempt is retained.

There are 64 development cases, 256 held-out cases using combinations absent from development, and 64 cases with a renamed source schema. Half the held-out cases require abstaining on the numerical conclusion while preserving other supported findings. A model-authored field mapping adapts the new schema; a fixed host transform applies it without changing numbers or the frozen numerical program. This measures renamed-schema binding, not discovery of a new domain.

After freezing, the evaluator scores both the first proposal and the final program on the same held-out cases. This measures improvement during development separately from one-shot compilation. It does not isolate the effect of feedback from additional attempts and examples. Deleting the learned program restores the declared summed-duration incumbent. An independent handwritten reference, using the same observed tables, checks that the task is solvable; the latent-data evaluator uses a different interval calculation.

On 32 paired held-out cases, additional controls answer directly or receive a prose translation of the first learner's final algorithm. Both get every raw table; neither has a code-execution tool. These comparisons measure an end-to-end compilation/execution advantage, not an isolated graph or memory advantage. Prose is intended to preserve the algorithm, but semantic equivalence is not certified. The first learner is the predeclared primary comparison; there is no best-of-three selection.

All inference is serialized through the existing budgeted provider, with verified inexpensive Chinese models and a $1.50 campaign ceiling. The initial DeepSeek V4.1 Flash campaign planned 29 calls. Corrected six-proposal campaigns plan at most 38, with an early stop for solved development. Each version freezes its model, host, reasoning setting, prompts and seeds; no automatic retries occur. Failed calls and non-executing programs remain failures. The [versioned evidence receipt](investigation-learning-20261013.json) records exact settings, outcomes and costs rather than treating different versions as a controlled model comparison.

The public evidence includes frozen model-authored programs, synthetic input tables, expected outputs, acquisition traces, executor and evaluator source. `python scripts/build_learning_report.py replay` re-executes those programs with zero inference calls and checks individual records, not only aggregate scores.

## Run and inspect

```sh
python -m research.investigation_learning_study prepare --output work/learning-run --model deepseek/deepseek-v4.1-flash --provider-slug deepinfra/fp8
python -m research.investigation_learning_study run --output work/learning-run --env-file /path/to/local.env
python -m pytest tests/test_investigation_program.py tests/test_provider_policy.py
```

`research/operational_cases.py` owns task generation, the independent evaluator and observed-data reference. `research/investigation_learning_study.py` owns the frozen protocol and comparisons. `zenith/investigation_program.py` owns execution. The existing provider, budget and source-archive machinery remain authoritative. The financial investigator remains available under its [historical method](investigator.md).

The current runner defaults to the broad feedback selection used in V5. `--feedback-style compact` selects the V6 follow-up rule; it did not demonstrate better repair. The versioned receipt retains all complete and partial outcomes.

The next scientific boundary is an equal-tool one-shot compiler and memory comparison on genuinely new semantic contracts and real operational data. A positive synthetic result earns that experiment; it does not establish a forecasting advantage or an autonomous research breakthrough.
