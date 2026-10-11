from copy import deepcopy
from fractions import Fraction
import pytest

from benchmarks import repair_controls as control


def test_training_selects_actual_context_repair_and_unseen_values_generalize():
    train = control.fixtures('omitted_relevant', seed=2, count=20)
    baseline = control.policy({'split': 0, 'notes': 0})
    selected, receipt = control.select(train, baseline)
    assert receipt['selection'] == 'restore_split'
    assert receipt['trials']['unchanged']['contract_correct'] == 0
    assert receipt['trials']['restore_notes']['contract_correct'] == 0
    before = deepcopy(train)
    test = control.fixtures('omitted_relevant', seed=7, count=100, assessment=True)
    result = control.summarize(test, selected)
    assert result['contract_correct'] == result['answered'] == 100
    assert train == before
    assert selected['nodes']['normalize']['incoming_weights'] == {'split': 1, 'notes': 0}


def test_missing_future_and_conflicting_sources_do_not_reward_fabrication():
    for scenario in ('absent_source', 'future_source', 'conflicting_source'):
        cases = control.fixtures(scenario, seed=3, count=10)
        baseline = control.policy({'split': 1, 'notes': 0})
        selected, selection = control.select(cases, baseline)
        assert selection['selection'] == 'unchanged'
        result = control.summarize(cases, selected)
        assert result['contract_correct'] == 10
        assert result['answered'] == result['required_numeric_answers'] == 0
        assert result['numeric_mae_on_answered'] is None


def test_observed_omission_is_not_a_causal_verdict_or_permission_to_change():
    for scenario in ('healthy', 'irrelevant_omission', 'wrong_calculation'):
        cases = control.fixtures(scenario, seed=4, count=20)
        baseline = control.policy({'split': 1, 'notes': 0})
        _, selection = control.select(cases, baseline, wrong_operator=scenario == 'wrong_calculation')
        assert selection['selection'] == 'unchanged'
        assert selection['causal_verdict'] == 'not_established'
        if scenario == 'wrong_calculation':
            assert all(row['contract_correct'] == 0 for row in selection['trials'].values())


def test_selector_cannot_see_assessment_or_succeed_by_repair_name():
    cases = control.fixtures('omitted_relevant', seed=5, count=20)
    baseline = control.policy({'split': 0, 'notes': 0})
    chosen, _ = control.select(cases, baseline)
    renamed = deepcopy(chosen)
    renamed['variant_id'] = 'arbitrary_label'
    renamed['policy_sha256'] = control.policy_sha256(renamed)
    assert control.summarize(cases, chosen)['contract_correct'] == control.summarize(cases, renamed)['contract_correct']
    # A leaf defect survives the same correctly named/context-restoring policy.
    assert control.summarize(cases, chosen, wrong_operator=True)['contract_correct'] == 0


def test_same_missing_view_can_hide_distinct_worlds_so_answer_stays_unknown():
    first = control.fixtures('absent_source', seed=8, count=1)[0]
    second = deepcopy(first)
    # Distinct possible hidden ratios cannot be recovered from identical inputs.
    worlds = [Fraction(first['sources']['quote']['price']) / ratio for ratio in (2, 5)]
    assert worlds[0] != worlds[1]
    selected = control.policy({'split': 1})
    assert control.execute(control.execution_input(first), selected)[0] is control.execute(control.execution_input(second), selected)[0] is None


def test_changed_policy_cannot_emit_receipt_under_stale_identity():
    case = control.fixtures('omitted_relevant', seed=2, count=1)[0]
    stale = control.policy({'split': 0})
    stale['nodes']['normalize']['incoming_weights']['split'] = 1
    with pytest.raises(ValueError, match='policy_sha256 mismatch'):
        control.execute(control.execution_input(case), stale)


def test_healthy_control_has_no_omission_candidate():
    cases = control.fixtures('healthy', seed=4, count=20)
    _, selected = control.select(cases, control.policy({'split': 1, 'notes': 1}))
    assert list(selected['trials']) == ['unchanged']
    _, omitted = control.select(cases, control.policy({'split': 1, 'notes': 0}))
    assert set(omitted['trials']) == {'unchanged', 'restore_notes'}


def test_execution_rejects_oracle_labels_and_reports_cost_of_restoration():
    cases = control.fixtures('omitted_relevant', seed=4, count=20)
    baseline = control.policy({'split': 0, 'notes': 0})
    with pytest.raises(ValueError, match='never oracle labels'):
        control.execute(cases[0], baseline)
    restored = control.policy({'split': 1, 'notes': 0})
    assert control.summarize(cases, restored)['mean_retained_source_chars'] > control.summarize(cases, baseline)['mean_retained_source_chars']
