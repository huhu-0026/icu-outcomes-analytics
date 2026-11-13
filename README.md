# ICU Outcomes Analytics

**面向数据分析／医疗数据分析岗位的个人作品：从 ICU 原始研究数据到可信指标、交互看板与可复用交付。**

![Synthetic showcase](docs/public/dashboard-overview.png)

本项目在 [huhu-0026 的医疗数据分析平台](https://github.com/huhu-0026/medical-data-analysis-platform) 基础上升级，保留来源与 MIT 许可。重点从“生成虚构医院数据”转为“研究队列的数据治理、分析口径与结果解释”。这是个人研究作品，不是在医院生产环境上线的系统。

## 先体验

**[在线交互演示 →](https://huhu-0026.github.io/icu-outcomes-analytics/)**

打开网址即可浏览六页、筛选模拟人群、切换四个预测时点和导出汇总。线上仅使用独立模拟数据；所有指标均非真实研究结果。GitHub Pages 托管静态网页，筛选在浏览器执行，无需运行 Python 后端。


- 双击 `web/index.html`：立即浏览**纯模拟**离线快照，支持六页导航与四时点切换；离线时人口筛选关闭。
- 双击 `启动演示.cmd`：打开完整本地交互演示，可筛选性别、年龄段和 ICU 科室。
- 命令行：`python app.py serve --mode demo --open`。带数据库的公开包仅启动看板时使用 Python 标准库，不必安装重建环境。
- 只有授权本地完整版具有 `data/private`：双击 `启动真实分析.cmd`。它读取真实已纳入队列，不会修改原研究数据或重训模型。

公开展示从零生成的模拟人群为 1,800 名患者 / 2,300 次住院 / 2,600 次 ICU 停留；模拟评分、校准曲线和贡献值仅展示界面与分析方法，不能作为研究性能。

## 六页分析

| 页面 | 分析问题 | 防止的口径错误 |
|---|---|---|
| 总览 | 数据规模、ICU 结构、时点覆盖如何？ | 患者、住院、停留分别计数 |
| 患者画像 | 纳入了谁？年龄、性别和科室结构如何？ | 年龄每位患者仅计一次 |
| 诊断与处方 | 常见诊断与处方结构是什么？ | 不做诊断×药品多对多宽表膨胀 |
| 模型评价 | 区分能力与概率准确性是否一致？ | 不混用 v03 与 v04 实验结果 |
| 数据质量 | 缺失与一致性检查是否可解释？ | 不把缺失当错误，不用统一剂量阈值 |
| 方法与成果 | 如何从问题到可复跑交付？ | 明确研究、演示与临床部署边界 |

人口筛选用于队列/诊断/处方；**冻结模型指标、特征贡献与特征缺失率只随预测时点改变**，始终代表各自全队列或指定解释样本。看板显式提示这个差异，不把已有指标冒充筛选子组重算结果。

## 数据流

```mermaid
flowchart LR
 A[本地授权源表 / 独立模拟生成器] --> B[Python 分块 ETL]
 B --> C[事务构建 + 数据契约检查]
 C --> D[(SQLite 分析库)]
 D --> E[参数化 SQL 汇总]
 E --> F[本地交互看板]
 D --> G[分表 CSV / 可选 PostgreSQL]
 G --> H[Power Query + DAX]
```

默认 SQLite 降低复跑门槛；PostgreSQL 是可选迁移目标，未冒充已经在服务器部署。Web 服务仅绑定 127.0.0.1，没有患者明细接口，没有通用文件下载或 SQL 执行接口，不依赖第三方 CDN。

数据模型以 `dim_patient → fact_admission → fact_icu_stay → fact_prediction` 为主，诊断和处方独立关联住院。SQL 约束校验唯一性、外键、概率范围和合法时点。真实源表只读；临时数据库全部成功后再原子替换，构建失败不破坏已完成数据库。

## 复跑

```text
python -m pip install -r requirements.txt
python app.py build-demo
python -m unittest discover -s tests -v
python app.py serve --mode demo --open
```

本地完整版：`python app.py build-mimic --project "完整复现项目的根目录"`，读取 02 原始表、03 冻结队列、05 折外预测与 07 汇总结果，**不新增模型特征、不调用测试集重新挑选模型**。病历源表、字典映射与处方均分块读取，输入溯源与阶段检查写入 metadata / pipeline_check。

`python app.py export-bi --mode demo` 导出可导入 Power BI 的分表 CSV；见 `powerbi/README.md`。`python app.py export-public` 生成白名单公开 ZIP 与四时点模拟静态快照。真实数据、权重、报告及个体预测不会被此导出器遍历。

## 阅读源码

| 文件 | 展示的技能 |
|---|---|
| icu_analytics/build.py | 分块处理、来源溯源、原子更新、数据契约 |
| sql/schema.sql | 维度/事实分离、主外键、约束与索引 |
| sql/analysis_queries.sql | CTE、窗口函数、去重计数、概率误差重算 |
| icu_analytics/analytics.py | 参数化筛选、正确分母、避免连接膨胀 |
| web/ | 轻量可访问的六页看板、空状态、移动端、汇总导出 |
| tests/ | 重复就诊、空子组、连接膨胀、指标复核及接口边界 |
| powerbi/ | 可导入查询、关系设计、DAX 与主题 |
| docs/public/ | 项目介绍、面试讲述、指标字典与分析边界 |

## 限制

真实分析为单中心回顾性方法复现，临床特征覆盖不等于原文完整重现；不把内部验证称作外部验证，不作治疗因果判断。患者日期经独立偏移，不做真实跨患者月度运营趋势。诊断和处方仅供回顾性描述，不进入早期预测。原 PBIX 未自动改写，新 Power BI 报表需在 Desktop 中按已交付材料导入与核对。

软件见 LICENSE；来源见 NOTICE.md。受限数据的使用与分享遵循 [PhysioNet 的数据协议及衍生资源说明](https://physionet.org/content/mimiciv/3.1/)。

## 在线部署

`.github/workflows/pages.yml` 在 main 更新后自动检查并发布。构建命令为 `python scripts/build_pages.py`；仅打包 8 个明确列出的静态资源，不上传真实库或 Python 服务。构建器核验已公开的模拟库 SHA256、数据来源与固定模拟规模。公开演示必须保留 SYNTHETIC 标记。

真实 MIMIC 分析继续在授权本地环境中运行。访问与衍生数据分享遵循 [PhysioNet 协议](https://physionet.org/content/mimiciv/3.1/)，不能因为原数据脱敏就再次公开个体记录；面向论文的汇总结果应另行检查披露风险与协议要求。
