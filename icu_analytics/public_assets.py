"""Explicit release inputs shared by the ZIP and GitHub Pages builders."""
import hashlib
import json
from contextlib import closing

from .analytics import ROOT, connect, dashboard, metadata
from .statistics import synthetic_research

DEMO_FILE = 'data/demo/mart.sqlite'
DEMO_SHA256 = '24adf071f329d1fb9e4f8f2e2b98f180cd3243b593082b2a4ecbdcc3842f7158'
PUBLIC_FILES = (
    '.github/workflows/ci.yml', '.github/workflows/pages.yml', '.gitignore',
    'LICENSE', 'NOTICE.md', 'README.md', 'requirements.txt', 'app.py',
    '启动演示.cmd', '启动真实分析.cmd',
    'docs/project_audit.md', 'docs/change_report.md', 'docs/acceptance_report.md',
    'docs/public/project_overview.md', 'docs/public/research_design.md',
    'docs/public/statistical_analysis_plan.md', 'docs/public/data_dictionary.md',
    'docs/public/model_development.md', 'docs/public/model_evaluation.md',
    'docs/public/visualization_guide.md',
    'docs/public/dashboard-overview.png', 'docs/public/patient-analysis.png',
    'docs/public/clinical-analysis.png', 'docs/public/data-quality.png',
    'docs/public/mobile-overview.png', 'docs/public/model-evaluation.png',
    'docs/public/project-methods.png', 'docs/public/cohort-construction.png',
    'icu_analytics/__init__.py', 'icu_analytics/analytics.py', 'icu_analytics/build.py',
    'icu_analytics/exports.py', 'icu_analytics/public_assets.py', 'icu_analytics/statistics.py',
    'icu_analytics/research.py', 'icu_analytics/research_figures.py', 'icu_analytics/research_inputs.py',
    'powerbi/FolderQuery.pq', 'powerbi/Measures.dax', 'powerbi/README.md', 'powerbi/theme.json',
    'sql/analysis_queries.sql', 'sql/postgres_load.py', 'sql/schema.sql',
    'scripts/build_pages.py', 'tests/test_analytics.py', 'tests/test_http.py',
    'tests/test_pages.py', 'tests/test_research.py', 'tests/client_parity.cjs',
    'web/app.js', 'web/client-analytics.js', 'web/research-ui.js',
    'web/favicon.svg', 'web/index.html', 'web/style.css', DEMO_FILE,
)


def demo_path():
    source = ROOT / DEMO_FILE
    if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != DEMO_SHA256:
        raise ValueError('Public build requires the verified independent synthetic database')
    return source


def preview():
    with closing(connect(demo_path())) as db:
        meta = metadata(db)
        if meta.get('mode') != 'demo' or meta.get('sources') != []:
            raise ValueError('Invalid synthetic database provenance')
        snapshots = {str(h):dashboard(db,{'hour':h}) for h in (1,24,48,72)}
        research = synthetic_research(db)
    return (
        'window.ICU_PREVIEW='+json.dumps(snapshots,ensure_ascii=False,allow_nan=False)+';\n'
        'window.ICU_RESEARCH='+json.dumps(research,ensure_ascii=False,allow_nan=False)+';\n'
    ).encode('utf-8')
