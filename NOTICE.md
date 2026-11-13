# 来源与升级范围

上游项目：[huhu-0026/medical-data-analysis-platform](https://github.com/huhu-0026/medical-data-analysis-platform)，MIT，固定参考提交 `83f89e845d80426141dec0fef755f3f684ca9c51`。本地完整版本中的 `upstream/` 是原始只读参考快照，保留原 LICENSE 与原 PBIX；公开求职包不重复包含该目录。项目没有向该远程仓库写入或推送。

本次升级在原项目的医疗数据分析思路上，重建了适配 ICU 研究队列的数据处理、SQL 分析库、独立模拟演示、交互 Web 看板、指标契约与测试。新增代码位于 app.py / icu_analytics / web / sql / tests；没有把原作者的全部作品称为自己的从零原创。

公开包仅包含新增源码、许可、文档及独立模拟数据。真实 MIMIC 原始表、个体衍生数据、预测、模型权重和真实结果快照均不在公开包中。MIT 软件许可不授予 MIMIC 数据的再分发权。

真实数据来源：[MIMIC-IV 3.1](https://physionet.org/content/mimiciv/3.1/)，DOI 10.13026/kpb9-mt58；访问及衍生资源遵循原数据协议。模型研究结论见完整复现项目 07，而非公开模拟演示指标。
