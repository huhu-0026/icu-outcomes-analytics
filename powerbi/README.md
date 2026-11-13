# Power BI 接入：真实模型与原始 PBIX 的区别

本次已经交付可运行的 Web 看板、分析库、CSV 导出器、Power Query 函数、DAX 和主题。`upstream/powerbi/*.pbix` 是上游原始合成数据模板，**未修改、未宣称已连接真实数据**。本机未自动操作 Power BI Desktop，因此尚无经 Desktop 刷新并验证的新 PBIX。

1. 在本项目运行 `python app.py export-bi --mode demo`（模拟）或 `--mode mimic`（本地真实）。
2. Power BI Desktop 新建报表，打开“转换数据”，新建空白查询 `LoadTable`，在高级编辑器粘贴 `FolderQuery.pq`。
3. 为每张表新建引用函数的查询，例如 `= LoadTable("D:\项目\data\demo\powerbi", "dim_patient")`。实际路径在 M 字符串中使用单个反斜杠；上例为示意，请直接粘贴资源管理器中的路径。ICD code 保持文本。
4. 建立单向关系：dim_patient[patient_id] 1:* fact_admission[patient_id]；fact_admission[admission_id] 1:* fact_icu_stay[admission_id] / fact_diagnosis[admission_id] / fact_prescription[admission_id]；fact_icu_stay[stay_id] 1:* fact_prediction[stay_id]。**不额外建立 patient→stay 活跃路径，不用双向关系**。
5. 建立 Landmark 时点表及关系，按 Measures.dax 添加度量。患者数/住院数从筛选后的 ICU 事实表去重统计。多模型指标用矩阵分行，不能取多个模型最大值当整体表现。
6. 报表六页参考 Web 版本；导入 theme.json。Model metric / missingness / importance 是冻结全队列表，保持与患者和科室筛选断开，另用 hour 显式筛选。缺失率不可跨时点直接相加。
7. 对照 Web 看板验证总人数与科室筛选、24h 覆盖及 Brier。模拟版应为 1,800 患者 / 2,300 住院 / 2,600 ICU 停留；真实版为 52,234 / 68,009 / 75,260。

可以复用原 PBIX 的版式，但原来的 `public patient_synthetic` 等表、医院排名、门诊数、ICD 七条硬编码规则不能沿用。Power BI Desktop 中需按新模型重建或替换查询和视觉字段。

可选 PostgreSQL：本项目默认 SQLite 本地运行，无需数据库密码。若有本地 PostgreSQL，安装可选驱动，在本地设置 `ICU_POSTGRES_URL` 后运行 `python sql/postgres_load.py --mode demo`。只创建全新 `icu_portfolio_demo` 或 `icu_portfolio_local` schema；若已存在则拒绝覆盖。本次没有 PostgreSQL 服务可供实测，此迁移路径不计入已通过验证的功能。

官方参考：[Csv.Document](https://learn.microsoft.com/en-us/powerquery-m/csv-document)、[DISTINCTCOUNT](https://learn.microsoft.com/en-us/dax/distinctcount-function-dax)。
