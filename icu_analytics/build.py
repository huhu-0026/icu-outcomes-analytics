"""Atomic, validated local mart builds; raw sources are opened read-only."""
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .analytics import ROOT

def age_band(a):
    return np.select([pd.isna(a),a<40,a<55,a<65,a<75,a<85],['Unknown','18–39','40–54','55–64','65–74','75–84'],default='85+')

def insert(db, table, frame):
    # pandas.to_sql can commit implicitly: use explicit insert for atomic bulk builds.
    if len(frame):
        db.executemany('INSERT INTO '+table+' VALUES('+','.join('?' for _ in frame.columns)+')',frame.replace({np.nan:None}).itertuples(index=False,name=None))

def check(db, name, checked, failures, detail):
    db.execute('INSERT INTO pipeline_check VALUES(?,?,?,?,?)',(name,int(failures==0),int(checked),int(failures),detail))
    if failures:
        raise ValueError(f'{name}: {failures} failures')

def begin(destination):
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    temp=destination.with_suffix('.building.sqlite')
    if temp.exists(): temp.unlink()
    db=sqlite3.connect(temp)
    db.executescript((ROOT/'sql/schema.sql').read_text(encoding='utf-8'))
    db.execute('PRAGMA journal_mode=DELETE')
    return db,temp

def finish(db,temp,destination,meta):
    violations=db.execute('PRAGMA foreign_key_check').fetchall()
    check(db,'Foreign-key integrity',1,len(violations),'Every fact links to a valid dimension; no orphan records.')
    for k,v in meta.items(): db.execute('INSERT INTO metadata VALUES(?,?)',(k,json.dumps(v,ensure_ascii=False)))
    db.commit()
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    db.close()
    os.replace(temp,destination)
    print(json.dumps({'database':str(destination),'status':'passed','mode':meta['mode']},ensure_ascii=False),flush=True)

def build_mimic(project,destination):
    start=time.time();project=Path(project).resolve()
    raw=project/'02_原始数据/mimic-iv-3.1'
    cohortpath=project/'03_队列与特征工程/analysis/private/cohort.parquet'
    tables=project/'07_最终报告与英文图表/03_tables'
    db,temp=begin(destination)
    sources=[]
    def read(relative,**kw):
        p=raw/relative;sources.append({'path':relative,'bytes':p.stat().st_size})
        return pd.read_csv(p,**kw)
    c=pd.read_parquet(cohortpath).sort_values(['intime','stay_id'])
    if c.stay_id.duplicated().any(): raise ValueError('Duplicate cohort stay_id')
    pat=read('hosp/patients.csv.gz',usecols=['subject_id','gender'])
    first=c.drop_duplicates('subject_id')[['subject_id','age']].merge(pat,on='subject_id',how='left',validate='one_to_one')
    first['age_band']=age_band(first.age)
    insert(db,'dim_patient',first[['subject_id','gender','age','age_band']])
    adm=read('hosp/admissions.csv.gz',usecols=['subject_id','hadm_id','admission_type'])
    adm=adm[adm.hadm_id.isin(c.hadm_id)]
    insert(db,'fact_admission',adm[['hadm_id','subject_id','admission_type']])
    stays=read('icu/icustays.csv.gz',usecols=['stay_id','first_careunit'])
    c=c.merge(stays,on='stay_id',how='left',validate='one_to_one')
    c['los_days']=(pd.to_datetime(c.outtime)-pd.to_datetime(c.intime)).dt.total_seconds()/86400
    c['unit']=c.first_careunit.fillna('Unknown')
    insert(db,'fact_icu_stay',c[['stay_id','hadm_id','subject_id','unit','los_days','target','fold']])
    check(db,'Cohort grain',len(c),int(c.stay_id.duplicated().sum()),'One row per ICU stay; patient/admission/stay counts kept separate.')
    check(db,'Patient fold isolation',c.subject_id.nunique(),int((c.groupby('subject_id').fold.nunique()>1).sum()),'Repeated ICU stays of a patient stay in the same outer fold.')
    ids=set(c.hadm_id);lookup=read('hosp/d_icd_diagnoses.csv.gz',dtype={'icd_code':'string'},keep_default_na=False)
    for chunk in read('hosp/diagnoses_icd.csv.gz',usecols=['hadm_id','icd_code','icd_version'],dtype={'icd_code':'string'},chunksize=500000):
        x=chunk[chunk.hadm_id.isin(ids)].drop_duplicates(['hadm_id','icd_code','icd_version'])
        x=x.merge(lookup,on=['icd_code','icd_version'],how='left',validate='many_to_one')
        x['long_title']=x.long_title.fillna('Unmapped diagnosis')
        db.executemany('INSERT OR IGNORE INTO fact_diagnosis VALUES(?,?,?,?)',x[['hadm_id','icd_code','icd_version','long_title']].itertuples(index=False,name=None))
    print('Cohort and ICD dictionary loaded; scanning prescription orders…',flush=True)
    orderrows=0
    for chunk in read('hosp/prescriptions.csv.gz',usecols=['hadm_id','drug'],chunksize=500000):
        x=chunk[chunk.hadm_id.isin(ids)].copy();x['drug']=x.drug.fillna('Unknown').str.strip().str.upper().replace('','Unknown')
        g=x.groupby(['hadm_id','drug']).size().reset_index(name='orders');orderrows+=len(x)
        db.executemany('INSERT INTO fact_prescription VALUES(?,?,?) ON CONFLICT(admission_id,drug) DO UPDATE SET orders=orders+excluded.orders',g.itertuples(index=False,name=None))
    check(db,'Prescription aggregation',orderrows,abs(orderrows-db.execute('SELECT COALESCE(SUM(orders),0) FROM fact_prescription').fetchone()[0]),'Counts raw prescription rows; this is not an administration or dose measure.')
    pdir=project/'05_独立患者校准/analysis/private'
    pred=np.load(pdir/'calibrated_oof.npz');unc=np.load(pdir/'nested_raw_oof.npz')
    assert np.array_equal(pred['stay_id'],unc['stay_id']) and np.array_equal(pred['mask'],unc['mask'])
    labelmap=c.set_index('stay_id').target
    assert np.array_equal(labelmap.loc[pred['stay_id']].to_numpy(),pred['label'])
    keyed=c.set_index('stay_id')
    assert np.array_equal(keyed.loc[pred['stay_id'],'subject_id'].to_numpy(),pred['subject_id'])
    assert np.array_equal(keyed.loc[pred['stay_id'],'fold'].to_numpy(),pred['fold'])
    assert np.array_equal(pred['fold'],unc['fold']) and np.array_equal(pred['label'],unc['label'])
    n=0
    for j,h in enumerate(pred['hours']):
        valid=pred['mask'][:,j].astype(bool)
        pr=unc['predictions'][valid,j];pc=pred['predictions'][valid,j]
        assert np.isfinite(pr).all() and np.isfinite(pc).all()
        db.executemany('INSERT INTO fact_prediction VALUES(?,?,?,?)',[(int(i),int(h),float(a),float(b)) for i,a,b in zip(pred['stay_id'][valid],pr,pc)])
        n+=int(valid.sum())
    check(db,'Prediction coverage',n,abs(n-db.execute('SELECT COUNT(*) FROM fact_prediction').fetchone()[0]),'Only valid landmark observations; outcome is 90 days from ICU admission.')
    for name,experiment in [('baseline_performance.csv','v03_baseline'),('calibrated_performance.csv','v04_nested')]:
        f=pd.read_csv(tables/name)
        if experiment=='v04_nested': f=f[f.model.isin(['nested_raw','isotonic'])]
        f.insert(0,'experiment',experiment)
        insert(db,'model_metric',f[['experiment','hour','model','stays','patients','prevalence','mean_probability','auroc','ap','brier']])
    insert(db,'calibration_bin',pd.read_csv(tables/'calibration_bins.csv'))
    insert(db,'feature_quality',pd.read_csv(tables/'descriptive_statistics.csv'))
    f=pd.read_csv(tables/'group_importance.csv')
    f['output']=f.output.replace({'isotonic_probability':'calibrated_probability'})
    insert(db,'feature_importance',f[['hour','output','group','group_label','mean_abs_contribution_pp','rank','sample_patients']])
    verified=json.loads((project/'03_队列与特征工程/analysis/results/特征独立核验.json').read_text(encoding='utf-8'))
    check(db,'Upstream temporal audit (frozen)',verified['raw_record_truncation_prefix_checks'],int(not verified['all_passed']),'Recorded research audit: source/report times checked; not rerun by dashboard ETL.')
    orphan=db.execute('SELECT COUNT(*) FROM fact_icu_stay s JOIN fact_admission a USING(admission_id) WHERE s.patient_id<>a.patient_id').fetchone()[0]
    check(db,'Admission ownership',len(c),orphan,'ICU stay and hospital admission belong to the same patient.')
    meta=dict(mode='mimic',title='ICU Outcomes Analytics',dataset='MIMIC-IV 3.1 · eligible replication cohort',scope='BIDMC, single centre; retrospective research only',built_utc=pd.Timestamp.now(tz='UTC').isoformat(),source_commit='83f89e845d80426141dec0fef755f3f684ca9c51',sources=sources,cohort_sha256=hashlib.sha256(cohortpath.read_bytes()).hexdigest(),duration_seconds=round(time.time()-start,2),model_scope='Frozen full-cohort OOF evaluation; cohort filters do not recompute model metrics or feature missingness.',date_policy='Patient-shifted dates are not used for cross-patient calendar trends.',count_policy='Patients and admissions are distinct counts. Mortality is ICU-stay-level, 90 days after ICU admission.',clinical_policy='Discharge diagnoses and prescription records are retrospective descriptive data, never added as model inputs.',restriction='Local credentialed use. Do not publish this database, exports, or real-data screenshots without an appropriate review.')
    finish(db,temp,destination,meta)

def build_demo(destination):
    """Independent synthetic records and predictions, never sampled from MIMIC."""
    from sklearn.metrics import roc_auc_score,average_precision_score,brier_score_loss
    rng=np.random.default_rng(20261113);db,temp=begin(destination);n=1800
    age=np.clip(rng.normal(63,17,n),18,95).round(1)
    insert(db,'dim_patient',pd.DataFrame({'id':np.arange(1,n+1),'sex':rng.choice(['F','M'],n),'age':age,'band':age_band(age)}))
    n_adm=2300;patient=np.r_[np.arange(1,n+1),rng.integers(1,n+1,n_adm-n)]
    insert(db,'fact_admission',pd.DataFrame({'id':np.arange(1,n_adm+1),'patient':patient,'type':rng.choice(['EMERGENCY','ELECTIVE','URGENT'],n_adm,p=[.72,.16,.12])}))
    n_stay=2600;adm=np.r_[np.arange(1,n_adm+1),rng.integers(1,n_adm+1,n_stay-n_adm)]
    ps=patient[adm-1];severity=rng.normal(0,1,n_stay)
    latent=1/(1+np.exp(-(-2.3+(age[ps-1]-50)*.022+severity)))
    outcome=rng.binomial(1,latent);los=rng.gamma(1.5,2.5,n_stay)+.15
    units=rng.choice(['Medical ICU','Surgical ICU','Cardiac ICU','Neuro ICU'],n_stay,p=[.4,.3,.2,.1])
    insert(db,'fact_icu_stay',pd.DataFrame({'id':np.arange(1,n_stay+1),'adm':adm,'pat':ps,'unit':units,'los':los,'y':outcome,'fold':ps%5}))
    diagnoses=[('I10',10,'Essential hypertension'),('E119',10,'Type 2 diabetes'),('I509',10,'Heart failure'),('J189',10,'Pneumonia'),('N179',10,'Acute kidney injury'),('A419',10,'Sepsis')]
    for a in range(1,n_adm+1):
        for idx in rng.choice(len(diagnoses),size=int(rng.integers(1,4)),replace=False):
            db.execute('INSERT INTO fact_diagnosis VALUES(?,?,?,?)',(a,*diagnoses[idx]))
        for drug in rng.choice(['SODIUM CHLORIDE','HEPARIN','ACETAMINOPHEN','POTASSIUM CHLORIDE','INSULIN','FUROSEMIDE'],size=3,replace=False):
            db.execute('INSERT INTO fact_prescription VALUES(?,?,?)',(a,str(drug),int(rng.integers(1,12))))
    for h in [1,24,48,72]:
        m=los*24>=h;signal=np.log(latent[m]/(1-latent[m]))+rng.normal(0,1.1/(1+h/36),m.sum())
        cal=1/(1+np.exp(-signal));raw=1/(1+np.exp(-(signal+.6 if h==1 else signal+.04)))
        db.executemany('INSERT INTO fact_prediction VALUES(?,?,?,?)',[(int(i+1),h,float(r),float(c)) for i,r,c in zip(np.flatnonzero(m),raw,cal)])
        y=outcome[m]
        for name,p in [('nested_raw',raw),('isotonic',cal)]:
            # Demo labels describe visual roles only; no fitted isotonic/LSTM claim.
            db.execute('INSERT INTO model_metric VALUES(?,?,?,?,?,?,?,?,?,?)',('synthetic_simulation',h,name,int(m.sum()),int(len(np.unique(ps[m]))),float(y.mean()),float(p.mean()),float(roc_auc_score(y,p)),float(average_precision_score(y,p)),float(brier_score_loss(y,p))))
            for b,ix in enumerate(np.array_split(np.argsort(p),10),1):
                db.execute('INSERT INTO calibration_bin VALUES(?,?,?,?,?,?)',(h,name,b,len(ix),float(p[ix].mean()),float(y[ix].mean())))
        for j,feature in enumerate(['Age','Heart rate','GCS','Creatinine','Bilirubin','PaO2 / FiO2','Temperature','Platelets']):
            missing=0. if j==0 else float(np.clip((j/10)*np.exp(-h/60)+rng.uniform(0,.04),0,.95))
            known=int(m.sum()*(1-missing));db.execute('INSERT INTO feature_quality VALUES(?,?,?,?,?,?,?,?)',(feature,h,int(m.sum()),known,1-known/int(m.sum()),None,None,None))
            db.execute('INSERT INTO feature_importance VALUES(?,?,?,?,?,?,?)',(h,'calibrated_probability',feature,feature,float(6/(j+1)),j+1,320))
    for rule,checked,detail in [('Cohort grain',n_stay,'Unique synthetic ICU stay key.'),('Patient fold isolation',n,'Deterministic synthetic patient grouping.'),('Admission ownership',n_stay,'Patient/admission join consistency.')]: check(db,rule,checked,0,detail)
    finish(db,temp,destination,dict(mode='demo',title='ICU Outcomes Analytics',dataset='Independent synthetic showcase',scope='Synthetic data · no patient data · not research findings',built_utc='2026-11-13T00:00:00Z',sources=[],source_commit='83f89e845d80426141dec0fef755f3f684ca9c51',model_scope='Simulated scores and illustrative contribution sizes; no trained LSTM/isotonic/SHAP claim. Model panels use the full synthetic cohort.',date_policy='No patient calendar dates exported.',count_policy='Patients/admissions/stays are separate. Synthetic mortality is stay-level.',clinical_policy='Generated diagnoses and prescription counts for UI demonstration.',restriction='Synthetic-only showcase. No MIMIC records, fitted weights, or real research results.'))
