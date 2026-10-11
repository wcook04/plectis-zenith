"""Fixed, training-only text controls and forward-evidence analog retrieval.

Character TF-IDF is a modest target-trained comparator, not a reproduction of
Ke, Kelly and Xiu. Numerical and narrative analogs are motivated by FinMem and
Wang and Yeung (2026); see docs/finance-adaptive-sources.json for provenance.
"""
from __future__ import annotations

import math
import hashlib
from importlib.metadata import version

import numpy as np

from research.engine import canonical, event_time

TEXT_CONFIG = {'analyzer': 'char', 'ngram_range': (2, 4), 'min_df': 2,
               'max_features': 8192, 'sublinear_tf': True, 'norm': 'l2'}
RETRIEVAL_RULE = '0.8 forward-text cosine + 0.2 exp(-0.5 mean training-standardized state distance squared); stable case-ID ties'


def library_versions():
    return {name: version(name) for name in ('numpy', 'scipy', 'scikit-learn', 'exchange-calendars')}


def evidence_text(asset):
    return '\n'.join(e['content'] for e in asset.get('context_evidence', [])
                     if not e['ref_id'].endswith(':identity'))


def panel_text(packet):
    # Common stories appear under several assets; count each actual text once.
    # Identity remains in the prediction packet, but constant identity boilerplate
    # must not make all memory queries appear alike.
    return '\n'.join(sorted({e['content'] for a in packet['assets']
                            for e in a.get('context_evidence', [])
                            if not e['ref_id'].endswith(':identity')}))


def vectorizer(documents, *, min_df=2):
    from sklearn.feature_extraction.text import TfidfVectorizer
    encoder = TfidfVectorizer(**{**TEXT_CONFIG, 'min_df': min_df})
    try:
        matrix = encoder.fit_transform(documents)
    except ValueError as exc:
        if not any(s in str(exc) for s in ('empty vocabulary', 'no terms remain', 'max_df corresponds')):
            raise
        return None, None
    return encoder, matrix


def metadata(asset, issue_at):
    evidence = [e for e in asset.get('context_evidence', []) if not e['ref_id'].endswith(':identity')]
    ages = [(event_time(issue_at) - event_time(e['available_at'])).total_seconds() / 86400 for e in evidence]
    return [len(evidence), sum(e['kind'] == 'filing' for e in evidence),
            sum(e['availability_basis'] == 'date_only_approximate' for e in evidence),
            min(ages, default=0), max(ages, default=0)]


def asset_records(rows, packets, feature_names=None):
    """The sample ID joins an input; labels never enter this representation."""
    result = []
    for row in rows:
        packet = packets[row['issue_date']]
        matches = [a for a in packet['assets'] if any(
            e['ref_id'].endswith(':identity') and e['content'].endswith(row['symbol'])
            for e in a.get('context_evidence', []))]
        if len(matches) != 1:
            raise ValueError('text-control issuer identity join is not unique')
        a = matches[0]
        if feature_names is None:
            feature_names = sorted(a['features'])
        if set(a['features']) != set(feature_names):
            raise ValueError('numeric feature schema changed')
        result.append({'id': row['sample_id'], 'symbol': row['symbol'],
                       'feature_names': feature_names,
                       'numeric': [a['features'][k] for k in feature_names] + metadata(a, packet['issue_at']),
                       'text': evidence_text(a)})
    return result


def fit_control(rows, packets, *, use_text):
    """Fit all transforms on the supplied matured training support only."""
    from scipy.sparse import csr_matrix, hstack
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    if not rows or any(r['phase'] != 'training' for r in rows):
        raise ValueError('text control fit requires training rows')
    records = asset_records(rows, packets)
    symbols = sorted({r['symbol'] for r in records})
    scaler = StandardScaler().fit([r['numeric'] for r in records])
    identity = np.array([[float(r['symbol'] == s) for s in symbols] for r in records])
    pieces = [csr_matrix(scaler.transform([r['numeric'] for r in records])), csr_matrix(identity)]
    encoder, matrix = vectorizer([r['text'] for r in records]) if use_text else (None, None)
    if encoder is not None:
        pieces.append(matrix)
    model = Ridge(alpha=1., solver='lsqr', tol=1e-8, max_iter=10000).fit(
        hstack(pieces, format='csr'), [r['actual_return'] for r in rows])
    digest = hashlib.sha256(canonical({'vocabulary': encoder.get_feature_names_out().tolist() if encoder is not None else [],
                                     'idf': encoder.idf_.tolist() if encoder is not None else [],
                                     'mean': scaler.mean_.tolist(), 'scale': scaler.scale_.tolist(),
                                     'coefficients': model.coef_.tolist(), 'intercept': float(model.intercept_)})).hexdigest()
    return {'model': model, 'encoder': encoder, 'scaler': scaler, 'symbols': symbols,
            'feature_names': records[0]['feature_names'],
            'receipt': {'training_sample_ids': [r['sample_id'] for r in rows],
                        'fit_end': max(r['outcome_available_at'] for r in rows),
                        'text_features': len(encoder.vocabulary_) if encoder is not None else 0,
                        'alpha': 1., 'solver': 'lsqr', 'text_config': {**TEXT_CONFIG, 'ngram_range': list(TEXT_CONFIG['ngram_range'])},
                        'numeric_feature_names': records[0]['feature_names'],
                        'fitted_transform_model_sha256': digest, 'library_versions': library_versions(),
                        'use_text': use_text, 'selection': 'fixed; no validation tuning'}}


def predict_control(fit, rows, packets):
    from scipy.sparse import csr_matrix, hstack
    if any(event_time(r['issue_at']) <= event_time(fit['receipt']['fit_end']) for r in rows):
        raise ValueError('control labels must mature before prediction')
    records = asset_records(rows, packets, fit['feature_names'])
    pieces = [csr_matrix(fit['scaler'].transform([r['numeric'] for r in records])),
              csr_matrix([[float(r['symbol'] == s) for s in fit['symbols']] for r in records])]
    if fit['encoder'] is not None:
        pieces.append(fit['encoder'].transform([r['text'] for r in records]))
    return {r['id']: float(v) for r, v in zip(records, fit['model'].predict(hstack(pieces, format='csr')), strict=True)}


def retrieve(packet, cases, reviews):
    eligible = [(c, r) for c, r in zip(cases, reviews, strict=True)
                if event_time(c['update_available_at']) < event_time(packet['issue_at'])
                and r.get('status') != 'rejected' and r.get('classification') != 'accounting_error']
    if not eligible:
        return []
    eligible.sort(key=lambda pair: pair[0]['case_id'])
    def state(p):
        return [math.fsum(a['features'][k] for a in p['assets']) / len(p['assets'])
                for k in ('return_5', 'realized_vol_20')]
    states = np.array([state(c['packet']) for c, _ in eligible])
    scale = states.std(axis=0)
    scale[scale < 1e-12] = 1.
    distance = np.mean(((states - np.array(state(packet))) / scale) ** 2, axis=1)
    encoder, matrix = vectorizer([panel_text(c['packet']) for c, _ in eligible], min_df=1)
    cosine = np.zeros(len(eligible)) if encoder is None else (matrix @ encoder.transform([panel_text(packet)]).T).toarray()[:, 0]
    candidates = []
    for i, (case, review) in enumerate(eligible):
        proximity = math.exp(-.5 * float(distance[i]))
        score = .8 * float(cosine[i]) + .2 * proximity
        experience = {'case_id': case['case_id'], 'state': states[i].tolist(),
                      'review': review, 'outcomes': case['outcomes'],
                      'retrieval': {'forward_text_cosine': float(cosine[i]), 'state_proximity': proximity,
                                    'score': score, 'rule': RETRIEVAL_RULE}}
        candidates.append((-score, case['case_id'], experience))
    selected = []
    for _, _, experience in sorted(candidates):
        if len(canonical(selected + [experience])) <= 24000:
            selected.append(experience)
        if len(selected) == 3:
            break
    return selected
