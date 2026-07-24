# Reproducible research catalog

本目录包含三份小型、确定性的公开研究流水线证据。它们全部使用程序生成的 `SYNTHETIC DATA`，因此统一标记为 `EXPLORATORY_ONLY`；用途是验证研究规范、PIT/数据读取、因子计算、数据指纹、结果哈希和报告构建，不是验证论文中的实证收益。

```powershell
dyadresearch demo generate-data
dyadresearch reproduce list
dyadresearch reproduce run reproductions/specs/momentum.yaml
dyadresearch reproduce run reproductions/specs/low-volatility.yaml
dyadresearch reproduce run reproductions/specs/low-turnover.yaml
```

每份 YAML 都保留论文题目、作者、年份、DOI、方法差异和限制。每次运行生成 `report.html`、`report.json` 与 `metrics.csv`；相同 spec 与相同数据指纹产生相同结果哈希。

安全规则：合成数据不能声明为 `EXACT_REPRODUCTION`；runner 会直接拒绝这种配置。
