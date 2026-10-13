"""Small scored interpretation task before open-ended forecast research.

This is a component calibration, not autonomous learning or a forecasting test.
The model sees questions, never the deterministic answer key. Both positive
and negative cases are generated before a single explicitly budgeted call.
"""
import argparse
import json
import random
from pathlib import Path
from jsonschema import validate
from zenith.providers import digest, write_json
from zenith.budgeted import OpenRouterBudgetedProvider
from zenith.provider_policy import latest_model
from system.lib.openrouter_free_runtime import load_env_file

INSTRUCTION = """Audit the supplied evidence. Return one answer per case, using only the supplied definitions and facts. Rank candidates from lowest to highest supplied mature validation MSE, breaking ties alphabetically by candidate ID. A forecast error can be measured only between a forecast and a later observation for the same entity and target interval, available at evaluation. A feature lookback or lag does not change the declared forecast horizon. A selection-only repair cannot create an option outside the supplied action set. An advisory default is not a mandatory policy. Flag an observed rule violation only when a stated mandatory rule was actually broken; a realised loss or a possible future mistake does not establish one. Do not suggest repairs or predict the market."""


def cases(seed=20261013, count=16):
    rng=random.Random(seed);questions=[];key={}
    for i in range(count):
        cid=f"case-{i+1:02d}";kind=i%4
        if kind==0:
            values=rng.sample(range(1,40),3);order=['alpha','beta','gamma'];rng.shuffle(order)
            options=[{'candidate_id':name,'validation_mse':value/100000} for name,value in zip(order,values)]
            question={'id':cid,'kind':'rank','candidates':options,'instruction':'Return candidate IDs in ascending mature validation MSE order.'}
            answer=','.join(x['candidate_id'] for x in sorted(options,key=lambda x:(x['validation_mse'],x['candidate_id'])))
        elif kind==1:
            matched=(i//4)%2==0
            question={'id':cid,'kind':'matched_error','forecast':{'entity':'system-A','target_interval':[10,15],'value':.02},
                'observed':{'entity':'system-A','interval':[10,15] if matched else [5,10],'value':.03,'available_at':16 if matched else 10},
                'evaluation_at':16,'feature_lag':20,'forecast_horizon':5,
                'instruction':'Is their difference a measured forecast error? Return yes or no. The feature lag is not the target horizon.'}
            answer='yes' if matched else 'no'
        elif kind==2:
            reachable=(i//4)%2==1
            question={'id':cid,'kind':'capability','available_predictions':[.01,.02,-.01 if reachable else .03],
                'allowed_edit':'Select one available prediction; may not alter numerical tools or add options.',
                'instruction':'Can this selection-only edit produce a negative forecast? Return yes or no.'}
            answer='yes' if reachable else 'no'
        else:
            mandatory=(i//4)%2==0
            question={'id':cid,'kind':'supported_defect','rule':('MUST choose the lowest validation MSE' if mandatory else 'Lowest validation MSE is an ADVISORY default; alternatives are permitted'),
                'validation_mse':{'alpha':.001,'beta':.002},'actual_selection':'beta','realised_loss':.003,
                'instruction':'Does this record establish a violation of the stated selection rule? Return yes or no. Do not infer a rule violation from realised loss.'}
            answer='yes' if mandatory else 'no'
        questions.append(question);key[cid]=answer
    rng.shuffle(questions)
    return questions,key


def response_schema(questions):
    return {'type':'object','properties':{q['id']:{'type':'string','minLength':1,'maxLength':80} for q in questions},
        'required':[q['id'] for q in questions],'additionalProperties':False}


def grade(questions,key,response):
    validate(response,response_schema(questions))
    rows=[{'id':q['id'],'kind':q['kind'],'expected':key[q['id']],'actual':response[q['id']],
        'exact_serialization_match':response[q['id']]==key[q['id']],
        'correct':([p.strip() for p in response[q['id']].split(',')]==key[q['id']].split(',') if q['kind']=='rank'
                   else response[q['id']].strip()==key[q['id']])} for q in questions]
    return {'correct':sum(r['correct'] for r in rows),'total':len(rows),'rows':rows,
        'scorer':'semantic_tokens_v2; comma whitespace is not a reasoning error; exact serialization match also retained',
        'interpretation':'A diagnostic of these supplied facts and controlled counterexamples only. No forecast accuracy, useful learned repair, general reasoning competence or transfer is established.'}


def audit_saved(output):
    """Inspect a saved response; never accept malformed output into the graph."""
    output=Path(output)
    ledger=json.loads((output/'budget/budget.json').read_text())
    entries=list(ledger['entries'].values())
    if len(entries)!=1:raise ValueError('component audit requires exactly one retained provider attempt')
    response=json.loads(entries[0]['provider_receipt']['response_text'])
    questions=json.loads((output/'questions.json').read_text());key=json.loads((output/'answer-key.json').read_text())
    recovered=isinstance(response,list) and len(response)==1 and isinstance(response[0],dict)
    candidate=response[0] if recovered else response
    result={'format_valid':not recovered,'diagnostic_array_unwrap_only':recovered,'imported_or_adopted':False,
        'reported_cost_usd':entries[0]['cost'],'score':grade(questions,key,candidate)}
    write_json(output/'semantic-audit.json',result)
    return result


def run(output,env_file,model=None,provider_slug=None,seed=20261013):
    output=Path(output).resolve()
    if output.exists():raise ValueError('Existing experiment is immutable; no automatic retry or resampling')
    model=model or latest_model();questions,key=cases(seed)
    output.mkdir(parents=True)
    protocol={'schema':'zenith_decision_audit_v1','model':model,'provider_slug':provider_slug,
        'seed':seed,'questions_sha256':digest(questions),'answer_key_sha256':digest(key),
        'instruction':INSTRUCTION,'scope':'predeclared generated component calibration; not historical financial outcomes',
        'max_cost_usd':'0.01','max_calls':1,'max_output_tokens':1024,
        'baseline':'Deterministic reference solves the explicitly typed task; this test does not demonstrate that an LLM is needed.'}
    write_json(output/'protocol.json',protocol);write_json(output/'questions.json',questions);write_json(output/'answer-key.json',key)
    load_env_file(Path(env_file))
    provider=OpenRouterBudgetedProvider(output,model,'.01',1,1024,output/'budget',provider_slug=provider_slug)
    try:
        raw=provider.ask_ai(json.dumps(questions,ensure_ascii=False),{'meta':{'session_id':output.name,'node_id':'decision_audit'},
            'system_prompt':INSTRUCTION,'response_format':{'type':'json_schema','json_schema':{'name':'decision_audit','strict':True,'schema':response_schema(questions)}}})
        result=grade(questions,key,json.loads(raw));write_json(output/'result.json',result)
        return result
    except Exception as exc:
        write_json(output/'failure.json',{'status':'terminal','error':str(exc)});raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--env-file',type=Path,required=True)
    p.add_argument('--model');p.add_argument('--provider-slug');p.add_argument('--seed',type=int,default=20261013)
    a=p.parse_args();print(json.dumps(run(a.output,a.env_file,a.model,a.provider_slug,a.seed),indent=2))


if __name__=='__main__':main()
