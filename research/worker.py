"""Execute a captured candidate, then score its probabilities with native replay."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

from research.engine import binding, canonical, cards_in, digest_bytes, read_json, verify, write_json
from tools.finance import historical_replay


def evaluate(study: Path, spec, artifacts, directory: Path):
    paths = []
    for index, artifact in enumerate(artifacts):
        path = directory / f'calculator-{index}.json'
        write_json(path, artifact)
        paths.append(str(path))
    envelope = historical_replay.run({'calculator_artifacts': paths,
        'price_history': str(study / spec['price_history']),
        'horizons': f"{spec['horizon_days']}d", 'benchmark': spec['benchmark'],
        'truth_as_of': spec['truth_as_of'], 'date_match_policy': 'exact',
        'split_policy': 'prequential', 'max_cards': sum(len(cards_in(a)) for a in artifacts),
        'minimum_coverage': 1.0,
        'experiment_id': 'frozen-evaluation',
        'runtime': {'run_id': 'frozen-evaluation', 'as_of': spec['truth_as_of']}}, run_dir=directory)
    write_json(directory / 'envelope.json', envelope)
    if envelope['metadata']['status'] != 'success':
        raise ValueError(envelope['metadata'].get('error', 'native evaluator failed'))
    data = envelope['data']
    counts = data['experiment_ledger']['claim_counts']
    expected = sum(len(cards_in(a)) for a in artifacts)
    if counts['candidate'] != expected or counts['admitted'] != expected or counts['resolved'] != expected:
        raise ValueError(f'native evaluator must resolve every frozen event: {counts}')
    score = data['experiment_ledger']['scores']['mean_brier']
    if type(score) not in (int, float) or not math.isfinite(score):
        raise ValueError('native evaluator returned no finite Brier score')
    keys = sorted(c['comparison_event_key'] for c in data['scorecards'])
    if len(set(keys)) != expected:
        raise ValueError('comparison event keys must be unique')
    return score, keys, counts


def run(study: Path, attempt: Path, phase: str):
    spec, _ = binding(study)
    verify(study, spec)
    started = read_json(attempt / 'started.json')
    if digest_bytes((attempt / 'candidate.py').read_bytes()) != started['provenance']['candidate_hash']:
        raise ValueError('captured candidate hash mismatch')
    selected = {row['forecast_id'] for row in spec['membership']
                if row['split'] == ('development' if phase == 'development' else 'holdout')}
    artifacts = []
    projection = []
    for ref in spec['calculator_artifacts']:
        artifact = read_json(study / ref)
        chosen = [card for card in cards_in(artifact) if card['identity']['forecast_id'] in selected]
        if not chosen:
            continue
        # Use a strict projection. Extra upstream fields (provider prose,
        # subsequent price labels, full source paths) never enter candidate stdin.
        artifact = {'metadata': {'tool': 'calculator', 'data_schema_version': 'calculator.6'},
                    'data': {'candidate_forecast_cards': chosen}}
        artifacts.append(artifact)
        for card in chosen:
            p = card.get('belief', {}).get('directional_hit_probability', card.get('belief', {}).get('event_probability', .5))
            if type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1:
                raise ValueError('frozen baseline probabilities must be finite and in [0,1]')
            projection.append({'forecast_id': card['identity']['forecast_id'],
                'subject_as_of': card['identity']['as_of'], 'direction': card['target']['direction'], 'probability': p})
    write_json(attempt / 'candidate-input.json', projection)
    # Only the small captured source file enters the process directory. This is
    # an interface boundary for trusted code, not an OS security sandbox.
    with tempfile.TemporaryDirectory(prefix='zenith-candidate-') as temp:
        script = Path(temp) / 'candidate.py'
        script.write_bytes((attempt / 'candidate.py').read_bytes())
        with (attempt / 'candidate.stdout').open('wb') as out, (attempt / 'candidate.stderr').open('wb') as err:
            process = subprocess.run([sys.executable, '-I', str(script)], input=canonical(projection),
                stdout=out, stderr=err, cwd=temp, env={'PATH': '/usr/bin:/bin'},
                timeout=spec['timeout_seconds'])
        if process.returncode:
            raise ValueError(f'candidate exited with code {process.returncode}')
    output = attempt / 'candidate.stdout'
    if output.stat().st_size > 1024 * 1024:
        raise ValueError('candidate output exceeds one MiB')
    probabilities = json.loads(output.read_bytes())
    if not isinstance(probabilities, list) or len(probabilities) != len(projection):
        raise ValueError('candidate must emit one probability per frozen event')
    if any(type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities):
        raise ValueError('candidate probabilities must be finite numbers in [0,1]')
    changed = copy.deepcopy(artifacts)
    index = 0
    for artifact in changed:
        for card in cards_in(artifact):
            card['belief']['event_probability'] = probabilities[index]
            card['belief']['directional_hit_probability'] = probabilities[index]
            index += 1
    verify(study, spec)
    baseline_score, baseline_keys, _ = evaluate(study, spec, artifacts, attempt / 'baseline')
    score, keys, counts = evaluate(study, spec, changed, attempt / 'candidate')
    if keys != baseline_keys or counts['resolved'] < spec['minimum_resolved']:
        raise ValueError('candidate changed frozen event support')
    result = {'metric': 'mean_brier', 'score': score, 'baseline_score': baseline_score,
        'event_keys': keys, 'counts': counts, 'identity_mapping': probabilities == [r['probability'] for r in projection],
        'week_clusters': sorted({r['week'] for r in spec['membership'] if r['forecast_id'] in selected}),
        'native_receipt': 'candidate/envelope.json', 'live_mutation_permission': False,
        'interpretation': 'historical probability error; no investment-performance claim'}
    write_json(attempt / 'evaluation.json', result)


if __name__ == '__main__':
    try:
        run(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        raise SystemExit(1)
