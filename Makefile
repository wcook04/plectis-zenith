.PHONY: test validate

test:
	python -m pytest tests

validate:
	python -m zenith validate
	python scripts/check_extraction.py
