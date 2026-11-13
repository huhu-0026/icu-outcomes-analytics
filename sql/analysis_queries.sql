-- SQLite runnable examples; parameters use named bindings. No patient dates are exported.
-- Q1: Distinct grains. Never count patient rows after joining diagnosis x prescriptions.
SELECT COUNT(DISTINCT patient_id) patients, COUNT(DISTINCT admission_id) admissions,
       COUNT(*) icu_stays, AVG(outcome*1.0) mortality_90d
FROM fact_icu_stay;

-- Q2: Patient age without weighting repeated ICU admissions.
WITH ranked AS (
 SELECT p.*, ROW_NUMBER() OVER (PARTITION BY p.patient_id ORDER BY s.stay_id) rn
 FROM dim_patient p JOIN fact_icu_stay s USING(patient_id)
)
SELECT age_band, COUNT(*) patients, AVG(age) mean_age
FROM ranked WHERE rn=1 GROUP BY age_band;

-- Q3: Prevent many-to-many inflation by pre-aggregating both facts at admission grain.
WITH dx AS (SELECT admission_id,COUNT(*) diagnosis_codes FROM fact_diagnosis GROUP BY admission_id),
rx AS (SELECT admission_id,SUM(orders) prescription_rows FROM fact_prescription GROUP BY admission_id)
SELECT a.admission_id, COALESCE(dx.diagnosis_codes,0) diagnosis_codes,
       COALESCE(rx.prescription_rows,0) prescription_rows
FROM fact_admission a LEFT JOIN dx USING(admission_id) LEFT JOIN rx USING(admission_id);

-- Q4: Prediction coverage is conditional on remaining eligible at each landmark.
SELECT hour,COUNT(*) eligible_stays,COUNT(DISTINCT s.patient_id) eligible_patients,
       AVG(s.outcome*1.0) observed_90d,AVG(x.probability_cal) mean_probability,
       AVG((x.probability_cal-s.outcome)*(x.probability_cal-s.outcome)) brier
FROM fact_prediction x JOIN fact_icu_stay s USING(stay_id) GROUP BY hour ORDER BY hour;

-- Q5: Missingness is not automatically a data error. Keep the actual denominator.
SELECT hour, feature, risk_stays, known, 1.0-known*1.0/risk_stays missing_rate
FROM feature_quality ORDER BY hour,missing_rate DESC;

-- Q6: Same-experiment calibration comparison; never compare v03 vs v04 as pure calibration gain.
SELECT r.hour,r.brier before_brier,c.brier after_brier,c.brier-r.brier difference
FROM model_metric r JOIN model_metric c ON r.experiment=c.experiment AND r.hour=c.hour
WHERE r.model='nested_raw' AND c.model='isotonic' ORDER BY r.hour;
