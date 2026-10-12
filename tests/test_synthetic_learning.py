"""Known-world checks are not financial or LLM learning claims."""
from copy import deepcopy
import json

import pytest

from research import synthetic_learning as learning
from research.__main__ import main
from zenith.providers import text_digest


def test_interpretation_uses_prior_guidance_not_growth_and_preserves_missingness():
    forward, _ = learning.make_day(0, 1729)
    forward['reports']['SYN1'].update(year_ago_profit=100, prior_guidance=180, new_guidance=150)
    before = deepcopy(forward)
    wrong = learning.forecast(forward, learning.BASELINE)
    corrected = learning.forecast(forward, {'comparison': 'prior_guidance', 'ranking': 'signal', 'scale': .08})
    assert wrong['interpretation']['SYN1']['change'] == .5
    assert corrected['interpretation']['SYN1']['change'] == pytest.approx(-1/6)
    assert corrected['shadow_forecasts']['SYN1'] < 0 < wrong['shadow_forecasts']['SYN1']
    assert corrected['interpretation']['SYN0']['status'] == 'missing_comparison'
    assert corrected['interpretation']['SYN0']['change'] is None
    assert corrected['shadow_forecasts']['SYN0'] == 0
    assert forward == before


def test_selection_intervention_preserves_forecast_values():
    forward, _ = learning.make_day(2, 1729)
    a = learning.forecast(forward, {'comparison': 'prior_guidance', 'ranking': 'headline', 'scale': .08})
    b = learning.forecast(forward, {'comparison': 'prior_guidance', 'ranking': 'signal', 'scale': .08})
    assert a['shadow_forecasts'] == b['shadow_forecasts']
    assert a['selected'] != b['selected']


def test_completed_example_retains_trials_files_and_refuses_overwrite(tmp_path):
    target = tmp_path / 'example'
    result = learning.run(target)
    assert result['trial_count'] == 12
    ledger = [json.loads(line) for line in (target / 'trials.jsonl').read_text().splitlines()]
    assert len(ledger) == 24
    assert sum(row['status'] == 'reserved' for row in ledger) == 12
    assert result['decision']['assessment_used'] is False
    assert result['decision']['selected'] == {'comparison': 'prior_guidance', 'ranking': 'signal', 'scale': .08}
    assert result['single_edit_search_control']['selected']['scale'] == 0
    assert result['single_edit_search_control']['selected']['comparison'] == 'year_ago'
    assert result['single_edit_search_control']['training_loss'] > min(row['loss'] for row in result['training_trials'])
    assert result['assessment']['selected']['universe_loss'] < result['assessment']['baseline']['universe_loss']
    assert result['assessment']['selected']['gain_over_fallback'] > 0
    assert result['model_calls'] == 0 and result['live_mutation_permission'] is False
    for name, sha in result['files'].items():
        assert text_digest((target / name).read_text()) == sha
    with pytest.raises(FileExistsError):
        learning.run(target)


def test_future_labels_cannot_change_training_selection_or_validation(tmp_path, monkeypatch):
    original = learning.run(tmp_path / 'first')
    make_day = learning.make_day

    def poisoned(index, seed, *, signal=True):
        forward, truth = make_day(index, seed, signal=signal)
        if index >= learning.SPLITS['assessment'][0]:
            truth = {key: 1000 for key in truth}
        return forward, truth

    monkeypatch.setattr(learning, 'make_day', poisoned)
    changed = learning.run(tmp_path / 'changed')
    assert original['training_trials'] == changed['training_trials']
    assert original['decision'] == changed['decision']
    assert original['assessment'] != changed['assessment']


def test_noise_control_can_choose_zero_instead_of_inventing_signal(tmp_path):
    result = learning.run(tmp_path / 'noise', signal=False)
    assert result['decision']['selected']['scale'] == 0
    assert result['assessment']['selected']['gain_over_fallback'] == 0


def test_failed_trial_remains_reserved_and_recorded(tmp_path, monkeypatch):
    evaluate = learning.evaluate

    def one_failure(forwards, labels, policy):
        if len(forwards) == 64 and policy == learning.candidates()[0]:
            raise ValueError('injected operator failure')
        return evaluate(forwards, labels, policy)

    monkeypatch.setattr(learning, 'evaluate', one_failure)
    result = learning.run(tmp_path / 'failure')
    assert result['training_trials'][0]['status'] == 'failed'
    assert result['trial_count'] == 12


def test_cli_runs_the_example_and_scores_a_panel(tmp_path, capsys):
    assert main(['synthetic-learning', '--output', str(tmp_path / 'cli')]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output['model_calls'] == 0
    cases = tmp_path / 'cases.json'
    cases.write_text(json.dumps([{'issue_id': 'synthetic', 'universe': ['s'], 'selected': [],
                                 'forecasts': {}, 'fallback': {'s': 0}, 'truth': {'s': .1}, 'budget': 0}]))
    assert main(['selection-score', '--input', str(cases)]) == 0
    assert json.loads(capsys.readouterr().out)['metrics']['gain_over_fallback'] == 0
