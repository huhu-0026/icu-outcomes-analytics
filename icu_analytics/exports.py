import csv
import hashlib
import json
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path
from .analytics import ROOT,connect,dashboard,metadata

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
    source_files=['README.md','LICENSE','NOTICE.md','requirements.txt','.gitignore','.github/workflows/ci.yml','.github/workflows/pages.yml','scripts/build_pages.py','tests/test_pages.py','tests/client_parity.cjs','app.py','启动演示.cmd','启动真实分析.cmd','tests/test_analytics.py','tests/test_http.py','sql/schema.sql','sql/analysis_queries.sql','sql/postgres_load.py','powerbi/README.md','powerbi/FolderQuery.pq','powerbi/Measures.dax','powerbi/theme.json']
    for folder in ('icu_analytics','web','docs/public'):
        source_files.extend(str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    source_files=sorted(set(source_files))
    with closing(connect(ROOT/'data/demo/mart.sqlite')) as db:
        if metadata(db).get('mode')!='demo': raise ValueError('Public export requires independent demo database')
        # Static bundle contains all synthetic filter combinations? Base snapshot per hour only;
        # cohort filters require the included local server for accurate SQL recomputation.
        snapshots={str(h):dashboard(db,{'hour':h}) for h in (1,24,48,72)}
    payload=('window.ICU_PREVIEW='+json.dumps(snapshots,ensure_ascii=False,allow_nan=False)+';').encode('utf-8')
    (ROOT/'web/preview-data.js').write_bytes(payload)
    files={name:(ROOT/name).read_bytes() for name in source_files if name!='web/preview-data.js'}
    files['web/preview-data.js']=payload
    # Export demonstrably synthetic DB into a reproducible public package; exclude private tree.
    files['data/demo/mart.sqlite']=(ROOT/'data/demo/mart.sqlite').read_bytes()
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
