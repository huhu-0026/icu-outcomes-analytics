import importlib.util
import json
import sys
import tempfile
import shutil
import subprocess
import os
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build_pages',ROOT/'scripts/build_pages.py')
pages=importlib.util.module_from_spec(spec);spec.loader.exec_module(pages)

class PagesTests(unittest.TestCase):
    def test_browser_aggregation_matches_sql_for_filters(self):
        sys.path.insert(0,str(ROOT))
        from icu_analytics.analytics import connect,dashboard
        node=os.environ.get('ICU_NODE') or shutil.which('node')
        if not node: self.skipTest('Node is needed only for client/SQL parity test')
        filters=[{}, {'sex':'F'}, {'sex':'M'}, {'sex':"F' OR 1=1--"}]
        filters += [{'hour':h} for h in (1,24,48,72)]
        filters += [{'age':a} for a in ('18–39','40–54','55–64','65–74','75–84','85+')]
        filters += [{'unit':u} for u in ('Medical ICU','Surgical ICU','Cardiac ICU','Neuro ICU')]
        filters += [{'hour':h,'sex':'F','age':'65–74','unit':'Medical ICU'} for h in (1,24,48,72)]
        db=connect(ROOT/'data/demo/mart.sqlite')
        try:
            fixture={'records':pages.synthetic_records(),'bases':{str(h):dashboard(db,{'hour':h}) for h in (1,24,48,72)},'cases':[{'filters':f,'expected':dashboard(db,f)} for f in filters]}
        finally: db.close()
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'fixture.json';p.write_text(json.dumps(fixture,ensure_ascii=False,allow_nan=False),encoding='utf-8')
            run=subprocess.run([node,str(ROOT/'tests/client_parity.cjs'),str(p)],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertIn('"passed":true',run.stdout)
    def test_static_site_has_only_explicit_synthetic_assets(self):
        with tempfile.TemporaryDirectory() as t:
            d=pages.build(Path(t))
            self.assertEqual({p.suffix for p in d.iterdir()},{'.html','.css','.js','.svg',''})
            html=(d/'index.html').read_text(encoding='utf-8')
            self.assertIn('name="icu-runtime" content="static"',html)
            self.assertIn('client-analytics.js',html)
            data=(d/'client-data.js').read_text(encoding='utf-8')
            payload=json.loads(data.removeprefix('window.ICU_CLIENT_DATA=').removesuffix(';'))
            self.assertEqual(payload['mode'],'demo');self.assertEqual(len(payload['stays']),2600)
            self.assertEqual(len({s['patient_id'] for s in payload['stays']}),1800)
            self.assertFalse(any(p.suffix in ('.sqlite','.npz','.parquet','.pt') for p in d.iterdir()))
    def test_builder_rejects_unexpected_output_files(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t)/'unexpected.txt').write_text('Do not publish me')
            with self.assertRaises(AssertionError): pages.build(Path(t))

if __name__=='__main__': unittest.main()
