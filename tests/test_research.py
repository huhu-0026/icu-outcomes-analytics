import importlib.util
import pathlib
import tempfile
import unittest
from contextlib import closing

from icu_analytics.analytics import ROOT, connect, metadata
from icu_analytics.public_assets import DEMO_FILE, PUBLIC_FILES, demo_path, preview
from icu_analytics.research_inputs import SHARED_INPUTS, V04_RAW, research_binding, validate_oof
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


class ResearchInputsTests(unittest.TestCase):
    def test_same_cohort_cannot_bind_different_model_inputs(self):
        fingerprints = {name: 'a' * 64 for name in SHARED_INPUTS}
        database = {'research_input_sha256': fingerprints, 'cohort_sha256': 'a' * 64}
        summary = {'mode': 'mimic', 'classification': 'RESTRICTED_LOCAL',
                   'research_input_sha256': dict(fingerprints), 'cohort_sha256': 'a' * 64}
        self.assertEqual(dict(research_binding(database, summary)), fingerprints)

        for path in (V04_RAW, next(p for p in SHARED_INPUTS if p.endswith('calibration_bins.csv')),
                     next(p for p in SHARED_INPUTS if p.endswith('group_importance.csv'))):
            with self.subTest(path=path):
                inputs = {**fingerprints, path: 'b' * 64}
                with self.assertRaisesRegex(ValueError, path.rsplit('/', 1)[-1]):
                    research_binding(database, {**summary, 'research_input_sha256': inputs})
        with self.assertRaisesRegex(ValueError, 'build-mimic'):
            research_binding({'cohort_sha256': 'a' * 64}, summary)
        with self.assertRaisesRegex(ValueError, 'review-research'):
            research_binding(database, {**summary, 'research_input_sha256': {}})

    @unittest.skipUnless(all(importlib.util.find_spec(x) for x in ('numpy', 'pandas')),
                         'OOF validation requires the optional analysis dependencies')
    def test_oof_rejects_reordered_hours_wrong_membership_and_partial_coverage(self):
        import numpy as np
        import pandas as pd

        cohort = pd.DataFrame({'subject_id': [3, 9], 'fold': [0, 4], 'target': [1, 0],
                               'hours': [24, 72]}, index=[10, 20])
        mask = np.array([[True, True, False, False], [True, True, True, True]])
        saved = {'stay_id': np.array([10, 20]), 'hours': np.array([1, 24, 48, 72]),
                 'subject_id': np.array([3, 9]), 'fold': np.array([0, 4]), 'label': np.array([1, 0]),
                 'mask': mask, 'predictions': np.where(mask, .5, np.nan)}
        np.testing.assert_array_equal(validate_oof(saved, cohort, 'fixture'), mask)
        for changes, error in (
            ({'hours': np.array([1, 48, 24, 72])}, 'landmark order'),
            ({'mask': mask[::-1]}, 'risk-set mismatch'),
            ({'stay_id': np.array([10])}, 'stay coverage mismatch'),
        ):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                validate_oof({**saved, **changes}, cohort, 'fixture')


if __name__=='__main__':
    unittest.main()
