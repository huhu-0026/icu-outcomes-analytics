// Create a blank query named LoadTable; paste this entire function.
// Call: = LoadTable("D:\...\data\demo\powerbi", "dim_patient")
// Replace folder with YOUR absolute local export folder. Never point at raw MIMIC tables.
(FolderPath as text, TableName as text) as table =>
let
    Allowed = {"dim_patient","fact_admission","fact_icu_stay","fact_diagnosis","fact_prescription","fact_prediction","model_metric","calibration_bin","feature_quality","feature_importance","pipeline_check"},
    SafeName = if List.Contains(Allowed, TableName) then TableName else error "Unsupported table",
    Source = Csv.Document(File.Contents(FolderPath & "\" & SafeName & ".csv"),[Delimiter=",",Encoding=65001,QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source,[PromoteAllScalars=true]),
    // ICD code remains TEXT, preserving leading zeroes and the ICD version.
    IntegerColumns = {"patient_id","admission_id","stay_id","version","orders","hour","stays","patients","outcome","fold","bin","n","risk_stays","known","rank","sample_patients","passed","checked","failures"},
    DecimalColumns = {"age","los_days","probability_raw","probability_cal","prevalence","mean_probability","auroc","ap","brier","observed_fraction","missing_fraction","median","q25","q75","importance_pp"},
    ExistingIntegers = List.Intersect({Table.ColumnNames(Headers),IntegerColumns}),
    ExistingDecimals = List.Intersect({Table.ColumnNames(Headers),DecimalColumns}),
    Types = List.Transform(ExistingIntegers,each {_,Int64.Type}) & List.Transform(ExistingDecimals,each {_,type number}),
    Typed = Table.TransformColumnTypes(Headers,Types,"en-US")
in
    Typed
