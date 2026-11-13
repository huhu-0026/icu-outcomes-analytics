"""Optional migration into a NEW isolated PostgreSQL schema; never drops user tables."""
import argparse
import os
import re
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from icu_analytics.analytics import ROOT

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['demo','mimic'],default='demo');args=p.parse_args()
    from sqlalchemy import create_engine,text
    import pandas as pd
    dsn=os.environ.get('ICU_POSTGRES_URL')
    if not dsn: p.error('Set ICU_POSTGRES_URL locally; do not paste credentials in chats or commits.')
    schema='icu_portfolio_demo' if args.mode=='demo' else 'icu_portfolio_local'
    engine=create_engine(dsn);source=ROOT/('data/demo' if args.mode=='demo' else 'data/private')/'mart.sqlite'
    if not source.exists(): p.error('Build the selected source database first.')
    ddl=(ROOT/'sql/schema.sql').read_text(encoding='utf-8').replace('PRAGMA foreign_keys=ON;','')
    ddl=re.sub(r'\bREAL\b','DOUBLE PRECISION',ddl)
    try:
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src,engine.begin() as target:
            if target.execute(text('SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name=:s'),{'s':schema}).scalar():
                raise RuntimeError('Target schema already exists. Choose a fresh database; existing data was not changed.')
            target.execute(text('CREATE SCHEMA '+schema))
            target.execute(text('SET LOCAL search_path TO '+schema))
            for statement in ddl.split(';'):
                if statement.strip(): target.execute(text(statement))
            for table in [r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid")]:
                for chunk in pd.read_sql_query('SELECT * FROM '+table,src,chunksize=10000):
                    chunk.to_sql(table,target,schema=schema,if_exists='append',index=False,chunksize=1000)
        print('Loaded isolated schema:',schema)
    except Exception as exc:
        # Some DB driver exceptions include connection parameters; never print raw details here.
        raise SystemExit('PostgreSQL migration failed ('+type(exc).__name__+'). Transaction rolled back. Check local configuration and schema availability.') from None

if __name__=='__main__': main()
