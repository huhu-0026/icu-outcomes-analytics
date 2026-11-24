"""Shared inputs linking the authorized analysis database and research summary."""

import hashlib

HOURS = (1, 24, 48, 72)
FEATURES = '03_队列与特征工程/analysis'
CALIBRATION = '05_独立患者校准/analysis'
RAW = '02_原始数据/mimic-iv-3.1'
TABLES = '07_最终报告与英文图表/03_tables'
COHORT = f'{FEATURES}/private/cohort.parquet'
V04_RAW = f'{CALIBRATION}/private/nested_raw_oof.npz'
V04_CALIBRATED = f'{CALIBRATION}/private/calibrated_oof.npz'

SHARED_INPUTS = (
    COHORT,
    f'{RAW}/hosp/patients.csv.gz',
    f'{RAW}/icu/icustays.csv.gz',
    V04_RAW,
    V04_CALIBRATED,
    *(f'{TABLES}/{name}' for name in (
        'baseline_performance.csv', 'calibrated_performance.csv',
        'calibration_bins.csv', 'descriptive_statistics.csv', 'group_importance.csv',
    )),
)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fingerprint_inputs(project):
    return {relative: digest(project / relative) for relative in SHARED_INPUTS}


def research_binding(database_meta, summary):
    """Return a hashable binding for a compatible pair, or explain the mismatch."""
    if summary.get('mode') != 'mimic' or summary.get('classification') != 'RESTRICTED_LOCAL':
        raise ValueError('研究汇总的模式或数据分类不正确')
    mart_inputs = database_meta.get('research_input_sha256')
    summary_inputs = summary.get('research_input_sha256')
    for name, inputs in [('分析库', mart_inputs), ('研究汇总', summary_inputs)]:
        if not isinstance(inputs, dict) or set(inputs) != set(SHARED_INPUTS):
            command = 'build-mimic' if name == '分析库' else 'review-research'
            raise ValueError(f'{name}缺少完整输入指纹，请用当前版本重新运行 {command}')
        if any(not isinstance(sha, str) or len(sha) != 64
               or any(c not in '0123456789abcdef' for c in sha) for sha in inputs.values()):
            raise ValueError(f'{name}的输入指纹格式不正确')
    mismatches = [relative for relative in SHARED_INPUTS
                  if mart_inputs[relative] != summary_inputs[relative]]
    if mismatches:
        names = '、'.join(relative.rsplit('/', 1)[-1] for relative in mismatches)
        raise ValueError(f'分析库与研究汇总的输入版本不一致：{names}')
    return tuple(sorted(mart_inputs.items()))


def validate_oof(saved, cohort, name):
    """Check the keys, landmark mask and probability domain against the frozen cohort."""
    import numpy as np

    ids = saved['stay_id']
    if ids.ndim != 1 or len(ids) != len(cohort) or len(np.unique(ids)) != len(cohort):
        raise ValueError(f'{name}: OOF stay coverage mismatch')
    if not np.isin(ids, cohort.index).all():
        raise ValueError(f'{name}: OOF contains unknown stay IDs')
    linked = cohort.loc[ids]
    for key, column in [('label', 'target'), ('subject_id', 'subject_id'), ('fold', 'fold')]:
        if not np.array_equal(saved[key], linked[column]):
            raise ValueError(f'{name}: OOF {key} mismatch')
    if not np.array_equal(saved['hours'], HOURS):
        raise ValueError(f'{name}: OOF landmark order mismatch')
    mask = saved['mask']
    expected = linked.hours.to_numpy()[:, None] >= np.asarray(HOURS)
    if not np.array_equal(mask, expected):
        raise ValueError(f'{name}: OOF risk-set mismatch')
    probabilities = saved['predictions']
    if probabilities.shape != expected.shape:
        raise ValueError(f'{name}: OOF prediction shape mismatch')
    valid = probabilities[expected]
    if not np.all(np.isfinite(valid) & (valid >= 0) & (valid <= 1)):
        raise ValueError(f'{name}: OOF probability out of range')
    return expected
