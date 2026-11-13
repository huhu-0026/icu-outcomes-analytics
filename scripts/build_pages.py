"""Build a static synthetic-only site using the standard library."""
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASSETS=('index.html','style.css','app.js','favicon.svg','preview-data.js','client-analytics.js')

def synthetic_records():
    source=ROOT/'data/demo/mart.sqlite'
    manifest=json.loads((ROOT/'PUBLIC_MANIFEST.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest['files']['data/demo/mart.sqlite'],'Unverified demo database'
    db=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        meta={r['key']:json.loads(r['value']) for r in db.execute('SELECT * FROM metadata')}
        assert meta['mode']=='demo' and meta['sources']==[],'Only independent synthetic data may be published'
        records={'mode':'demo'}
        queries={
            'stays':'SELECT s.stay_id,s.admission_id,s.patient_id,s.unit,s.los_days,s.outcome,p.sex,p.age,p.age_band FROM fact_icu_stay s JOIN dim_patient p USING(patient_id)',
            'diagnoses':'SELECT * FROM fact_diagnosis',
            'prescriptions':'SELECT * FROM fact_prescription',
            'predictions':'SELECT stay_id,hour,probability_cal FROM fact_prediction',
        }
        for name,sql in queries.items(): records[name]=[dict(r) for r in db.execute(sql)]
        assert len(records['stays'])==2600 and len({r['patient_id'] for r in records['stays']})==1800
        return records
    finally: db.close()

def build(destination=None):
    destination=Path(destination or ROOT/'dist/pages')
    destination.mkdir(exist_ok=True,parents=True)
    # Positive asset allowlist; never copy the repository or a database into the site.
    for name in ASSETS:
        content=(ROOT/'web'/name).read_bytes()
        if name=='index.html':
            html=content.decode('utf-8')
            html=html.replace('<head>','<head><meta name="icu-runtime" content="static">',1)
            html=html.replace('<script src="app.js" defer>', '<script src="client-data.js" defer></script><script src="client-analytics.js" defer></script><script src="app.js" defer>',1)
            content=html.encode('utf-8')
        (destination/name).write_bytes(content)
    payload='window.ICU_CLIENT_DATA='+json.dumps(synthetic_records(),ensure_ascii=False,separators=(',',':'),allow_nan=False)+';'
    (destination/'client-data.js').write_text(payload,encoding='utf-8',newline='\n')
    (destination/'.nojekyll').write_bytes(b'')
    expected=set(ASSETS)|{'client-data.js','.nojekyll'}
    assert {p.name for p in destination.iterdir()}==expected,'Unexpected file in static output; use a fresh output directory'
    assert not any(p.is_symlink() for p in destination.iterdir())
    print(json.dumps({'status':'passed','output':str(destination),'assets':len(expected),'mode':'synthetic-only','backend_required':False}))
    return destination

if __name__=='__main__': build()
