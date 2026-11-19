import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from icu_analytics.analytics import ROOT,connect,dashboard

MIMIC_MART = Path(os.environ.get('ICU_TEST_MIMIC_MART', ROOT/'data/private/mart.sqlite'))

class GrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=sqlite3.connect(':memory:');cls.db.row_factory=sqlite3.Row
        cls.db.executescript((ROOT/'sql/schema.sql').read_text(encoding='utf-8'))
        cls.db.executemany('INSERT INTO dim_patient VALUES(?,?,?,?)',[(1,'F',40,'40–54'),(2,'M',60,'55–64')])
        cls.db.executemany('INSERT INTO fact_admission VALUES(?,?,?)',[(10,1,'EMERGENCY'),(11,1,'URGENT'),(20,2,'ELECTIVE')])
        cls.db.executemany('INSERT INTO fact_icu_stay VALUES(?,?,?,?,?,?,?)',[(100,10,1,'MICU',2,1,0),(101,10,1,'SICU',3,1,0),(110,11,1,'MICU',1,0,0),(200,20,2,'MICU',5,0,1)])
        cls.db.executemany('INSERT INTO fact_diagnosis VALUES(?,?,?,?)',[(10,'001',9,'Example A'),(10,'A01',10,'Example B'),(11,'002',9,'Example C')])
        cls.db.executemany('INSERT INTO fact_prescription VALUES(?,?,?)',[(10,'DRUG A',3),(10,'DRUG B',5),(11,'DRUG C',1)])
        cls.db.executemany('INSERT INTO fact_prediction VALUES(?,?,?,?)',[(100,24,.6,.5),(101,24,.7,.6),(200,24,.1,.2)])
    def test_distinct_grain(self):
        x=dashboard(self.db)['summary'];self.assertEqual((x['patients'],x['admissions'],x['stays']),(2,3,4))
        self.assertEqual(x['age'],50) # Not the 45-year stay-weighted mean.
    def test_repeated_stays_do_not_duplicate_diagnoses_or_orders(self):
        x=dashboard(self.db);self.assertEqual(sum(r['n'] for r in x['diagnoses']),3)
        self.assertEqual(sum(r['n'] for r in x['drugs']),9)
    def test_unit_filter_preserves_selected_admissions_once(self):
        x=dashboard(self.db,{'unit':'SICU'});self.assertEqual(x['summary']['stays'],1)
        self.assertEqual(sum(r['n'] for r in x['diagnoses']),2)
        self.assertEqual(sum(r['n'] for r in x['drugs']),8)
    def test_empty_subgroup_and_sql_payload(self):
        x=dashboard(self.db,{'sex':"F' OR 1=1--"});self.assertEqual(x['summary']['stays'],0)
        self.assertIsNone(x['summary']['mortality']);self.assertEqual(x['coverage'],[])
    def test_landmark_is_valid_observations(self):
        self.assertEqual(dashboard(self.db)['coverage'][0]['n'],3)
        self.assertEqual(dashboard(self.db,{'hour':1})['risk'],[])
    def test_invalid_hour(self):
        with self.assertRaises(ValueError): dashboard(self.db,{'hour':12})
    def test_constraints_reject_orphan_and_duplicate(self):
        with self.assertRaises(sqlite3.IntegrityError): self.db.execute('INSERT INTO fact_admission VALUES(99,99,"INVALID")')
        with self.assertRaises(sqlite3.IntegrityError): self.db.execute('INSERT INTO fact_diagnosis VALUES(10,"001",9,"Duplicate")')

class DataIntegrationTests(unittest.TestCase):
    def test_demo_provenance_and_count_contract(self):
        with connect(ROOT/'data/demo/mart.sqlite') as db:
            d=dashboard(db);self.assertEqual(d['meta']['mode'],'demo')
            self.assertEqual((d['summary']['patients'],d['summary']['admissions'],d['summary']['stays']),(1800,2300,2600))
            self.assertEqual(d['meta']['sources'],[])
    @unittest.skipUnless(MIMIC_MART.is_file(),'Credentialed local database not included in public showcase')
    def test_real_counts_and_same_experiment_probabilities(self):
        from sklearn.metrics import roc_auc_score,average_precision_score
        with connect(MIMIC_MART) as db:
            counts=db.execute('SELECT COUNT(DISTINCT patient_id),COUNT(DISTINCT admission_id),COUNT(*) FROM fact_icu_stay').fetchone()
            self.assertEqual(tuple(counts),(52234,68009,75260))
            n=db.execute('SELECT COUNT(*) FROM fact_prediction').fetchone()[0];self.assertEqual(n,196129)
            # Independently recompute Brier/mean score from row-level predictions vs frozen table.
            for h in (1,24,48,72):
                for col,model in [('probability_raw','nested_raw'),('probability_cal','isotonic')]:
                    b,p=db.execute(f'SELECT AVG((x.{col}-s.outcome)*(x.{col}-s.outcome)),AVG(x.{col}) FROM fact_prediction x JOIN fact_icu_stay s USING(stay_id) WHERE hour=?',(h,)).fetchone()
                    stored=db.execute('SELECT brier,mean_probability FROM model_metric WHERE experiment=? AND model=? AND hour=?',('v04_nested',model,h)).fetchone()
                    self.assertAlmostEqual(b,stored['brier'],places=10);self.assertAlmostEqual(p,stored['mean_probability'],places=10)
                    samples=db.execute(f'SELECT s.outcome,x.{col} FROM fact_prediction x JOIN fact_icu_stay s USING(stay_id) WHERE hour=?',(h,)).fetchall()
                    y=[r[0] for r in samples];prob=[r[1] for r in samples]
                    auc,ap=db.execute('SELECT auroc,ap FROM model_metric WHERE experiment=? AND model=? AND hour=?',('v04_nested',model,h)).fetchone()
                    self.assertAlmostEqual(roc_auc_score(y,prob),auc,places=10)
                    self.assertAlmostEqual(average_precision_score(y,prob),ap,places=10)
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
    def test_every_sql_example_executes(self):
        text='\n'.join(line for line in (ROOT/'sql/analysis_queries.sql').read_text(encoding='utf-8').splitlines() if not line.lstrip().startswith('--'))
        with connect(ROOT/'data/demo/mart.sqlite') as db:
            for query in text.split(';'):
                if query.strip(): db.execute(query).fetchmany(2)

if __name__=='__main__': unittest.main()
