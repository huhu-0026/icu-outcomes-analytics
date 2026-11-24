# 模型开发与本地复现

历史研究使用入科后前 72 小时的序列。25 个临床槽位形成 26 列模型输入。连续量的填补和缩放参数在各折训练范围内拟合，通气阳性和未知分别编码。各时点评价使用相应风险集，特征可得性以测量时间、报告时间和预测时点为准。

| 实验 | 当前证据 |
|---|---|
| M4-LR-V03-20261112 | 每时点×五折的 20 个 L2 Logistic。四时点快照，基准主要时点 24h |
| M4-LSTM-V03-20261112 | 五个单向 LSTM。固定 16 隐藏单元、四轮训练。有效时长 mask |
| M4-CAL-V04-20261112 | 五折各自划分训练、校准、折外验证患者。每折四个 Isotonic 共 20 个映射。主要 1h 同网络 Brier 对比 |
| M4-EXPL-V06-20261112 | 13 组历史解释，外层验证抽样，训练患者为参照 |

## v03 · Logistic 与 LSTM

```mermaid
%%{init: {"htmlLabels": false, "flowchart": {"htmlLabels": false}}}%%
flowchart TB
  accTitle: v03 患者五折基线比较
  accDescr: 在每折训练侧拟合预处理和模型，汇总留出患者的 Logistic 与 LSTM 预测。
  development["Development 患者五折"] --> training["四折训练患者"]
  development --> holdout["一折留出患者"]
  training --> preprocess["训练侧拟合预处理"]
  preprocess --> logistic["Logistic 时点快照"]
  preprocess --> lstm["LSTM 历史序列"]
  logistic --> predict["留出折时点预测"]
  lstm --> predict
  holdout --> predict
  predict --> oof["汇总五个留出折的 OOF"]
  oof --> compare["同一时点与风险集比较"]
```

每位患者的预测来自留出该患者的折。v03 的主要对比时点为 24 小时，其余时点用于观察结果随风险集的变化。

## v04 · 同网络概率校准

```mermaid
%%{init: {"htmlLabels": false, "flowchart": {"htmlLabels": false}}}%%
flowchart TB
  accTitle: v04 训练校准验证分工
  accDescr: 每个外层折隔离网络训练、映射校准和留出验证患者，同一网络的两套概率在同一留出折比较。
  outer["Development 外层五折"] --> training["内层训练患者"]
  outer --> calibration["内层校准患者"]
  outer --> holdout["外层验证患者"]
  training --> network["拟合预处理及 LSTM"]
  network --> calibration_scores["计算校准患者概率"]
  calibration --> calibration_scores
  calibration_scores --> mapping["按时点拟合 Isotonic"]
  network --> raw["计算验证患者原概率"]
  holdout --> raw
  mapping --> calibrated["计算同一批校准概率"]
  raw --> calibrated
  raw --> oof["汇总成对 OOF"]
  calibrated --> oof
```

v04 以首小时 Brier 为重点，同时保留各时点的其他评价指标。v06 单独归档分组历史 Shapley 解释，抽样来自外层验证患者，参照来自对应网络的训练患者。

以上流程记录授权本地项目的历史方法。第 03、05、06 章保存模型及核验产物，第 07 章保存结果表。本仓库导入这些冻结产物，并提供只读复算。

## 授权本地复算

安装 requirements 后使用 PowerShell。将占位路径替换为本机目录，选择新的输出目录。

```powershell
python app.py build-mimic --project "D:/本地完整复现项目"
python app.py review-research --project "D:/本地完整复现项目" --output "validation/新的研究目录"
python app.py serve --mode mimic --research-dir "validation/新的研究目录" --open
```

`review-research` 对照阶段二登记的 SHA256 和保存的索引复算 OOF 指标，生成聚合报告以及 PNG/SVG，并拟合一套探索性统计 GLM。历史预测模型训练保存在授权本地研究项目。

同时加载分析库和研究汇总时，程序逐文件比较冻结队列、人口与科室源表、v04 折外文件、模型结果表、校准、缺失率和分组贡献表的 SHA256。两份产物需要从同一批共同输入生成。已有完整指纹的分析库可通过 `--database` 指定。旧分析库可单独打开基础看板，合并展示前需要重建缺少指纹的产物。

[评价方法](model_evaluation.md) · [统计计划](statistical_analysis_plan.md)
