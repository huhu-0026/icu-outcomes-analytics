"""Descriptive and prediction summaries. This module uses the standard library."""
from collections import Counter
from itertools import groupby
from math import sqrt
from statistics import mean, median, quantiles, stdev


def continuous(values):
    known = [x for x in values if x is not None]
    quartiles = quantiles(known, n=4, method='inclusive') if len(known) > 1 else None
    return {
        'n': len(known), 'missing': len(values) - len(known),
        'mean': mean(known) if known else None,
        'sd': stdev(known) if len(known) > 1 else None,
        'median': median(known) if known else None,
        'q1': quartiles[0] if quartiles else (known[0] if known else None),
        'q3': quartiles[2] if quartiles else (known[0] if known else None),
    }


def standardized_difference(non_events, events):
    """Event group minus non-event group, scaled by the mean group variance."""
    if non_events['sd'] is None or events['sd'] is None:
        return None
    scale = sqrt((non_events['sd']**2 + events['sd']**2) / 2)
    return (events['mean'] - non_events['mean']) / scale if scale else None


def baseline(records, continuous_fields):
    """Each record must be one index stay per patient."""
    if len({r['patient_id'] for r in records}) != len(records):
        raise ValueError('Table 1 requires one record per patient')
    groups = [records, [r for r in records if r['outcome'] == 0],
              [r for r in records if r['outcome'] == 1]]
    result = {'counts': [len(g) for g in groups], 'continuous': [], 'categorical': []}
    for name in continuous_fields:
        stats = [continuous([r[name] for r in g]) for g in groups]
        result['continuous'].append({'feature': name, 'groups': stats,
                                     'smd': standardized_difference(*stats[1:])})
    for name in ('sex', 'unit'):
        counts = [Counter(r[name] for r in g) for g in groups]
        for level in sorted(counts[0]):
            proportions = [c[level] / len(g) if g else None for c, g in zip(counts, groups)]
            p, q = proportions[1:]
            scale = sqrt((p * (1 - p) + q * (1 - q)) / 2) if p is not None and q is not None else 0
            result['categorical'].append({
                'feature': name, 'level': level, 'counts': [c[level] for c in counts],
                'proportions': proportions, 'smd': (q - p) / scale if scale else None,
            })
    return result


def evaluate_scores(labels, probabilities, threshold=0.5):
    """ROC/PR in threshold order with ties grouped. AP uses step integration."""
    if len(labels) != len(probabilities) or not labels:
        raise ValueError('Score and outcome arrays must have equal nonzero length')
    if any(y not in (0, 1) for y in labels) or any(not 0 <= p <= 1 for p in probabilities):
        raise ValueError('Invalid labels or probabilities')
    events = sum(labels)
    nonevents = len(labels) - events
    tp = sum(y == 1 and p >= threshold for y, p in zip(labels, probabilities))
    fp = sum(y == 0 and p >= threshold for y, p in zip(labels, probabilities))
    fn, tn = events - tp, nonevents - fp
    denominator = sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    result = {
        'stays': len(labels), 'prevalence': events / len(labels), 'threshold': threshold,
        'brier': mean((p - y)**2 for y, p in zip(labels, probabilities)),
        'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp,
        'mcc': (tp * tn - fp * fn) / denominator if denominator else None,
        'auroc': None, 'ap': None, 'roc': [], 'pr': [],
    }
    if not events or not nonevents:
        return result
    roc, pr = [[0, 0]], [[0, 1]]
    tp = fp = 0
    for _, tied in groupby(sorted(zip(probabilities, labels), reverse=True), key=lambda row: row[0]):
        for _, outcome in tied:
            tp += outcome
            fp += 1 - outcome
        roc.append([fp / nonevents, tp / events])
        pr.append([tp / events, tp / (tp + fp)])
    result['auroc'] = sum((b[0] - a[0]) * (b[1] + a[1]) / 2 for a, b in zip(roc, roc[1:]))
    result['ap'] = sum((b[0] - a[0]) * b[1] for a, b in zip(pr, pr[1:]))
    # Display downsampling does not change metrics calculated from the full curve.
    for key, points in [('roc', roc), ('pr', pr)]:
        stride = max(1, (len(points) + 999) // 1000)
        result[key] = points[::stride]
        if result[key][-1] != points[-1]:
            result[key].append(points[-1])
    return result


def synthetic_research(db):
    """Study panels on the complete, independently generated demo dataset."""
    records = [dict(row) for row in db.execute('''
        SELECT p.patient_id, p.age, p.sex, s.unit, s.outcome
        FROM dim_patient p JOIN fact_icu_stay s USING(patient_id)
        WHERE s.stay_id = (SELECT MIN(x.stay_id) FROM fact_icu_stay x
                           WHERE x.patient_id = p.patient_id)
        ORDER BY p.patient_id
    ''')]
    performance = []
    for hour in (1, 24, 48, 72):
        samples = db.execute('''
            SELECT s.outcome, x.probability_raw, x.probability_cal
            FROM fact_prediction x JOIN fact_icu_stay s USING(stay_id)
            WHERE x.hour = ?
        ''', (hour,)).fetchall()
        if samples:
            labels, a, b = zip(*samples)
            for model, scores in [('nested_raw', a), ('isotonic', b)]:
                performance.append(dict(experiment='synthetic_simulation', model=model,
                                        hour=hour, **evaluate_scores(labels, scores)))
    return {'mode': 'demo', 'classification': 'SYNTHETIC', 'table1': baseline(records, ['age']),
            'performance': performance}
