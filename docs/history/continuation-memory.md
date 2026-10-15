# Retaining questions that help the next acquisition

Historical research record. References to “current” or “next” describe this stage; see [today’s findings](../status.md).

This experiment asks whether learned tests provide useful memory beyond retaining the same measured answers. Its input is six executable programs acquired in Zenith's earlier DeepSeek source-rule study. An authored exact learner treats their behavior as a collection of functions on integer sequences. It learns a joint state representation, then tries to add a previously withheld program.

A state coordinate has an operational meaning: “what would program j return if continuation e followed this history?” Counterexamples add program/continuation pairs that distinguish behavior the previous coordinates missed. The learner fits exact rational transition and readout matrices from queried outputs. The acquired test directions are therefore distinct from the cached answers used to fit them.

The new comparison predeclares six conditions. Each program is withheld once; the other five are acquired first. Both extension arms start with byte-identical measurement caches. One retains the acquired continuation tests; the other starts with the same generic empty-output tests and original seed anchor. Neither receives an extra anchor for the withheld program. Access histories and transition matrices are fitted again, so the claimed transferred object is the selected questions, not warm-started matrix arithmetic.

Each condition records initial cost, extension cost, complete lifetime cost, requested query/symbol counts, model dimensions and later outputs. All teacher executions are local program calls; the follow-up makes no language-model calls. Six conditions over the same six programs are correlated robustness checks, not six independent domains. The hypothesis was selected from the return's earlier result; this is an exploratory follow-up, not a preregistered novel scientific discovery.

## Verification and controls

The archive contains the protocol frozen before acquisition, exact program teachers and learning implementation, complete query caches/ledgers, acquired models, all condition outcomes and an independent verifier. Verification re-executes source queries, checks cache/cost accounting, reconstructs the common initial caches, evaluates later outputs and recomputes exact reference certificates.

Certificates establish equality to the supplied rational linear reference on every finite word over the declared alphabet of integers from -8 through 8. They do not establish that an unknown external source obeys that class. The native program outputs and separately sampled longer histories provide additional finite checks. The representation class, extraction algorithm, seed tests, challenge generator and certificate machinery are supplied.

Three alternatives matter. Cached-answer-only acquisition isolates the contribution of learned test directions. Independently acquired ordinary modules test whether joint abstraction was worth building at all. A fitter informed of the original finite generating family needs no additional teacher executions after the previously supplied identification observations. The last control has stronger prior knowledge; its advantage still prevents claiming that the new machinery is the best solution to this particular known family. Later-stage savings do not erase initial acquisition cost.

The mechanism adapts the established observation-table and counterexample refinement construction described in [Exactly Learning Weighted Automata over a Field](https://www.cs.ox.ac.uk/people/james.worrell/MA-learning.pdf). A finite challenge list replaces a genuine equivalence oracle during learning. The certificate is a separate evaluation check, not an oracle secretly available to construction. No new automata-learning theorem or general learning-rule improvement is claimed.

## Relation to the active system

The result worth pursuing is that an experience-derived *question* can remain useful after its original answer has already been cached. This gives a concrete target for the [model-generated investigation loop](../studies/native/conformance-study.md): retain useful executable experiments as well as repaired code, then remove only those experiments in a later-task comparison. The native live pilot and this algebraic follow-up test complementary mechanisms; a shared vocabulary does not establish that their general integration already works.

The [research programme](../../program.md) defines the next boundary: changed client mechanisms, an acquired investigation procedure, matched earlier experience, and full acquisition plus execution cost. [Return assimilation](advance-returns-20261014.md) records the attribution and earlier controls.

## Measured results

The six conditions below use the same six archived teachers; each is withheld once. Counts are additional local teacher executions during extension, not model calls.

| Withheld teacher | Cache only | Retained questions | Saved | Joint lifetime with retention | Separate modules, full lifetime |
|---|---:|---:|---:|---:|---:|
| 0 | 740 | 463 | 277 | 5686 | 3071 |
| 1 | 2049 | 1642 | 407 | 5445 | 3071 |
| 2 | 1456 | 708 | 748 | 5427 | 3071 |
| 3 | 1850 | 1642 | 208 | 5445 | 3071 |
| 4 | 1254 | 463 | 791 | 5698 | 3071 |
| 5 | 1650 | 1198 | 452 | 5441 | 3071 |

Retained questions reduce extension queries in all six matched-cache conditions, by 11.2%–63.1%. This isolates value beyond cached answers inside this learner. The joint representation has 16 coordinates; separate models total 25, yet cost fewer teacher executions overall. Fewer state coordinates therefore do not establish a cheaper learning architecture. Runtime, symbol and arithmetic counters are retained alongside query counts; these units are not interchangeable.

A separately frozen follow-up tried to carry the useful part into the simpler architecture. It transferred every unique learned suffix from five ordinary modules to the sixth, with identical empty target caches and no target answers. That proposal mostly failed:

| Target | Ordinary acquisition | With transferred suffixes | Queries saved |
|---|---:|---:|---:|
| 0 | 258 | 380 | -122 |
| 1 | 622 | 671 | -49 |
| 2 | 447 | 574 | -127 |
| 3 | 803 | 768 | 35 |
| 4 | 336 | 477 | -141 |
| 5 | 605 | 671 | -66 |

All resulting models pass their checks. The loss is excess acquisition work, not wrong final predictions. Blindly importing questions is therefore not a demonstrated improvement. A future relevance selector must pay for its own selection and acquisition work, and beat ordinary learning on fresh mechanisms before becoming the default. We did not tune a subset against these six outcomes.

Independent verification of the first study reran 77,865 teacher queries, 30 exact certificates and 18,432 later program outputs. The second reran 6,612 queries, 12 certificates and 1,536 later outputs. Verification work is separate from the acquisition counts above. Both studies used zero new model calls.

## Reproduce

The [portable evidence bundle](../../examples/continuation-memory/leave-one-out-v1/README.md) includes both protocols, every condition, source, native teachers, query ledgers, models and the independent verifier. Unpack its `source.zip` into a new directory, then run:

```sh
python3 -I verify_all.py --out run-v1
python3 -I verify_all.py --out run-v2
```

The verifier reruns acquisition and checks every query, counter and certificate. See the bundle README for fresh-output reproduction commands. Its source manifest and explicit metadata-projection receipt preserve source attribution without publishing personal paths.
