"""Frozen experiments, durable attempts, and explicit keep/discard decisions.

Candidate code is trusted local code, not sandboxed. The interface supplies only
frozen prediction-time fields. The scientific boundary is enforced on artifacts,
contracts, temporal membership, scoring, and the final-evaluation budget.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'zenith_research_spec_v1'


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def read_json(path: Path):
    return json.loads(path.read_text())


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temp.write_bytes(canonical(value) + b'\n')
    temp.replace(path)


def event_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('event time requires an explicit timezone')
    return parsed.astimezone(timezone.utc)


def evaluator_hashes():
    # Pin the extracted evaluator and its local authorities, including admission,
    # event keys, truth resolver, and envelope implementation.
    paths = sorted((ROOT / 'tools/finance').glob('*.py'))
    paths += sorted((ROOT / 'system/lib').glob('*.py'))
    paths += sorted((ROOT / 'research').glob('*.py'))
    if not (ROOT / 'tools/finance/historical_replay.py').exists():
        raise ValueError('extracted Zenith replay evaluator is unavailable')
    return {str(p.relative_to(ROOT)): digest_bytes(p.read_bytes()) for p in paths}


def cards_in(payload):
    data = payload.get('data', payload)
    cards = data.get('candidate_forecast_cards')
    if not isinstance(cards, list) or not cards:
        raise ValueError('calculator artifact needs nonempty candidate_forecast_cards')
    return cards


@contextmanager
def connect(study: Path):
    db = sqlite3.connect(study / 'trials.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def champion(db):
    return db.execute("SELECT * FROM trials WHERE id=(SELECT CAST(value AS INTEGER) FROM metadata WHERE key='champion_trial')").fetchone()


def row_receipt(row):
    return {'attempt': row['id'], 'phase': row['phase'], 'provenance': json.loads(row['provenance']),
            'state': row['state'], 'decision': row['decision'],
            'result': json.loads(row['result']) if row['result'] else None, 'error': row['error']}


def binding(study: Path):
    raw = (study / 'frozen.json').read_bytes()
    with connect(study) as db:
        pinned = db.execute("SELECT value FROM metadata WHERE key='spec_hash'").fetchone()
    if pinned is None or digest_bytes(raw) != pinned['value']:
        raise ValueError('frozen spec hash mismatch')
    return json.loads(raw), pinned['value']


def verify(study: Path, spec):
    if sys.version != spec['python_version']:
        raise ValueError('Python runtime version mismatch; create a new study')
    if evaluator_hashes() != spec['evaluator_hashes']:
        raise ValueError('evaluator source hash mismatch; create a new study')
    for ref in spec['artifacts']:
        path = study / ref['path']
        if digest_bytes(path.read_bytes()) != ref['sha256']:
            raise ValueError(f"frozen input hash mismatch: {ref['path']}")


def freeze(spec_path: Path, study: Path):
    raw = read_json(spec_path)
    required = {'schema', 'calculator_artifacts', 'price_history', 'truth_as_of',
                'holdout_start', 'horizon_days', 'embargo_days', 'max_trials',
                'timeout_seconds', 'minimum_improvement', 'minimum_resolved', 'benchmark'}
    if not required <= set(raw) or set(raw) - required - {'intervention'} or raw['schema'] != SCHEMA:
        raise ValueError('spec must contain documented v1 fields and optional intervention only')
    intervention = raw.get('intervention', {'parameter_kind': 'probability_mapping',
        'node_ids': [], 'incoming_edge_ids': [], 'source_artifacts': []})
    if not isinstance(intervention, dict) or set(intervention) != {'parameter_kind', 'node_ids', 'incoming_edge_ids', 'source_artifacts'}:
        raise ValueError('intervention requires parameter_kind, node_ids, incoming_edge_ids, source_artifacts')
    if intervention['parameter_kind'] not in {'node_skill', 'context_policy', 'topology', 'model', 'probability_mapping'}:
        raise ValueError('unsupported intervention parameter_kind')
    for name in ('node_ids', 'incoming_edge_ids', 'source_artifacts'):
        if not isinstance(intervention[name], list) or any(not isinstance(v, str) or not v for v in intervention[name]):
            raise ValueError(f'intervention {name} must be a list of nonempty strings')
    for name in ('horizon_days', 'max_trials', 'minimum_resolved'):
        if type(raw[name]) is not int or raw[name] < 1:
            raise ValueError(f'{name} must be a positive integer')
    if type(raw['embargo_days']) is not int or raw['embargo_days'] < 0:
        raise ValueError('embargo_days must be a nonnegative integer')
    for name in ('timeout_seconds', 'minimum_improvement'):
        if type(raw[name]) not in (int, float) or not math.isfinite(raw[name]) or raw[name] < 0:
            raise ValueError(f'{name} must be finite and nonnegative')
    if raw['timeout_seconds'] <= 0:
        raise ValueError('timeout_seconds must be positive')
    boundary = event_time(raw['holdout_start'])
    truth_as_of = event_time(raw['truth_as_of'])
    if truth_as_of <= boundary:
        raise ValueError('truth_as_of must follow holdout boundary')
    if study.exists():
        raise ValueError('study already exists; frozen studies cannot be overwritten')
    source_root = spec_path.resolve().parent
    frozen = dict(raw)
    frozen['intervention'] = copy.deepcopy(intervention)
    frozen['intervention']['source_artifacts'] = []
    frozen['python_version'] = sys.version
    frozen['evaluator_hashes'] = evaluator_hashes()
    frozen['artifacts'] = []
    frozen['membership'] = []
    frozen['calculator_artifacts'] = []
    seen = set()
    copied = []
    # Validate before any executable candidate is loaded or any study is created.
    for index, source in enumerate(raw['calculator_artifacts']):
        data = (source_root / source).read_bytes()
        payload = json.loads(data)
        for card in cards_in(payload):
            identity = card['identity']
            identifier = identity['forecast_id']
            if not isinstance(identifier, str) or not identifier or identifier in seen:
                raise ValueError('forecast ids must be nonempty and globally unique')
            seen.add(identifier)
            start = event_time(identity['as_of'])
            end = start + timedelta(days=raw['horizon_days'])
            if end > truth_as_of:
                raise ValueError('every event must mature before truth_as_of')
            available = event_time(identity.get('available_at', identity['as_of']))
            if available > start:
                raise ValueError('forecast artifact was not available at event time')
            # All predictions in a calendar week share one split. Purge the whole
            # development group if any event plus embargo overlaps the holdout.
            week = (start - timedelta(days=start.weekday())).date().isoformat()
            frozen['membership'].append({'forecast_id': identifier, 'subject_as_of': start.isoformat(),
                'event_end': end.isoformat(), 'available_at': available.isoformat(), 'week': week,
                'split': 'holdout' if start >= boundary else 'development'})
        ref = f'inputs/calculator-{index}.json'
        frozen['calculator_artifacts'].append(ref)
        copied.append((ref, data))
    weeks = {}
    for row in frozen['membership']:
        weeks.setdefault(row['week'], []).append(row)
    for group in weeks.values():
        splits = {r['split'] for r in group}
        if len(splits) > 1:
            raise ValueError('holdout boundary splits a clustered calendar week')
        if splits == {'development'} and any(event_time(r['event_end']) + timedelta(days=raw['embargo_days']) > boundary for r in group):
            for row in group:
                row['split'] = 'purged'
    for split in ('development', 'holdout'):
        if sum(r['split'] == split for r in frozen['membership']) < raw['minimum_resolved']:
            raise ValueError(f'{split} needs at least minimum_resolved events after purge')
    for index, source in enumerate(intervention['source_artifacts']):
        data = (source_root / source).read_bytes()
        ref = f'inputs/upstream-{index}.artifact'
        copied.append((ref, data))
        frozen['intervention']['source_artifacts'].append({'path': ref, 'sha256': digest_bytes(data)})
    truth_data = (source_root / raw['price_history']).read_bytes()
    json.loads(truth_data)
    frozen['price_history'] = 'inputs/prices.json'
    copied.append((frozen['price_history'], truth_data))
    frozen['artifacts'] = [{'path': ref, 'sha256': digest_bytes(data)} for ref, data in copied]
    frozen['objective'] = {'metric': 'mean_brier', 'direction': 'minimize',
        'support': 'all frozen events resolved; identical comparison_event_keys',
        'baseline': 'identity_probability_mapping', 'promotion': 'proposal_only',
        'final_evaluations': 1,
        'execution_scope': 'probability_mapping_over_frozen_upstream_forecasts',
        'availability': 'declared available_at, defaulting to subject time; not externally certified'}
    study.mkdir(parents=True)
    for ref, data in copied:
        path = study / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    write_json(study / 'frozen.json', frozen)
    with connect(study) as db:
        db.executescript('''CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE trials (
          id INTEGER PRIMARY KEY AUTOINCREMENT, request_key TEXT UNIQUE NOT NULL,
          phase TEXT NOT NULL, candidate_hash TEXT, provenance TEXT NOT NULL,
          state TEXT NOT NULL, decision TEXT, started REAL NOT NULL, finished REAL,
          owner_pid INTEGER NOT NULL, result TEXT, error TEXT);
        ''')
        db.execute('INSERT INTO metadata VALUES (?,?)', ('spec_hash', digest_bytes((study / 'frozen.json').read_bytes())))
    return {'study': str(study), 'spec_hash': digest_bytes((study / 'frozen.json').read_bytes()),
            'membership_counts': {s: sum(r['split'] == s for r in frozen['membership']) for s in ('development', 'purged', 'holdout')}}


def source_commit():
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def status(study: Path):
    spec, spec_hash = binding(study)
    with connect(study) as db:
        rows = [dict(r) for r in db.execute('SELECT * FROM trials ORDER BY id')]
        current = champion(db)
    for row in rows:
        row['provenance'] = json.loads(row['provenance'])
        row['result'] = json.loads(row['result']) if row['result'] else None
    return {'spec_hash': spec_hash, 'development_budget': spec['max_trials'],
            'development_attempts': sum(r['phase'] == 'development' for r in rows),
            'holdout_consumed': any(r['phase'] == 'holdout' for r in rows),
            'champion_attempt': current['id'] if current else None,
            'champion_candidate_hash': current['candidate_hash'] if current else None, 'trials': rows}


def trial(study: Path, candidate: Path, *, key: str, hypothesis: str, change: str,
          model: str = 'offline-deterministic', prompt: bytes = b'', phase: str = 'development', input_error: str | None = None):
    study = study.resolve()
    spec, spec_hash = binding(study)
    if phase not in {'development', 'holdout'} or not key or not hypothesis or not change or not model:
        raise ValueError('phase, key, hypothesis, change, and model are required')
    try:
        code = candidate.read_bytes()
        candidate_hash = digest_bytes(code)
        load_error = None
    except OSError as exc:
        code, candidate_hash, load_error = b'', None, str(exc)
    provenance = {'hypothesis': hypothesis, 'change': change, 'model': model,
                  'prompt_hash': digest_bytes(prompt), 'source_commit': source_commit(),
                  'candidate_hash': candidate_hash, 'spec_hash': spec_hash,
                  'intervention': spec['intervention'], 'input_error': input_error}
    with connect(study) as db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('SELECT * FROM trials WHERE request_key=?', (key,)).fetchone()
        if existing:
            if existing['candidate_hash'] != candidate_hash or existing['phase'] != phase or any(json.loads(existing['provenance'])[field] != provenance[field] for field in ('hypothesis', 'change', 'model', 'prompt_hash', 'spec_hash', 'input_error')):
                raise ValueError('idempotency key reused with different candidate or provenance')
            return row_receipt(existing)
        if phase == 'development':
            count = db.execute("SELECT count(*) FROM trials WHERE phase='development'").fetchone()[0]
            if count >= spec['max_trials']:
                raise ValueError('development trial budget exhausted')
            if db.execute("SELECT 1 FROM trials WHERE phase='holdout'").fetchone():
                raise ValueError('study sealed by final evaluation; development is closed')
        else:
            if db.execute("SELECT 1 FROM trials WHERE phase='holdout'").fetchone():
                raise ValueError('heldout final evaluation already consumed')
            if db.execute("SELECT 1 FROM trials WHERE state='running'").fetchone():
                raise ValueError('finish or recover development attempts before final evaluation')
            current = champion(db)
            if not current or current['candidate_hash'] != candidate_hash:
                raise ValueError('final evaluation requires the recorded development champion')
        cur = db.execute('INSERT INTO trials(request_key,phase,candidate_hash,provenance,state,started,owner_pid) VALUES(?,?,?,?,?,?,?)',
                         (key, phase, candidate_hash, canonical(provenance).decode(), 'running', time.time(), os.getpid()))
        attempt = cur.lastrowid
    attempt_dir = study / 'attempts' / str(attempt)
    attempt_dir.mkdir(parents=True)
    receipt = {'attempt': attempt, 'phase': phase, 'provenance': provenance}
    write_json(attempt_dir / 'started.json', receipt)
    (attempt_dir / 'prompt.bin').write_bytes(prompt)
    result, error = None, None
    try:
        if load_error or input_error:
            raise ValueError(load_error or input_error)
        verify(study, spec)
        (attempt_dir / 'candidate.py').write_bytes(code)
        args = [sys.executable, '-m', 'research.worker', str(study), str(attempt_dir), phase]
        process = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=spec['timeout_seconds'])
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
            (attempt_dir / 'worker.stdout').write_bytes(stdout)
            (attempt_dir / 'worker.stderr').write_bytes(stderr)
            raise TimeoutError('candidate/evaluator trial timed out')
        (attempt_dir / 'worker.stdout').write_bytes(stdout)
        (attempt_dir / 'worker.stderr').write_bytes(stderr)
        if process.returncode:
            raise ValueError(stderr.decode(errors='replace')[-4000:] or 'worker failed')
        result = read_json(attempt_dir / 'evaluation.json')
        verify(study, spec)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    with connect(study) as db:
        db.execute('BEGIN IMMEDIATE')
        decision = 'error'
        if error is None:
            if phase == 'holdout':
                decision = 'final_report'
            else:
                prior = champion(db)
                previous = json.loads(prior['result']) if prior else None
                if previous and result['event_keys'] != previous['event_keys']:
                    error, decision = 'comparison event support changed', 'error'
                elif previous is None:
                    if result['identity_mapping']:
                        decision = 'baseline'
                    else:
                        error = 'run the identity mapping baseline before candidates'
                        decision = 'error'
                else:
                    decision = 'keep' if result['score'] < previous['score'] - spec['minimum_improvement'] else 'discard'
        if decision in {'baseline', 'keep'}:
            db.execute("INSERT OR REPLACE INTO metadata VALUES ('champion_trial',?)", (str(attempt),))
        db.execute('UPDATE trials SET state=?,decision=?,finished=?,result=?,error=? WHERE id=?',
                   ('error' if error else 'complete', decision, time.time(), canonical(result).decode() if result else None, error, attempt))
    receipt.update({'state': 'error' if error else 'complete', 'decision': decision, 'result': result, 'error': error})
    write_json(attempt_dir / 'receipt.json', receipt)
    if decision == 'keep':
        write_json(attempt_dir / 'promotion-proposal.json', {'schema': 'zenith_candidate_proposal_v1',
            'attempt': attempt, 'candidate_hash': candidate_hash, 'spec_hash': spec_hash,
            'provenance': provenance,
            'reason': 'predeclared development Brier improvement on common support',
            'live_mutation_permission': False, 'requires': 'independent prospective shadow evidence and explicit review'})
    return receipt


def finalize(study: Path, *, key: str):
    binding(study)
    with connect(study) as db:
        row = champion(db)
    if not row:
        raise ValueError('no development champion exists')
    provenance = json.loads(row['provenance'])
    candidate = study / 'attempts' / str(row['id']) / 'candidate.py'
    # Reuse the original provenance prompt hash by loading its captured bytes.
    prompt_path = study / 'attempts' / str(row['id']) / 'prompt.bin'
    return trial(study, candidate, key=key, hypothesis=provenance['hypothesis'], change=provenance['change'],
                 model=provenance['model'], prompt=prompt_path.read_bytes() if prompt_path.exists() else b'', phase='holdout')


def recover(study: Path):
    binding(study)
    recovered = []
    with connect(study) as db:
        db.execute('BEGIN IMMEDIATE')
        for row in db.execute("SELECT * FROM trials WHERE state='running'").fetchall():
            try:
                os.kill(row['owner_pid'], 0)
            except ProcessLookupError:
                error = 'owner process disappeared; attempt remains spent'
                db.execute("UPDATE trials SET state='error',decision='error',finished=?,error=? WHERE id=?", (time.time(), error, row['id']))
                receipt = row_receipt(row)
                receipt.update({'state': 'error', 'decision': 'error', 'error': error})
                write_json(study / 'attempts' / str(row['id']) / 'receipt.json', receipt)
                recovered.append(row['id'])
            except PermissionError:
                pass
    return {'recovered_attempts': recovered}
