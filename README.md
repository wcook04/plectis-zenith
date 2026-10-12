# Plectis Zenith

**Experimental research prototype.** The public example uses synthetic observations of a disclosed toy generator. No predictive improvement has been demonstrated.

Zenith studies forecasting a changing, partially observed system from heterogeneous, incomplete, overlapping and sometimes delayed perspectives. A reasoning graph reconciles what the observations mean and when they were available, distinguishes missing evidence from conflicting evidence, forms competing explanations and selects explicit future targets. Saved intermediate outputs expose the support chain. Different feeds are not independent votes.

Lab freezes predictions at a cutoff. Oracle evaluates them against later observations and proposes a failure hypothesis. Evolve proposes one reviewed revision for a held-out matched comparison. Applicability requires observations linked to the same system, entity and time, a declared target and horizon, and later measurable truth.

Physical problems motivate the design. For heat transfer, a heated chamber or greenhouse could combine temperature sensors, heater power, weather and door or vent logs to predict temperature six hours ahead. For damped vibration, camera position, accelerometer readings, applied-force and calibration logs could support a displacement or acceleration target one second ahead; position alone does not reveal direction of motion, so history matters. For fluid transport, flow, pressure, dye observations and valve logs could support a downstream concentration target, provided geometry and boundary conditions are supplied.

Sensors expose different functions or aspects of state, and known forces, boundaries and interventions condition the future. Proposed reasoning aligns clocks and units, recognises source dependence, compares sensor faults with state or regime changes, and selects or parameterises an appropriate physical model or numerical tool where available. It must freeze the target, horizon and uncertainty. Narrative is not a substitute for equations. Solver integration and these applications have not been implemented or tested; some state can remain unobservable even with history. See [Tedrake's Output Feedback](https://underactuated.mit.edu/output_feedback.html). A language model is not assumed necessary or better than direct or numerical prediction.

The [three-page paper](paper/zenith.pdf) explains the protocol and proposed context-conditioned prompt controller. The [teaching website](site/README.md) exposes native node instructions, dependencies and public evidence through a read-only API.

![Earlier observations through Lab, Oracle, Evolve and a later comparison](docs/graphs/replay.svg)

The public example is an invented abstract System A with five synthetic source perspectives: measurements, subsystems, environment, events and interventions. A sixth derives summaries from those inputs. It is a protocol fixture, not evidence that reasoning adds predictive value or a physically validated simulation. A general observation contract does not establish reliable prediction of arbitrary scientific or physical systems. See [data](docs/data.md), [demo](docs/demo.md), [current status](docs/status.md) and [research boundary](RESEARCH_NOTICE.md).

Each numeric observable carries `target_id`, `value`, `unit`, `observed_at` and `available_at`. Predictions freeze `snapshot_value` and `target_value` at an exact declared horizon; later outcomes must match that target. Preserve missingness and information availability rather than filling them from hindsight.

The current demonstration prepares the first request with zero model calls. It has no completed forecast, Oracle diagnosis or Evolve comparison. Historical runs do not establish results for this configuration.

```sh
python -m pip install -e '.[test]'
python -m zenith validate
python -m zenith prepare-demo --output state/demo/system-a
python -m zenith serve --port 4175
```

The API serves the paper, graph and published observations. Follow [site/README.md](site/README.md) to build the teaching frontend. Offline checks and document builds:

```sh
python -m pytest tests
python scripts/build_graphs.py
tectonic paper/zenith.tex
```

Native agent responses pass through import-response and validation. Provider execution requires explicit configuration and the existing budget. Never commit credentials or private run payloads. Exact graphs live in `codex/substrate/nodes/`; runtime behavior lives in `zenith/`; evaluation lives in `feedback/`.

A diagnosis suggests an experiment. Only a separate comparison can establish whether a revision improves the declared score, with regressions, coverage, uncertainty and cost visible.
