"""Independent accounting and cutoff checks, not forecast-performance tests."""
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction

import pytest

from benchmarks import traderharness as data


def action(ex='2025-07-29', record='2025-07-28', cash=39.74, bonus=8., transfer=12.):
    return {'stock_code': '002594', 'ann_date': '2025-07-22', 'record_date': record,
            'ex_date': ex, 'bonus_shares': bonus, 'transfer_shares': transfer,
            'cash_dividend': cash, 'progress': '实施'}


@pytest.mark.parametrize('entry,exit_date,opening,closing,expected', [
    ('2025-07-28', '2025-08-01', 337.93, 105.8, (3 * Fraction('105.8') + Fraction('3.974')) / Fraction('337.93') - 1),
    ('2025-07-29', '2025-08-04', 112.01, 104.88, Fraction('104.88') / Fraction('112.01') - 1),
    ('2025-07-23', '2025-07-29', 342.09, 111.42, (3 * Fraction('111.42') + Fraction('3.974')) / Fraction('342.09') - 1),
])
def test_real_byd_entitlement_examples_with_independent_fraction_oracle(entry, exit_date, opening, closing, expected):
    lookup = {entry: {'open': opening}, exit_date: {'close': closing}}
    actual, receipt = data.wealth_return(entry, exit_date, lookup, [action()])
    assert actual == pytest.approx(float(expected), abs=1e-14)
    assert bool(receipt['actions']) == (entry != '2025-07-29')


def test_two_distributions_cash_uses_pre_event_quantity_and_is_not_reinvested():
    actions = [action(ex='2025-07-23', record='2025-07-22', cash=10, bonus=10, transfer=0),
               action(ex='2025-07-29', record='2025-07-28', cash=20, bonus=0, transfer=10)]
    actual, receipt = data.wealth_return('2025-07-22', '2025-07-30',
                                        {'2025-07-22': {'open': 100}, '2025-07-30': {'close': 25}}, actions)
    assert actual == pytest.approx(.05)
    assert receipt['terminal_shares'] == '4'
    assert receipt['cash_receivable'] == '5'


def test_duplicate_or_ambiguous_actions_are_not_silently_credited():
    with pytest.raises(ValueError, match='duplicate'):
        data.normalize_actions([action(), action()], ['002594'])
    with pytest.raises(ValueError, match='clocks'):
        data.normalize_actions([{**action(), 'ann_date': '2026-01-01'}], ['002594'])


def test_history_wealth_marks_do_not_show_a_distribution_crash_or_future_adjustment():
    lookup = {d: {'open': p, 'high': p, 'low': p, 'close': p, 'volume': v}
              for d, p, v in [('2025-07-28', 303., 100.), ('2025-07-29', 100., 300.), ('2025-07-30', 101., 300.)]}
    dates = sorted(lookup)
    past_action = action(cash=30.)
    hist, preceding = data.history_view(dates, lookup, [past_action])
    assert preceding == 1
    assert hist[0]['Close'] == 1
    assert hist[1]['Close'] == pytest.approx(306 / 303)
    assert hist[0]['Volume'] == 1
    future = action(ex='2025-08-20', record='2025-08-19', cash=1000.)
    assert data.history_view(dates, lookup, [past_action, future]) == (hist, preceding)


def test_news_epoch_and_day_only_announcement_use_explicit_clocks():
    class Calendar:
        def session_open(self, date):
            import pandas as pd
            return pd.Timestamp(date + 'T01:30:00Z')
    tables = {'news_cls': [{'id': 1, 'ctime': 1735876800, 'display_time': datetime(2025, 1, 3, 12),
                           'title': '{{C002594}} profit report', 'content_source': 'derived_headline'}],
              'announcements': [{'stock_code': '002594', 'title': 'report',
                                 'announcement_time': datetime(2025, 1, 3), 'pdf_url': 'x'}]}
    records, audit = data.text_index(tables, ['2025-01-03', '2025-01-06'], Calendar(), ['002594'])
    news = next(r for r in records if r['kind'] == 'news')
    notice = next(r for r in records if r['kind'] == 'filing')
    assert news['available_at'] == datetime.fromtimestamp(1735876800, timezone.utc).isoformat()
    assert notice['available_at'] == '2025-01-06T01:30:00+00:00'
    selected, _ = data.select_text(records, '2025-01-03T07:01:00+00:00', '002594')
    assert notice not in selected


def test_post_cutoff_text_and_duplicate_headline_do_not_change_forward_selection():
    row = {'id': 'one', 'kind': 'news', 'available_at': '2025-01-02T00:00:00+00:00',
           'content': 'same fact', 'entities': ['002594']}
    baseline = data.select_text([row], '2025-01-03T00:00:00+00:00', '002594')[0]
    future = {**row, 'id': 'future', 'available_at': '2025-01-04T00:00:00+00:00', 'content': 'future secret'}
    assert data.select_text([row, future], '2025-01-03T00:00:00+00:00', '002594')[0] == baseline
    selected, _ = data.select_text([row, {**row, 'id': 'two'}], '2025-01-03T00:00:00+00:00', '002594')
    assert len(selected) == 1


def test_missing_or_zero_volume_bar_is_not_bridged():
    assert not data.valid_bar(None)
    assert not data.valid_bar({'open': 10, 'high': 11, 'low': 9, 'close': 10, 'volume': 0})


def test_teacher_window_retains_holiday_reporting_older_than_seven_calendar_days():
    row = {'id': 'holiday', 'kind': 'news', 'available_at': '2023-04-28T08:00:00+00:00',
           'content': 'Quarterly earnings changed.', 'entities': ['002594']}
    assert data.select_text([row], '2023-05-09T07:01:00+00:00', '002594')[0] == []
    selected, _ = data.select_text([row], '2023-05-09T07:01:00+00:00', '002594', after='2023-04-27T07:01:00+00:00')
    assert selected[0]['id'] == 'holiday'
