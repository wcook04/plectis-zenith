import pytest
from jsonschema import ValidationError
from research.decision_audit import cases,grade


def test_counterexamples_and_complete_scoring():
    q,key=cases();result=grade(q,key,key)
    assert result['correct']==result['total']==16
    for kind in ('matched_error','capability','supported_defect'):
        assert {key[x['id']] for x in q if x['kind']==kind}=={'yes','no'}
    wrong={k:'no' for k in key}
    assert grade(q,key,wrong)['correct']==6
    with pytest.raises(ValidationError):grade(q,key,{})


def test_question_order_changes_and_answer_key_stays_separate():
    q,a=cases(1);q2,a2=cases(2)
    assert q!=q2 and a!=a2
    assert all('expected' not in x and 'answer' not in x for x in q)


def test_whitespace_is_not_a_reasoning_error_and_array_is_still_invalid():
    q,a=cases();spaced={k:v.replace(',',', ') for k,v in a.items()}
    assert grade(q,a,spaced)['correct']==16
    with pytest.raises(ValidationError):grade(q,a,[spaced])
