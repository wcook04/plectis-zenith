# Kept experience: protocol (frozen before held-out calls)

## Question

When an AI tester finds or misses a mistake, does keeping that experience help the same fixed model expose hidden mistakes in programs it has never seen, under the same small test budget?

The model's weights never change. What changes is what it is shown: nothing, generic advice, its own earlier testing record, or a playbook it wrote from that record.

## Programs and hidden faults

- **Programs:** the 164 HumanEval problems with EvalPlus's augmented inputs and input contracts (HumanEvalPlus v0.1.10, sha256 `42526ec0…5bd7f`). Each problem supplies a public specification (signature, docstring, examples), a reference solution, the original HumanEval test inputs and roughly a thousand augmented inputs.
- **Natural faults (primary):** solutions sampled from three code models (ChatGPT, CodeGen-16B, InCoder-6B; EvalPlus v0.1.0 release, temperature 0.8) that return the reference's answer on every original HumanEval test input but differ on at least one augmented input. These are mistakes real models made that the original human-written tests did not catch. Faulty solutions with the same set of failing augmented inputs count once (one fault class).
- **Mechanical faults (secondary):** single-site mutants of the reference (relational, arithmetic, logical, constant and condition operators), filtered by the same rule.
- Neither the study author nor the tested model selects faults. The filter is a fixed execution rule (`research/kept_experience/natural.py`).

## Task given to the model

The tester sees one problem's specification and its input preconditions. It must choose **K = 5** inputs. Each valid input is executed on the reference and on every hidden fault class of that problem; any difference in return value or exception type exposes that fault class. Inputs that violate the preconditions are discarded and still use budget. The model never sees the faulty code, its outputs or the augmented inputs of the problem it is testing.

**Score per problem:** the fraction of that problem's fault classes exposed. **Primary metric:** the mean over held-out problems, averaged over replicates.

## Splits

Problems with at least one natural fault class are ordered by `sha256("zenith-kept-experience-2026-10-19|" + task_id)`. The first quarter is **practice** (the only source of experience), the second quarter **development** (pilots, sanity checks and the playbook revision), and the second half **held-out** (run once, after this protocol is committed).

## Arms

| Arm | What the model is shown besides the specification |
|---|---|
| `cold` | nothing |
| `advice` | a fixed paragraph of generic testing advice (boundaries, ties, ordering, types, size, interactions) |
| `kept` | the practice record: for each practice problem, the inputs it chose, how many faults they exposed, and up to three missed faults with the faulty code and an exposing input |
| `lessons_v1` | a ≤400-word playbook the model wrote from the practice record |
| `lessons_v2` | the playbook revised by the model after `lessons_v1` was used on development problems and its misses were revealed |
| `imagine` | asked to write its own reference and eight plausible buggy versions, then twenty candidates; the host picks five by greedy cover of the imagined bugs (only model-written code is executed for selection) |
| `imagine_kept` | `imagine` with the practice record |
| `random_plus` | five inputs drawn uniformly from EvalPlus's augmented inputs (exact expectation over 200 draws); no model |

Model: `deepseek/deepseek-v4.1-flash-1017` through OpenRouter, pinned to the `morph/fp8` endpoint, reasoning effort `high`. Two replicates per model arm on held-out problems. Total spend cap $8 across the whole study.

**Delivery rule.** A reply whose answer field is empty, or whose final python block lacks `INPUTS` (`CANDIDATES` for the imagined-fault arms), is a delivery failure and is requested again, at most three times, identically in every arm. Undelivered attempts and their costs stay in the record. The rule was added during the practice phase after two of 28 replies left the whole answer in the reasoning channel; those two replies are kept in `replies_superseded/`.

## Development pilot (non-confirmatory)

One replicate per arm on the 29 development problems, natural faults, mean share of fault classes exposed: none 0.569, advice 0.635, record 0.688, playbook v1 0.734, imagined faults 0.668, imagined faults with record 0.608, random augmented inputs 0.376. The pilot changed no prompt, arm or analysis. Its only use is the planned one: the playbook-v1 development misses (`frozen/development_record_for_v2.md`) were given to the model to write playbook v2 (`frozen/lessons_v2.md`). Practice: none 0.784, random 0.410.

## Hypotheses and analysis

1. **H1 (primary):** `kept` exposes more natural faults than `cold`.
2. **H2:** `lessons_v1` exposes more than `cold`.
3. **H3:** `kept` exposes more than `advice` (experience beyond generic advice).
4. Exploratory: `imagine` vs `cold`; `imagine_kept` vs `imagine`; `lessons_v2` vs `lessons_v1` (does the improver improve?); every arm vs `random_plus`; mechanical faults as a secondary population.

The unit is the problem. Report the paired mean difference with a 95% bootstrap interval over problems and a two-sided sign test. No arm, prompt or analysis changes after the first held-out call; any later change becomes a new, separately labelled version. Every call, cost and raw reply is kept; scoring replays with no network calls.

## Limits stated in advance

All faults come from one benchmark of short, single-function Python problems. Natural faults come from three older code models; mechanical faults share operators across splits. A positive result would show transfer of testing experience to unseen problems within this benchmark, under a five-input budget, for one model. It would not show transfer to large systems, other languages or other models.

## Addendum A (19 October 2026, before any experiment 2 call)

**Written after** the five main held-out arms of experiment 1 were scored. Their result: no experience condition differed measurably from none (playbook v2 +3.0 points, 95% interval −3.9 to +10.3; playbook v1 −1.4; advice −3.4), while the model's chosen inputs beat five random EvalPlus inputs by 26 points. Experiment 1's record, imagined-fault arms and analysis are unchanged.

**Experiment 2: experience without reasoning.** One question follows from experiment 1: at high reasoning effort the model may already derive what the record and playbooks say. Experiment 2 repeats four experiment 1 prompts with reasoning switched off (`reasoning: {"enabled": false}`, verified to return zero reasoning tokens on the pinned endpoint): `cold_nr`, `kept_nr`, `lessons_v1_nr`, `lessons_v2_nr`. Same 58 held-out problems, same frozen record and playbooks (none of which was derived from held-out problems), two replicates, same delivery rule, scoring and analysis.

- **H5:** with reasoning off, `kept_nr` and `lessons_v2_nr` each expose more natural fault classes than `cold_nr` (paired by problem, bootstrap interval and sign test).
- Exploratory: whether either recovers the gap between `cold_nr` and experiment 1's `cold`.

Reusing the held-out problems is a second look at the same problems; a positive result would need confirmation on fresh problems.

**Post-freeze code changes (none affects calls or scores):** `study.py` writes score files with `default=repr` so a bytes literal proposed as an input can be stored; `harness.py` adds the reasoning-off option and the `_nr` arm suffix for this addendum.
