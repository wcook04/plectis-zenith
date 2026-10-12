# Current result

The shared-universe basket backend completed a real-data comparison using **147 instruments, six research baskets and 17 index histories**. The model was `inclusionai/ling-3.0-flash` through OpenRouter. It made **221 calls**, with reported inference cost **$0.0217910322**.

Four dates in 2023 supplied development evidence. Evolve proposed an instruction requiring specific observed patterns in investigation reasons; that instruction was frozen before six test dates in 2024. The numerical store enforced historical cutoffs and the evaluator scored every basket.

## Measured comparison

| Held-out forecast procedure | Mean squared return error |
|---|---:|
| All-universe numerical ridge | 0.0006556543 |
| Directed graph | 0.0006556543 |
| Revised directed graph | 0.0006556543 |
| Single controller | 0.0006556543 |
| Undirected investigations | 0.0006519576 |
| Zero-return reference | 0.0006458906 |

**The revision was not retained.** Directed, revised and serial forecasts equal the numerical baseline in this pilot. Zero return had the lowest aggregate loss. There is no demonstrated forecasting advantage for the graph or instruction revision. Six dates are a small descriptive comparison, not a claim of statistical superiority.

Eight of the 32 model arms failed final validation: the model assigned a numerical candidate to a target for which that candidate had not been calculated. The predeclared failure policy retained the entire numerical baseline vector and included those cases in the score. These failures are visible in the [result](../examples/baskets/result.json), rather than discarded. The revision's diagnosis is model-generated and has not been independently established as causal or numerically correct.

The first attempted endpoint, `nex-agi/nex-n2.5-mini`, timed out on eight requests and its budget stopped. Those requests were not retried; their actual cost remains unknown, with a total conservative reservation of $0.004005700. A separate successful Ling feasibility check cost $0.000001029. Including that check, known cost is $0.0217920612; adding the full timeout reservation gives a conservative ceiling of $0.0257977612 for these attempts.

## Evidence and implementation

- [Public protocol and source audit](../examples/baskets/protocol.json)
- [Every forecast, outcome and per-target loss](../examples/baskets/forecasts.json)
- [First chronological test trace and exact proposed revision](../examples/baskets/trace.json)
- [Native graphs, numerical method and reproduction](baskets.md)
- [Data licence and limitations](data.md)

The read-only API serves these reviewed records. No frontend redesign was made. Full source observations, intermediate provider records and failed attempts remain local. The older [System A fixture](demo.md) remains a separate synthetic preparation example.
