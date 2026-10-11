.PHONY: build test serve

build:
	python3 -m benchmark.run --output web/data/benchmark.json

test:
	python3 -m unittest discover -s tests -v

serve:
	python3 -m observatory.serve --port 8768
