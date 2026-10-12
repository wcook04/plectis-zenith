"""Explicit Decide composition: authored economic state, fitted numerical output.

Never fetches outcomes, fits weights, or alters the raw provider response.
The inherited JUDGMENTAL interface names the quantile contract; the derivation
records that its numbers were produced by a fitted operator, not the LLM.
"""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

from system.lib import learned_head as head
from zenith.providers import digest

SOURCE_EDGES = {'global_stock_feed', 'global_news_feed'}


def source_data(run_dir, issue_at):
    sources = {name: json.loads((Path(run_dir)/'artifacts'/f'{name}.json').read_text()) for name in SOURCE_EDGES}
    issue = datetime.fromisoformat(issue_at)
    for env in sources.values():
        at = datetime.fromisoformat(env['metadata']['as_of'])
        if at != issue:
            raise ValueError('Learned head requires the original issue snapshot')
    stock = sources['global_stock_feed']['data']
    news = sources['global_news_feed']['data']
    return {'issue_date': issue.date().isoformat(), 'issue_at': issue_at,
            'symbols': sorted(r[0] for r in stock['rows']), 'stock': stock,
            'news': [{k:r[k] for k in ('ledger_id','text','entities','available_at','source_ref')}
                     for r in news.get('items',[])]}


def quantiles(model, data, state, evidence):
    numeric = head.predict(model, data, state)
    by_id = {e['ledger_id']:e for e in evidence}
    states = {r[0]:r for r in state}
    rows = []
    for row in numeric:
        symbol = row['target_id']
        stocks = [e for e in evidence if e.get('subject') == symbol and str(e.get('ledger_id','')).startswith('S_')]
        if len(stocks) != 1:
            raise ValueError('One original stock grounding per fitted target required')
        refs = [stocks[0]['ref_id'], *[by_id[n]['ref_id'] for n in states[symbol][4]]]
        rows.append({**row,'evidence_refs':refs,
                     'reasoning':'Frozen outcome-trained quantile operator; economic state authored from supplied evidence. '
                                 'No causal identification or validated calibration is claimed. '+' '.join(refs)})
    return {'method':'evidence_conditioned_quantiles_v1','calendar':'XSHG','units':'simple_return_fraction',
            'calibration_status':'UNVALIDATED','targets':rows}


def materialize(payload, model, run_dir, issue_at):
    if not isinstance(payload,dict) or payload.get('forecast_basis') != 'JUDGMENTAL':
        raise ValueError('Learned Decide requires the explicit quantile forecast branch')
    if 'forecast_quantiles' in payload or 'learned_head_derivation' in payload:
        raise ValueError('Learned Decide must not submit numerical forecasts or a derived receipt')
    data = source_data(run_dir,issue_at)
    state = head.parse_state(payload['economic_state'], data)
    result = deepcopy(payload)
    # Preserve authored references; add missing original identities deterministically.
    evidence = result['evidence_dictionary']
    ids = {e['ledger_id'] for e in evidence}
    original = list(data['stock']['evidence_dictionary'])
    news_env = json.loads((Path(run_dir)/'artifacts/global_news_feed.json').read_text())
    cited = {n for row in state for n in row[4]}
    original += [e for e in news_env['data'].get('evidence_dictionary',[]) if e['ledger_id'] in cited]
    next_ref = max([int(e['ref_id'][1:-1]) for e in evidence]+[0])+1
    for row in original:
        if row['ledger_id'] not in ids:
            evidence.append({**row,'ref_id':f'[{next_ref}]'})
            next_ref += 1; ids.add(row['ledger_id'])
    result['forecast_quantiles'] = quantiles(model,data,state,evidence)
    result['learned_head_derivation'] = {'method':'frozen_fitted_quantile_head_v1','model':deepcopy(model),
        'model_sha256':model['model_sha256'],'encoder_sha256':model['encoder_sha256'],
        'input_sha256':digest(data),'economic_state_sha256':digest(state),
        'numerical_origin':'deterministic_fitted_operator',
        'representation_origin':'native_decide_richer_context_than_component_encoder'}
    return result


def rule_errors(payload):
    if not {'economic_state','learned_head_derivation'} & payload.keys():
        return []
    try:
        if payload.get('forecast_basis') != 'JUDGMENTAL':
            raise ValueError('Learned derivation requires quantile branch')
        d = payload['learned_head_derivation']
        expected = {'method','model','model_sha256','encoder_sha256','input_sha256','economic_state_sha256',
                    'numerical_origin','representation_origin'}
        if set(d) != expected or d['method'] != 'frozen_fitted_quantile_head_v1':
            raise ValueError('Exact learned derivation fields required')
        head.check_model(d['model'])
        if (d['model_sha256'] != d['model']['model_sha256'] or d['encoder_sha256'] != d['model']['encoder_sha256']
                or d['economic_state_sha256'] != digest(payload['economic_state'])
                or d['numerical_origin'] != 'deterministic_fitted_operator'
                or d['representation_origin'] != 'native_decide_richer_context_than_component_encoder'):
            raise ValueError('Learned derivation binding differs')
        return []
    except (ValueError,KeyError,TypeError,IndexError,AttributeError,OverflowError) as exc:
        return ['INVALID_LEARNED_HEAD: '+str(exc)]


def replay_errors(payload, run_dir, issue_at):
    if 'learned_head_derivation' not in payload:
        return []
    try:
        errors = rule_errors(payload)
        if errors:
            return errors
        d = payload['learned_head_derivation']
        spec = json.loads((Path(run_dir)/'zenith_run.json').read_text())
        if spec.get('reasoning_policy',{}).get('nodes',{}).get('lab_decide',{}).get('learned_head') != d['model']:
            raise ValueError('Fitted model differs from the original run policy')
        data = source_data(run_dir,issue_at)
        if digest(data) != d['input_sha256']:
            raise ValueError('Learned forward input binding differs')
        expected = quantiles(d['model'],data,payload['economic_state'],payload['evidence_dictionary'])
        if expected != payload['forecast_quantiles']:
            raise ValueError('Forecast differs from independently replayed learned head')
        return []
    except (ValueError,KeyError,TypeError,IndexError,AttributeError,OverflowError,OSError) as exc:
        return ['INVALID_LEARNED_HEAD: '+str(exc)]
