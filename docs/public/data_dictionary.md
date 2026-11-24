# 数据字典

这份字典覆盖项目实际使用的 SQLite 分析库、冻结模型特征和看板指标。临床定义对应授权本地的 MIMIC-IV 3.1 Development 队列。公开演示沿用展示结构，评分和贡献值来自独立模拟数据。源表名与字段定义可对照 [MIMIC-IV 表关系](https://mimic.mit.edu/docs/iv/about/schema-overview.html) 和 [3.1 版本说明](https://physionet.org/content/mimiciv/3.1/)。

## 分析库字段

一位患者可有多次住院，一次住院可有多次 ICU 停留。同一位患者的索引停留是在冻结队列内按 `intime`、再按 `stay_id` 排序后的首个合格停留。下表中的主键、外键和类型以 [SQLite 表结构](../../sql/schema.sql) 为准。

| 表 · 每行代表 | 字段 | 来源与处理 |
|---|---|---|
| `dim_patient` · 患者 | `patient_id` · 整数主键 | `hosp.patients.subject_id`。患者级分区、分折和去重使用同一标识。 |
|  | `sex` · 文本 | `patients.gender` 的记录类别。SQLite 要求非空。本地研究汇总将未匹配的值记为 `Unknown`。 |
|  | `age`、`age_band` · 数值、文本 | 索引停留的估计年龄和年龄组。连续值可空，年龄组将缺失记为 `Unknown`。按科室筛选时仍使用该患者的索引年龄。 |
| `fact_admission` · 住院 | `admission_id`、`patient_id`、`admission_type` | 住院 ID 为整数主键，患者 ID 为外键。来源为 `admissions.hadm_id`、`subject_id` 和 `admission_type`。 |
| `fact_icu_stay` · ICU 停留 | `stay_id`、`admission_id`、`patient_id` | 停留 ID 为整数主键，住院和患者 ID 为外键。来自冻结队列，以源 ICU 停留标识连接。 |
|  | `unit`、`los_days` | `icustays.first_careunit` 给出本次停留的首次科室，缺失记为 `Unknown`。停留天数为 `(outtime - intime) / 86400`，时间差以秒计。 |
|  | `outcome`、`fold` | 二元结局与冻结的患者外层折号，均为整数。同一患者的各次停留共享折号。结局的日期规则见下节。 |
| `fact_diagnosis` · 住院 × ICD 编码 × 版本 | `admission_id`、`code`、`version`、`diagnosis` | 前三列组成主键。使用 `diagnoses_icd`，按 `icd_code + icd_version` 关联 `d_icd_diagnoses`。编码保留文本，未匹配标题记为 `Unmapped diagnosis`。 |
| `fact_prescription` · 住院 × 药名 | `admission_id`、`drug`、`orders` | 前两列组成主键。源药名去除首尾空格并统一大写，空值记为 `Unknown`。`orders` 是处方源表的记录行数。 |
| `fact_prediction` · ICU 停留 × 时点 | `stay_id`、`hour`、`probability_raw`、`probability_cal` | 前两列组成主键。时点为 1、24、48、72 小时。真实库的两列概率来自 v04 同一网络的折外原概率和 Isotonic 概率，取值均为 0 至 1。只有冻结风险集内的停留才有预测行。 |

**年龄的两个口径。** 模型特征 `age` 按每次停留计算，公式为 `anchor_age + YEAR(intime) - anchor_year`，保留 `16 < age ≤ 100`，其余记为缺失。画像和 Table 1 取索引停留的年龄。MIMIC-IV 把锚定年超过 89 岁的 `anchor_age` 编码为 91，估计的高龄值需按这一规则理解。当前看板把所有已知且小于 40 岁的年龄标作「18–39」，该分箱也会纳入 17 岁。 [MIMIC-IV 患者表](https://mimic.mit.edu/docs/iv/modules/hosp/patients.html) · [年龄分组实现](../../icu_analytics/build.py)

## 结局、预测时点与样本

| 字段或概念 | 粒度与取值 | 项目口径 |
|---|---|---|
| `target` → `outcome` | ICU 停留，整数 0 或 1 | 若 `patients.dod` 落在 `DATE(intime)` 至该日期加 90 天的闭区间，标记为 1。其他情况标记为 0，包括死亡日期缺失。标签 0 表示该窗口内无已记录死亡。 |
| `hour` | 入 ICU 后的整小时，评价使用 1、24、48、72 | 预测时刻为 `intime + hour` 小时。四个时点共享入科日起算的结局窗口。 |
| `hours`、`mask` | 冻结队列可评价时长、停留 × 时点的布尔标记 | `hours` 是连续可评价的完整小时数，上限 72。预测要严格早于出科和可用的住院死亡时刻。仅有死亡日期时，预测日期须早于死亡日期。时点 `h` 的 `mask` 等价于 `hours ≥ h`。 |
| 折外预测（OOF） | ICU 停留 × 时点 × 实验及模型 | 使用未参与该折模型训练的留出患者预测。v04 校准映射也在与该外层验证折隔离的患者上拟合。复算核对停留 ID、患者 ID、折号、结局和时点标记。 |

## 模型特征

冻结方案 `corrected_core25_v03` 定义 25 个原尺度槽位，v03 和 v04 使用这套特征定义。动态特征按 **停留 × 入科后小时** 记录。下表合并描述同一临床概念的不同统计量，同时列出每个实际字段。表中的数值范围包含两端，属于本项目的冻结清洗规则。

| 冻结字段 | 源表与项目编号 | 输出单位、有效值及处理 |
|---|---|---|
| `hr_min`、`hr_median`、`hr_max` | `icu.chartevents`，220045 | 心率，次/分，40–240。接受 `bpm` 或空单位，取最近有效测量小时的最小值、中位数、最大值。 |
| `sbp_min`、`sbp_median`、`sbp_max` | `icu.chartevents`，220050 / 220179 / 225309 | 收缩压，mmHg，0–300。接受 `mmHg`、`mm Hg` 或空单位，汇总最近有效测量小时。 |
| `temperature_min`、`temperature_median`、`temperature_max` | `icu.chartevents`，223761 / 223762 | 体温，统一为 °C，20–42。223761 按华氏摄氏公式换算，空单位按项目编号对应的单位处理。 |
| `gcs_min`、`gcs_median`、`gcs_max` | `icu.chartevents`，220739 / 223900 / 223901 | GCS 睁眼、言语、运动组件求和，分别为 1–4、1–5、1–6 的整数，总分 3–15。组件距本次评估须小于 6 小时。最新评估不完整、冲突、失效或出现插管相关言语标记时，该状态记缺失。 |
| `pafi_min`、`pafi_median`、`pafi_max` | `hosp.labevents`，50821 / 50816 / 52033。补充用 `icu.chartevents` 223835 | 明确为动脉标本的 PaO₂ 除以 FiO₂ 比例，单位 mmHg。PaO₂ 范围按 5.3–39.9 kPa 等值核验，FiO₂ 统一为 0.21–1.00。优先用同标本 FiO₂，无匹配时允许此前 4 小时内的监护 FiO₂。无可用分母或最近分母无效时记缺失。 |
| `ph_min`、`ph_median`、`ph_max` | `hosp.labevents`，50820 / 52033 | 动脉血 pH，无量纲，6.5–7.7。使用报告已可得、明确的动脉标本。 |
| `leucocytes_median` | `hosp.labevents`，51300 / 51301 | 白细胞，×10⁹/L，0–40。源 `K/uL` 与 `10^9/L` 数值等价。 |
| `creatinine_median` | `hosp.labevents`，50912 | 肌酐，μmol/L。源值 mg/dL 乘 88.4，保留 17.7–1326。 |
| `bilirubin_median` | `hosp.labevents`，50885 | 总胆红素，μmol/L。源值 mg/dL 乘 17.1，保留 1.7–855。 |
| `platelets_median` | `hosp.labevents`，51265 | 血小板，×10⁹/L，0–1000。源 `K/uL` 与 `10^9/L` 数值等价。 |
| `age` | `hosp.patients`、`icu.icustays` | 停留级估计年龄，年。按上文公式及缺失规则处理。在该停留的有效小时内保持同值。 |
| `pre_icu_los_days` | `hosp.admissions.admittime`、`icu.icustays.intime` | `(intime - admittime)` 的秒数除以 86400。负值或缺少时间时记缺失。 |
| `mechanical_ventilation_recorded` | `icu.chartevents`，223849 / 229314 / 226732 | 已记录的呼吸支持状态。明确有创或无创通气为 1，识别到的非机械支持为 0。仅有气管导管或气切、冲突、未映射或距测量 ≥14 小时时为未知。 |

### 时间窗口与缺失

- **可用性。** `charttime` 必须早于预测时刻，`storetime` 必须在测量时刻至预测时刻之间，包含两端。缺任一时间的记录不进入特征。监护记录按停留 ID 关联并校对患者及可用住院 ID。化验按患者和住院关联，允许使用入科前 24 小时内的记录。
- **聚合。** 生命体征和四项常规化验先筛选单位和范围，再按测量小时聚合。同一测量键使用预测时已到达的最新报告版本，同一最新报告时刻的数值冲突取中位数。入科前化验并入第一个测量小时。后续没有较新有效测量时沿用最近可得小时的聚合值。GCS 和血气组在最新测量小时内汇总连续有效记录，新的无效状态会中断沿用。
- **预处理。** 原尺度特征无有效值时记缺失。训练侧对 24 个连续槽位拟合均值填补与缩放，年龄和入科前住院天数拟合时每次停留只计一次。通气状态拆成 `vent_positive`、`vent_unknown` 两个指示列，合计 26 个模型输入列。看板的特征缺失率使用填补前的原尺度槽位。
- **首小时示例。** `hr_median` 的 1 小时值来自入科后第一个小时内、在首小时结束时已报告的有效心率。Table 1 的首小时心率、收缩压、GCS 和肌酐只取每位患者的索引停留。

## 看板指标与分母

| 看板指标或结果表 | 分母及计算 | 筛选范围 |
|---|---|---|
| 患者、住院、ICU 停留、平均年龄 | 从筛选后的停留去重计患者和住院，停留按行数计。平均年龄用每位患者一次的已知索引年龄。 | 性别、索引年龄、每次停留的首次科室。 |
| 90 天结局率、平均 ICU 时长 | 筛选后全部 ICU 停留的 `outcome` 均值、`los_days` 均值。科室结局率以该科室停留为分母。 | 使用队列筛选，分母不随预测时点改变。 |
| 预测时点覆盖 | 分别报告每个时点有预测记录的停留数和去重患者数。相对覆盖以同一筛选下的 1 小时停留数为分母。 | 使用队列筛选及各时点风险集。 |
| 诊断和处方频次 | 对筛选后的住院 ID 去重。诊断按住院 × ICD 编码 × 版本计数，再按名称汇总。处方按源处方行汇总，另计涉及住院数。 | 使用队列筛选。两者均为回顾性描述，可能包含预测时点以后的记录。 |
| Table 1、SMD、调整 OR | 一位患者一个索引停留。连续变量按有效值计算中位数和 IQR，并报告缺失数。分类比例以各结局组人数为分母。SMD 方向为标签 1 减标签 0。调整 OR 使用年龄、记录性别完整的病例。 | 使用定义好的全队列研究样本。 |
| `model_metric` · 区分度及概率误差 | 每实验 × 模型 × 时点。记录可评价停留数、患者数、标签 1 比例、均值预测概率、AUROC、AP 和 Brier。Brier 为预测概率与二元标签之差的平方均值。研究汇总另有 MCC 和混淆计数，分类阈值为 0.50。 | 使用实验在该时点的完整折外风险集。 |
| `calibration_bin` · 概率校准 | 每模型 × 时点 × 分箱，报告箱内样本数、平均预测概率和标签 1 比例。真实 v04 按各模型概率尝试分十个分位箱，重复边界时减少箱数。 | 使用该模型在该时点的完整折外风险集。 |
| `feature_quality` · 特征缺失 | 每特征 × 时点。`risk_stays` 为可评价停留数，`known` 为原尺度上有值的停留数。`missing_fraction = 1 - known / risk_stays`。 | 使用完整时点风险集。 |
| `feature_importance` · 分组历史贡献 | 每输出 × 时点 × 特征组，记录平均绝对贡献（概率百分点）、排序及解释样本患者数。 | 真实 v06 基于固定解释样本，公开演示使用模拟示意值。 |
| `pipeline_check` · 数据检查 | 每条规则记录是否通过、检查数量、失败数量和规则说明。各规则的计数单位见其说明。 | 分析库构建或上游冻结核验的记录。 |

`metadata` 按键保存分析库模式、来源和构建信息。 `bi_cohort` 按记录性别、索引年龄组和停留科室预聚合。同一患者可能进入多个科室组，各组患者数不能直接相加为总人数。

数据来源、字段生成和分析实现分别见 [研究设计](research_design.md)、[模型开发](model_development.md)、[统计分析计划](statistical_analysis_plan.md)、[模型评价](model_evaluation.md) 和 [SQLite 汇总代码](../../icu_analytics/analytics.py)。模型特征规则对照授权本地研究项目第 03 章的冻结方案和特征构建代码。
