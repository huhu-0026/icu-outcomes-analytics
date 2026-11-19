# 临床数据字典

| 字段或概念 | 来源与粒度 | 类型、单位及处理 |
|---|---|---|
| subject_id / patient_id | patients · 患者 | 整数键。患者级分区 |
| hadm_id / admission_id | admissions · 住院 | 整数键。一个患者可有多次住院 |
| stay_id | icustays · ICU 停留 | 整数键。一个住院可有多次 ICU 停留 |
| age | anchor_age 与入科年份 · 停留 | 年。超范围置缺失。画像以患者索引停留年龄分组 |
| sex | patients.gender · 患者 | 来源类别。缺失用 Unknown 描述 |
| unit | icustays.first_careunit · 停留 | 类别。显示首次科室 |
| pre_icu_los_days | admissions.admittime 到 ICU intime | 天。负值置缺失 |
| HR / SBP / 温度 | chart events · ICU 小时 | 次/分、mmHg、°C。有效小时 min/median/max |
| GCS | chart events · ICU 小时 | 组件转总分。缺组件及冲突保守置缺失 |
| PaO₂/FiO₂、动脉 pH | lab/chart · ICU 小时 | PaO₂ 分压与 FiO₂ 分数配对，pH 无量纲。依赖可得的动脉标本 |
| 白细胞、肌酐、胆红素、血小板 | lab events · ICU 小时 | ×10⁹/L、μmol/L、μmol/L、×10⁹/L。有效小时中位数 |
| 通气 | chart events · ICU 小时 | 阳性、阴性或未知。模型编码为阳性与未知两列 |
| diagnosis | ICD code + version · 住院 | 字符串编码去重。出院回顾性 |
| prescriptions | prescriptions · 住院×规范药名 | 按源处方行汇总 |
| target / outcome | patients.dod 与 index ICU | 二元日历日期标签。定义单见研究设计 |
| OOF | 冻结模型 · 停留×时点 | [0,1]。与预测时点 mask、折及标签一一匹配 |

聚合前约束测量时点早于预测，报告时点不晚于预测。变量级缺失、单位及来源详证在完整本地项目的第 03 和 07 章。Table 1 展示已实现连续变量的有效及缺失数量，质量页按所选时点显示全队列各变量缺失率。

[研究设计](research_design.md) · [模型开发](model_development.md)
