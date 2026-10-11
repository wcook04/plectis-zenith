# Working in Plectis Observatory

Read README.md and docs/research-boundary.md first. Keep this repository portable and independent of any private collector checkout.

Benchmark results must be generated from the pinned licensed source, with frozen time splits and future-label fields excluded from predictors. Do not edit generated web/data/benchmark.json or prediction CSVs by hand. Preserve source hashes, attribution, labels, exclusions and simple baselines. Report error metrics as error metrics, never as profit or investment performance.

The optional collector bridge is an explicit aggregate allowlist. Never publish raw prompts, current asset-level forecasts, private feeds, API keys, absolute local paths or provider response prose. Do not add trading actions, personalised portfolio recommendations or broker inducements as incidental features.

Use the standard library unless a concrete requirement justifies a dependency. Run `python3 -m unittest discover -s tests -v` and regenerate the benchmark after changes. Check the actual browser interface at desktop and narrow widths for UI changes. Commit only owned changes. Public deployment requires a separate release decision with content, data-rights and UK perimeter review.
