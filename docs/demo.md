# Prepare one synthetic observation pair

**Experimental research prototype.** The public example uses synthetic observations of a disclosed toy generator. No predictive improvement has been demonstrated.

The preparation creates earlier and later packets for an invented abstract System A. Measurements, subsystems, environment, events and interventions are five synthetic perspectives of the same generated state; derived values are computed from them. No source archive or network is needed. Use the native CLI's `prepare-demo --help` for current command options.

Pass the earlier packet to `python -m zenith prepare lab`, declaring its cutoff and a later horizon. Preparation loads the six feed artifacts and prepares the first agent request. It makes no model call and produces no completed forecast. See [the current receipt](../examples/demo/result.json). Agent responses are imported with `python -m zenith import-response`; authored teaching answers must not be presented as model execution.

After Lab completes, Oracle receives that frozen subject and the later packet. Freeze numeric `snapshot_value` and `target_value` forecasts for named observables at the exact horizon. Keep unavailable or unmatched outcomes unresolved. Evolve may propose one reviewed change; compare original and revised graphs on further held-out cases under the same information and budget.

This teaches the protocol. It does not validate physical dynamics, predictive accuracy or an improvement from revision.

## Synthetic offline first run

Run `python -m zenith demo --output work/first-run` to execute authored Lab responses without an API key or network. It demonstrates contracts and retains an intentionally rejected response. It is not model inference or a forecasting result. See the generated `summary.json` and README.
