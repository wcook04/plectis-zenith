PYTHON ?= python

.PHONY: demo replay test-current test validate validate-index

demo:
	"$(PYTHON)" scripts/demo_continuation_learning.py

replay:
	"$(PYTHON)" scripts/build_client_investigation_report.py replay-behavior examples/conformance/client-reuse-v2-low

# Current studies and their shared execution/publication boundaries. The complete
# retained suite stays available through `make test` and the source-checkout CI job.
test-current:
	"$(PYTHON)" -m pytest \
		tests/test_paper_references.py \
		tests/test_paper_reading.py \
		tests/test_continuation_learning.py \
		tests/test_continuation_rank_witness.py \
		tests/test_native_conformance_tasks.py \
		tests/test_conformance_study.py \
		tests/test_conformance_export.py \
		tests/test_conformance_budget_continuation.py \
		tests/test_direct_investigation.py \
		tests/test_direct_conformance.py \
		tests/test_direct_export.py \
		tests/test_client_investigation_tasks.py \
		tests/test_client_investigation_study.py \
		tests/test_client_investigation_report.py \
		tests/test_investigation_program.py \
		tests/test_provider_policy.py \
		tests/test_zenith_budgeted.py \
		tests/test_source_snapshot.py \
		tests/test_extraction.py \
		tests/test_strict_json.py \
		tests/test_reasoning_contracts.py \
		tests/test_progress_report.py \
		tests/test_progress_analysis.py \
		tests/test_web.py \
		tests/test_structure.py

test:
	"$(PYTHON)" -m pytest tests

validate:
	"$(PYTHON)" scripts/build_paper_references.py --check
	"$(PYTHON)" scripts/build_paper_reading.py --check
	"$(PYTHON)" scripts/check_structure.py
	"$(PYTHON)" scripts/check_extraction.py
	"$(PYTHON)" -m zenith validate

validate-index:
	"$(PYTHON)" scripts/build_paper_references.py --index
	"$(PYTHON)" scripts/check_structure.py --index
