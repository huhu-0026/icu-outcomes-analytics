import importlib.util
import pathlib
import tempfile
import unittest
from contextlib import closing

from icu_analytics.analytics import ROOT, connect, metadata
from icu_analytics.public_assets import DEMO_FILE, PUBLIC_FILES, demo_path, preview
from icu_analytics.statistics import baseline, evaluate_scores, synthetic_research


class StatisticsTests(unittest.TestCase):
    def test_table_one_denominators_missing_and_category_difference(self):
        records = [
            dict(patient_id=1,outcome=0,sex='F',unit='A',age=40),
            dict(patient_id=2,outcome=0,sex='M',unit='A',age=60),
            dict(patient_id=3,outcome=1,sex='M',unit='B',age=70),
            dict(patient_id=4,outcome=1,sex='M',unit='B',age=None),
        ]
        table = baseline(records, ['age'])
        self.assertEqual(table['counts'], [4,2,2])
        age = table['continuous'][0]
        self.assertEqual(age['groups'][0]['median'], 60)
        self.assertEqual(age['groups'][2]['missing'], 1)
        self.assertIsNone(age['smd'])
        female = next(r for r in table['categorical'] if r['feature']=='sex' and r['level']=='F')
        self.assertEqual(female['proportions'], [.25,.5,0])
        self.assertAlmostEqual(female['smd'], -2**.5)
        with self.assertRaises(ValueError):
            baseline(records+[records[0]],['age'])

    def test_perfect_and_tied_predictions(self):
        result=evaluate_scores([0,0,1,1],[.1,.2,.5,.9])
        self.assertEqual((result['auroc'],result['ap'],result['mcc']), (1,1,1))
        self.assertEqual((result['tn'],result['fp'],result['fn'],result['tp']), (2,0,0,2))
        tied=evaluate_scores([0,0,0,1],[.5]*4)
        self.assertEqual((tied['auroc'],tied['ap'],tied['mcc']), (.5,.25,None))
        self.assertEqual(tied['roc'],[[0,0],[1,1]])
        self.assertIsNone(evaluate_scores([1],[.8])['auroc'])
        with self.assertRaises(ValueError):
            evaluate_scores([1],[float('nan')])

    def test_chart_and_table_data_reconcile_to_sql(self):
        with closing(connect(demo_path())) as db:
            r=synthetic_research(db)
            self.assertEqual(r['table1']['counts'][0],db.execute(
                'SELECT COUNT(DISTINCT patient_id) FROM fact_icu_stay').fetchone()[0])
            for result in r['performance']:
                sql=db.execute('SELECT stays,auroc,ap,brier FROM model_metric WHERE experiment=? AND model=? AND hour=?',
                               (result['experiment'],result['model'],result['hour'])).fetchone()
                for key in sql.keys():
                    self.assertAlmostEqual(result[key],sql[key],places=11)

    def test_public_exports_only_allowlisted_and_generated_synthetic(self):
        self.assertEqual(set(p for p in PUBLIC_FILES if p.startswith('data/')), {DEMO_FILE})
        self.assertFalse(any(pathlib.Path(p).suffix in ('.npz','.pt','.parquet','.pbix') for p in PUBLIC_FILES))
        self.assertFalse(any(p.startswith(('validation/','data/private/','docs/local/')) for p in PUBLIC_FILES))
        self.assertIn(b'"classification": "SYNTHETIC"', preview())
        self.assertNotIn(b'RESTRICTED_LOCAL', preview())

    @unittest.skipUnless(all(importlib.util.find_spec(x) for x in ('numpy','pandas','sklearn')),
                         'ETL rebuild requires the optional analysis dependencies')
    def test_synthetic_etl_rebuild_to_fresh_path(self):
        from icu_analytics.build import build_demo
        with tempfile.TemporaryDirectory() as temp:
            dest=pathlib.Path(temp)/'new.sqlite'
            build_demo(dest)
            with closing(connect(dest)) as db:
                self.assertEqual(metadata(db)['sources'],[])
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
                data=synthetic_research(db)
                self.assertEqual(data['table1']['counts'][0],1800)
                self.assertEqual(len(data['performance']),8)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM fact_icu_stay').fetchone()[0],2600)


if __name__=='__main__':
    unittest.main()
