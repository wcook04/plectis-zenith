# Run the demonstration

**This is not financial advice.** [Research notice](../RESEARCH_NOTICE.md).

## Offline teaching example (start here)

`python -m zenith demo --output state/demo/offline-example` is a fully synthetic,
offline first run. It needs no inputs, credentials or network. It authors its own
feed snapshots, executes the real native Lab graph through the original engine,
`runtime.start`/`import-response` and contract validation, deliberately imports one
invalid response (rejected and retained), corrects it, and reports the completion
counts it actually observed in `summary.json`. Everything it generates stays under
`--output`, and an existing nonempty output directory is refused.

It is a **synthetic contract demonstration**: completing the graph shows the
contracts execute, not that forecasting improved. The generated README and
summary retain the research notice and identify the synthetic inputs.

## Prepare one mixed snapshot pair (real inputs, optional)

`prepare-demo` uses real saved stocks, ETFs and prediction markets. It replaces
only macro and news, then reruns CALC. It never reads the original macro/news
payloads and makes no network or model calls. The source directories must contain
`runtime_context.json` and the three retained `artifacts/global_*_feed.json` files.

```sh
python -m zenith prepare-demo --earlier-source /path/to/earlier \
  --later-source /path/to/later --output state/demo/my-pair
python -m zenith prepare lab --run-id DEMO_LAB \
  --feed-source state/demo/my-pair/earlier \
  --time-anchor <latest-permitted-earlier-collection-time> \
  --horizon <declared-later-time> --context-profile compact_feeds
```

The second command loads the actual graph and writes the first agent request.
Those private prompts contain real inputs. Agent responses are imported through
`python -m zenith import-response --packet <request.json> --response <answer.json> --model <author>`.
Model execution and permission to send source data to that provider need explicit
configuration. Do not call an authored teaching response an LLM result.

Once the Lab completes, pair it with the later mixed packet:

```sh
python -m zenith run oracle --run-id DEMO_ORACLE --subject-run DEMO_LAB \
  --truth-run state/demo/my-pair/later --context-profile compact_feeds
```

The current prepared example loaded six feeds and stopped at `lab_seed_state`
awaiting its first response. No CP1, CP2, forecast or Oracle result exists for
this edition. See [the receipt](../examples/demo/result.json).

Only the two files under the prepared directory's `public/` subdirectory are
intended for public input presentation: per-feed provenance and synthetic
replacements. Real inputs and recomputed CALC stay beside them in private
`earlier/` and `later/` directories. Copying a file into `public/` is not a licence
check; the exporter itself deliberately withholds the real payloads.
