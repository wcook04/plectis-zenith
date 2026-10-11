.PHONY: test validate benchmark

test:
	python -m pytest tests

validate:
	python -m zenith validate

benchmark:
	python -m benchmark.run --output work/benchmark/benchmark.json
