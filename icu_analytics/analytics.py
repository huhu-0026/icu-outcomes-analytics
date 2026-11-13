import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def connect(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db

def rows(db, sql, params=()):
    return [dict(r) for r in db.execute(sql, params)]

def metadata(db):
    return {r['key']: json.loads(r['value']) for r in db.execute('SELECT * FROM metadata')}

def dashboard(db, filters=None):
    filters = filters or {}
    hour = int(filters.get('hour', 24))
    if hour not in (1,24,48,72):
        raise ValueError('hour must be 1, 24, 48 or 72')
    clauses, params = [], []
    for key, column in [('sex','p.sex'), ('age','p.age_band'), ('unit','s.unit')]:
        value = filters.get(key)
        if value and value != 'all':
            clauses.append(column + ' = ?')
            params.append(value)
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    cte = 'WITH selected AS (SELECT s.*,p.sex,p.age,p.age_band FROM fact_icu_stay s JOIN dim_patient p USING(patient_id)' + where + ') '
    def q(sql, extra=()):
        return rows(db, cte + sql, tuple(params) + tuple(extra))
    summary = q('SELECT COUNT(DISTINCT patient_id) patients,COUNT(DISTINCT admission_id) admissions,COUNT(*) stays,AVG(los_days) los,AVG(outcome*1.0) mortality FROM selected')[0]
    # One first-eligible-ICU age per patient, never weighted by number of stays.
    summary['age'] = q('SELECT AVG(age) age FROM (SELECT DISTINCT patient_id,age FROM selected)')[0]['age']
    unit = q('SELECT unit label,COUNT(*) n,AVG(outcome*1.0) mortality FROM selected GROUP BY unit ORDER BY n DESC')
    age = q('SELECT age_band label,COUNT(DISTINCT patient_id) n FROM selected GROUP BY age_band ORDER BY age_band')
    sex = q('SELECT sex label,COUNT(DISTINCT patient_id) n FROM selected GROUP BY sex ORDER BY n DESC')
    clinical = q('SELECT d.diagnosis label,COUNT(*) n FROM fact_diagnosis d WHERE d.admission_id IN(SELECT admission_id FROM selected) GROUP BY d.diagnosis ORDER BY n DESC,label LIMIT 10')
    drugs = q('SELECT d.drug label,SUM(d.orders) n,COUNT(*) admissions FROM fact_prescription d WHERE d.admission_id IN(SELECT admission_id FROM selected) GROUP BY d.drug ORDER BY n DESC,label LIMIT 10')
    coverage = q('SELECT x.hour,COUNT(*) n,COUNT(DISTINCT s.patient_id) patients FROM fact_prediction x JOIN selected s USING(stay_id) GROUP BY x.hour ORDER BY x.hour')
    risk = q('SELECT MIN(9,CAST(x.probability_cal*10 AS INTEGER)) bucket,COUNT(*) n FROM fact_prediction x JOIN selected s USING(stay_id) WHERE x.hour=? GROUP BY bucket ORDER BY bucket', (hour,))
    metrics = rows(db, 'SELECT * FROM model_metric WHERE hour=? ORDER BY experiment,model', (hour,))
    bins = rows(db, 'SELECT * FROM calibration_bin WHERE hour=? ORDER BY model,bin', (hour,))
    missing = rows(db, 'SELECT * FROM feature_quality WHERE hour=? ORDER BY missing_fraction DESC,feature', (hour,))
    importance = rows(db, 'SELECT * FROM feature_importance WHERE hour=? AND output=? ORDER BY rank', (hour,'calibrated_probability'))
    # Clinical and descriptive charts respond to cohort filters; frozen scientific evaluations remain global.
    return dict(meta=metadata(db), filters=dict(hour=hour, **{k:filters.get(k,'all') for k in ('sex','age','unit')}), summary=summary,units=unit,ages=age,sexes=sex,diagnoses=clinical,drugs=drugs,coverage=coverage,risk=risk,metrics=metrics,calibration=bins,missingness=missing,importance=importance,checks=rows(db,'SELECT * FROM pipeline_check ORDER BY rule'),options={k:[r[0] for r in db.execute(sql)] for k,sql in {'sex':'SELECT DISTINCT sex FROM dim_patient ORDER BY sex','age':'SELECT DISTINCT age_band FROM dim_patient ORDER BY age_band','unit':'SELECT DISTINCT unit FROM fact_icu_stay ORDER BY unit'}.items()})
