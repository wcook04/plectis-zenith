"""An exact acquired native test, its provenance and scoped later failures."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile

from research.native_conformance_tasks import measure
from scripts.build_observation_report import digest

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def test_acquired_regression_binds_original_policy_observation_and_costs():
    data = read(ROOT / 'examples/conformance/learned-regressions.json')
    assert data['schema'] == 'zenith_learned_regressions_v1'
    assert len(data['regressions']) == 1
    item = data['regressions'][0]; provenance = item['acquired_from']
    bundle = ROOT / provenance['bundle']; frozen = read(bundle / 'frozen.json')
    record = next(r for r in frozen['records'] if r['task_id'] == 'native-utf8-1')
    policy = record['arms']['ordinary']['policy']
    receipt = record['arms']['ordinary']['investigation']['receipts'][0]
    assert provenance['frozen_sha256'] == digest(frozen)
    assert provenance['source_archive_sha256'] == read(bundle / 'protocol.json')['source']['sha256']
    assert provenance['policy_call_id'] == policy['call_id']
    assert provenance['policy_source_sha256'] == hashlib.sha256(policy['source'].encode()).hexdigest()
    assert provenance['policy_raw_sha256'] == policy['raw_sha256']
    assert provenance['policy_prompt_sha256'] == policy['prompt_sha256']
    assert provenance['query_receipt'] == receipt
    assert provenance['query_receipt_sha256'] == digest(receipt)
    assert item['query'] == receipt['query'] and item['expected'] == receipt['expected']
    assert receipt['verified_counterexample'] and receipt['parent_error'] is None
    assert item['untrusted_hypothesis']['original_note'] == receipt['note']
    billing = {e['node_id']:e for e in read(bundle / 'billing.json')['entries']}
    assert provenance['provider_call_id'] == billing[policy['call_id']]['call_id']
    assert item['acquisition_cost']['policy_cost_usd'] == billing[policy['call_id']]['cost']
    assert item['acquisition_cost']['shared_parent_cost_usd'] == billing[record['parent']['call_id']]['cost']


def test_native_prefix_result_and_mismatches_replay_with_frozen_original_code():
    data = read(ROOT / 'examples/conformance/learned-regressions.json')
    item = data['regressions'][0]; bundle = ROOT / item['acquired_from']['bundle']
    assert measure('utf8', item['query']) == item['expected'] == {'count':0,'status':'error'}
    # A fresh interpreter loads the archived executor and exact original target
    # source; the live checkout cannot silently repair their known failures.
    body = '''
import hashlib,json,socket,sys
from pathlib import Path
def denied(*args,**kwargs):raise RuntimeError('No network in regression replay')
socket.socket.connect=denied
socket.socket.connect_ex=denied
socket.create_connection=denied
sys.path.insert(0,sys.argv[1])
from research import conformance_study as s
bundle=Path(sys.argv[2]);_,data=s.verify(bundle)
item=s.read(Path(sys.argv[3]))['regressions'][0]
frozen=s.read(bundle/'frozen.json');records={r['task_id']:r for r in frozen['records']}
tasks={t['id']:t for t in data['tasks']}
results=[]
for target in item['posthoc_targets']:
 record=records[target['task_id']]
 original=record['parent'] if target['version']=='parent' else record['arms']['fixed']['selected']
 assert original['call_id']==target['call_id']
 assert hashlib.sha256(original['source'].encode()).hexdigest()==target['source_sha256']
 result=s.invoke(original['source'],item['query'])
 results.append(result)
 assert s.measure(record['source_id'],item['query'])==item['expected']
 for saved,query in zip(target['full_fixed_pack'],tasks[target['task_id']]['fixed_queries'],strict=True):
  assert saved['query']==query
  assert saved['expected']==s.measure(record['source_id'],query)
  got=s.invoke(original['source'],query)
  assert (got['error'] is not None)==(saved['error'] is not None)
  assert got['answer']==saved['actual']
print(json.dumps(results))
'''
    with tempfile.TemporaryDirectory(prefix='zenith-regression-replay-') as directory:
        runtime = Path(directory) / 'runtime'; runtime.mkdir()
        with ZipFile(bundle / 'runtime-source.zip') as archive:
            archive.extractall(runtime)
        result = subprocess.run([sys.executable, '-I', '-B', '-c', body, str(runtime), str(bundle),
                                 str(ROOT / 'examples/conformance/learned-regressions.json')],
                                cwd=runtime, env={}, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        results = json.loads(result.stdout)
    assert len(results) == len(item['posthoc_targets']) == 4
    for result, target in zip(results, item['posthoc_targets'], strict=True):
        assert result['error'] is None
        assert result['answer'] == target['observation']['parent_answer'] == {'count':0,'status':'open'}
        assert result['answer'] != item['expected']
        assert len(target['full_fixed_pack']) == 8
        assert target['query_absent_from_full_fixed_pack']
        assert all(row['query'] != item['query'] for row in target['full_fixed_pack'])
    later = [t for t in item['posthoc_targets'] if t['task_id']=='native-utf8-1']
    assert all(t['fixed_semantic_failures']==0 and t['fixed_technical_failures']==4 for t in later)
