"""Authorized local summaries from frozen Development artifacts."""
import csv
import json
from pathlib import Path

from .statistics import baseline, evaluate_scores
from .research_inputs import (
    CALIBRATION, COHORT, FEATURES, HOURS, RAW, TABLES,
    digest, fingerprint_inputs, validate_oof,
)

PHASE2 = '11_项目治理与方法审查/phase2_20261118'


def adjusted_age_sex(frame):
    """Exploratory association model on patient-index complete cases."""
    import numpy as np
    import pandas as pd
    import statsmodels.api as sm

    known = frame['age'].notna() & frame['sex'].isin(['F', 'M'])
    cases = frame.loc[known]
    x = pd.DataFrame({'age_per_10_years': (cases.age - 65) / 10,
                      'male_vs_female': cases.sex.eq('M').astype(float)})
    fit = sm.GLM(cases.outcome, sm.add_constant(x), family=sm.families.Binomial()).fit(cov_type='HC1')
    if not fit.converged:
        raise ValueError('Exploratory association model did not converge')
    ci = fit.conf_int()
    return {'n': len(cases), 'excluded': len(frame) - len(cases), 'events': int(cases.outcome.sum()),
            'terms': [{'term': term, 'or': float(np.exp(fit.params[term])),
                       'low': float(np.exp(ci.loc[term, 0])), 'high': float(np.exp(ci.loc[term, 1]))}
                      for term in x.columns]}


def collect(project):
    import numpy as np
    import pandas as pd

    project = Path(project).resolve()
    shared = fingerprint_inputs(project)
    audited = json.loads((project/PHASE2/'artifact_registry.json').read_text(encoding='utf-8'))['artifacts']
    fingerprints = {row['path']: row['sha256'] for row in audited}
    used = {}

    def verified(relative):
        source = project / relative
        observed = shared.get(relative) or digest(source)
        if fingerprints.get(relative) != observed:
            raise ValueError(f'Frozen artifact fingerprint mismatch: {relative}')
        used[relative] = observed
        return source

    cohort = pd.read_parquet(verified(COHORT))
    raw_root = project / RAW
    patients = pd.read_csv(raw_root/'hosp/patients.csv.gz', usecols=['subject_id', 'gender'])
    units = pd.read_csv(raw_root/'icu/icustays.csv.gz', usecols=['stay_id', 'first_careunit'])
    index = cohort.sort_values(['intime','stay_id']).drop_duplicates('subject_id')
    index = index.merge(patients, on='subject_id', validate='one_to_one', how='left')
    index = index.merge(units, on='stay_id', validate='one_to_one', how='left')
    frame = index.rename(columns={'subject_id':'patient_id','gender':'sex',
                                  'first_careunit':'unit','target':'outcome'})
    frame[['sex','unit']] = frame[['sex','unit']].fillna('Unknown')
    raw = np.load(verified(f'{FEATURES}/private/raw25.npy'), mmap_mode='r', allow_pickle=False)
    with np.load(verified(f'{FEATURES}/private/index.npz'),allow_pickle=False) as feature_index:
        if not np.array_equal(feature_index['stay_id'][cohort.row.to_numpy()],cohort.stay_id):
            raise ValueError('Feature rows and cohort stay IDs disagree')
    plan = json.loads((project/FEATURES/'frozen_plan.json').read_text(encoding='utf-8'))
    columns = ['age','pre_icu_los_days','hr_median','sbp_median','gcs_median','creatinine_median']
    for feature in columns[2:]:
        frame[feature] = raw[frame.row.to_numpy(), 0, plan['columns'].index(feature)]
    if not cohort.stay_id.is_unique or len(frame) != cohort.subject_id.nunique():
        raise ValueError('Cohort grain mismatch')
    table1 = baseline(frame[columns+['patient_id','outcome','sex','unit']].astype(object)
                      .where(lambda value:value.notna(),None).to_dict('records'), columns)
    anchor = cohort.set_index('stay_id')
    performance = []
    models = [
        (FEATURES, 'logistic_oof.npz', 'v03_baseline', 'logistic', 'M4-LR-V03-20261112'),
        (FEATURES, 'lstm_oof.npz', 'v03_baseline', 'lstm', 'M4-LSTM-V03-20261112'),
        (CALIBRATION, 'nested_raw_oof.npz', 'v04_nested', 'nested_raw', 'M4-CAL-V04-20261112'),
        (CALIBRATION, 'calibrated_oof.npz', 'v04_nested', 'isotonic', 'M4-CAL-V04-20261112'),
    ]
    tab = project / TABLES
    for directory, filename, experiment, model, experiment_id in models:
        frozen = pd.read_csv(tab/('baseline_performance.csv' if experiment == 'v03_baseline'
                                  else 'calibrated_performance.csv'))
        with np.load(verified(f'{directory}/private/{filename}'), allow_pickle=False) as saved:
            mask = validate_oof(saved, anchor, model)
            for j, hour in enumerate(HOURS):
                valid = mask[:, j]
                result = evaluate_scores(saved['label'][valid].astype(int).tolist(),
                                         saved['predictions'][valid,j].tolist())
                ref = frozen[(frozen.model == model) & (frozen.hour == hour)].iloc[0]
                for key in ('stays','auroc','ap','brier','tn','fp','fn','tp'):
                    if abs(result[key] - ref[key]) > 1e-10:
                        raise ValueError(f'{experiment_id} {hour} h disagrees with frozen {key}')
                performance.append(dict(experiment=experiment,experiment_id=experiment_id,
                                        model=model,hour=hour,**result))
    subgroup = []
    for sex, group in frame.groupby('sex'):
        n, events = len(group), int(group.outcome.sum())
        subgroup.append({'group': sex,'n':n,'events':events,'rate':events/n})
    association = adjusted_age_sex(frame)
    sensitivity = adjusted_age_sex(frame[frame.age.lt(90)])
    risk = pd.read_csv(project/PHASE2/'risk_set_decomposition.csv').to_dict('records')
    for row in risk:
        if row['saved_risk'] != int(cohort.hours.ge(row['hour']).sum()):
            raise ValueError('Risk audit and cohort disagree')
    result = {
        'mode':'mimic', 'classification':'RESTRICTED_LOCAL', 'dataset':'Development',
        'analysis_id':'M4-PORTFOLIO-DESCRIPTIVE-20261119',
        'cohort_sha256':shared[COHORT], 'research_input_sha256':shared,
        'provenance':used, 'table1':table1,'performance':performance, 'risk_audit':risk,
        'association':association,'association_age_lt_90':sensitivity,'subgroup':subgroup,
        'calibration':pd.read_csv(tab/'calibration_bins.csv').to_dict('records'),
        'feature_missingness':pd.read_csv(tab/'descriptive_statistics.csv')
            [['hour','feature','risk_stays','known','missing_fraction']].to_dict('records'),
        'population':{'patients':len(frame),'admissions':int(cohort.hadm_id.nunique()),'stays':len(cohort)},
    }
    if fingerprint_inputs(project) != shared:
        raise ValueError('Shared research inputs changed during review')
    return result


def write_review(project, output):
    """Create a separate, local output directory. Existing runs are immutable."""
    import tempfile
    from .research_figures import draw

    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f'Choose an unused output directory: {output}')
    if output.is_relative_to(Path(project).resolve()):
        raise ValueError('Write this analysis to a separate local workspace')
    output.parent.mkdir(parents=True, exist_ok=True)
    result = collect(project)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='research-') as temp:
        staging = Path(temp)/'result'
        staging.mkdir()
        (staging/'research_summary.json').write_text(
            json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        write_tables(result, staging)
        draw(result, staging)
        staging.rename(output)
    return output


def write_tables(result, output):
    """Write human-readable analysis tables alongside the dashboard payload."""
    table = result['table1']
    headers = ('variable','level_or_measure','overall','label_0','label_1','smd')
    rows = [('Index patients','N',*table['counts'],'')]
    for row in table['continuous']:
        cells = [f"{g['median']:.3g} [{g['q1']:.3g}, {g['q3']:.3g}]"
                 if g['n'] else '' for g in row['groups']]
        rows.append((row['feature'],'Median [Q1, Q3]',*cells,row['smd']))
        rows.append((row['feature'],'Known n',*[g['n'] for g in row['groups']],''))
        rows.append((row['feature'],'Missing n',*[g['missing'] for g in row['groups']],''))
    for row in table['categorical']:
        cells = [f'{n} ({p:.1%})' if p is not None else ''
                 for n,p in zip(row['counts'],row['proportions'])]
        rows.append((row['feature'],row['level'],*cells,row['smd']))
    with (output/'table1_RESTRICTED_LOCAL.csv').open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)
    columns=('experiment_id','experiment','model','hour','stays','prevalence','auroc','ap',
             'brier','mcc','threshold','tn','fp','fn','tp')
    with (output/'oof_metrics_RESTRICTED_LOCAL.csv').open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore')
        writer.writeheader()
        writer.writerows(result['performance'])
