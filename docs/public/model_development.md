# 模型开发与本地复现

时间序列为前 72 小时，25 个临床槽位形成 26 列模型输入。每折训练范围内拟合连续量的均值填补和缩放，并保留通气阳性、未知。时点前原始事件及报告时间追溯详于冻结特征方案。

| 实验 | 当前证据 |
|---|---|
| M4-LR-V03-20261112 | 每时点×五折的 20 个 L2 Logistic。四时点快照，基准主要时点 24h |
| M4-LSTM-V03-20261112 | 五个单向 LSTM。固定 16 隐藏单元、四轮训练。有效时长 mask |
| M4-CAL-V04-20261112 | 五折各自划分训练、校准、折外验证患者。每折四个 Isotonic 共 20 个映射。主要 1h 同网络 Brier 对比 |
| M4-EXPL-V06-20261112 | 13 组历史解释，外层验证抽样，训练患者为参照 |

历史分区为患者哈希 Development/Test。内部患者五折、角色隔离及 OOF 对齐已经本地核验。历史 Test 已在既往查看。当前以第 03、05、06 章作为权威模型证据，第 07 章作为正式结果表。基线副本不计为新训练。

## 授权本地复算

安装 requirements 后使用 PowerShell。将占位路径替换为本机目录，选择新的输出目录。可以使用已存在的真数据 SQLite 分析库。

```powershell
python app.py review-research --project "D:/本地完整复现项目" --output "validation/新的研究目录"
python app.py serve --mode mimic --database "D:/现有分析库/mart.sqlite" --research-dir "validation/新的研究目录" --open
```

`review-research` 对照阶段二登记的 SHA256 和保存的索引复算 OOF 指标，生成聚合报告以及 PNG/SVG，另拟合一套探索性统计 GLM。运行训练的历史代码、权重和 Test 数据未纳入此命令。输出为本地资料。

[评价方法](model_evaluation.md) · [统计计划](statistical_analysis_plan.md)
