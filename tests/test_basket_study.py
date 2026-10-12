"""Outcome access and policy retention are experiment contracts."""
from unittest.mock import Mock
import pytest
from research.basket_study import score_case, report
from zenith.providers import digest, write_json


def test_every_arm_commits_before_outcome_access(tmp_path):
    case={'cutoff':'2024-01-01','split':'holdout','arms':['directed','serial'], 'baseline':{'B01':0.,'B02':0.}}
    panel=Mock()
    panel.outcome.return_value={'returns':{'B01':.1,'B02':-.1}}
    def save(arm,values):
        record={'forecasts':values};record['sha256']=digest(record)
        write_json(tmp_path/'commitments'/case['cutoff']/(arm+'.json'),record)
    save('directed',{'B01':.05,'B02':-.05})
    with pytest.raises(FileNotFoundError):score_case(tmp_path,{},case,panel)
    panel.outcome.assert_not_called()
    save('serial',{'B01':.1,'B02':-.1})
    answer=score_case(tmp_path,{},case,panel)
    assert answer['mse']['directed']==pytest.approx(.0025)
    assert answer['mse']['serial']==0
    assert answer['mse']['numerical']==pytest.approx(.01)
    write_json(tmp_path/'commitments'/case['cutoff']/'serial.json', {'sha256':'changed','forecasts':{'B01':9}})
    panel.reset_mock()
    with pytest.raises(ValueError,match='commitment changed'):score_case(tmp_path,{},case,panel)
    panel.outcome.assert_not_called()


def test_worst_origin_and_failed_arm_block_retention(tmp_path):
    write_json(tmp_path/'protocol.json',{'cases':[{},{}], 'basket_manifest':{'groups':{'B01':['A']},'source_commit':'fixture'},
        'sha256':'fixture','limit':'test only','model':'fake','data_qualifications':[]})
    for i,(old,new) in enumerate(((3.,.1),(4.,4.1))):
        write_json(tmp_path/'scores'/f'{i}.json', {'split':'holdout','mse':{'directed':old,'revised':new}})
    write_json(tmp_path/'commitments'/'0'/'directed.json',{'run_id':'fixture-directed','arm':'directed','status':'completed','cp2':{'query_count':0}})
    assert report(tmp_path)['revision_retained'] is False
    write_json(tmp_path/'scores'/'1.json',{'split':'holdout','mse':{'directed':4.,'revised':3.9}})
    assert report(tmp_path)['revision_retained'] is True
    write_json(tmp_path/'commitments'/'0'/'directed.json',{'run_id':'fixture-directed','arm':'directed','status':'failed','cp2':None})
    assert report(tmp_path)['revision_retained'] is False
