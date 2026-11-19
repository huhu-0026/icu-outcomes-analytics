import csv
import hashlib
import json
import zipfile
from contextlib import closing
from .analytics import ROOT,connect,metadata
from .public_assets import PUBLIC_FILES, preview

def export_bi(mode):
    prefix='data/demo' if mode=='demo' else 'data/private'
    dest=ROOT/prefix/'powerbi';dest.mkdir(exist_ok=True,parents=True)
    # Separate fact tables preserve grain; patients must never be summed from aggregate slices.
    with closing(connect(ROOT/prefix/'mart.sqlite')) as db:
        for table in ('dim_patient','fact_admission','fact_icu_stay','fact_diagnosis','fact_prescription','fact_prediction','model_metric','calibration_bin','feature_quality','feature_importance','pipeline_check'):
            cur=db.execute('SELECT * FROM '+table)
            with (dest/(table+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
                out=csv.writer(f);out.writerow([c[0] for c in cur.description]);out.writerows(cur)
        (dest/'DATA_CLASSIFICATION.txt').write_text(metadata(db)['restriction'],encoding='utf-8')
    print(f'BI CSV tables exported locally: {dest}',flush=True)

def public_bundle():
    """Positive source allowlist. No private research path, database or image is traversed."""
    payload=preview()
    files={}
    for name in PUBLIC_FILES:
        source=ROOT/name
        if source.is_symlink() or source.resolve()!=source.absolute():
            raise ValueError(f'Unexpected link in public release inputs: {name}')
        files[name]=source.read_bytes()
    (ROOT/'web/preview-data.js').write_bytes(payload)
    files['web/preview-data.js']=payload
    manifest={k:hashlib.sha256(v).hexdigest() for k,v in files.items()}
    files['PUBLIC_MANIFEST.json']=json.dumps({'classification':'synthetic-only records and snapshots; no real MIMIC records, predictions, weights or result tables; documentation may describe project-scale counts','files':manifest},indent=2).encode()
    (ROOT/'PUBLIC_MANIFEST.json').write_bytes(files['PUBLIC_MANIFEST.json'])
    path=ROOT/'dist/icu-outcomes-analytics-portfolio.zip';path.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,content in files.items(): z.writestr('icu-outcomes-analytics/'+name,content)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for name,sha in manifest.items(): assert hashlib.sha256(z.read('icu-outcomes-analytics/'+name)).hexdigest()==sha
    (ROOT/'validation/public_export.json').parent.mkdir(exist_ok=True)
    (ROOT/'validation/public_export.json').write_text(json.dumps({'passed':True,'members':len(files),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'policy':'positive allowlist; generated synthetic database and synthetic static snapshots only'},indent=2),encoding='utf-8')
    print(path,flush=True)
