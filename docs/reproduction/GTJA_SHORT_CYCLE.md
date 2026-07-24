# 国泰君安短周期价量 191 因子

公式账本包含 191/191 条原始表达。源表存在换行、全角标点、拼写、参数与
括号歧义；这些问题保留在 `source_expression` 与 `ambiguity_notes` 中。

三种协议：

- `paper_strict`：缺少历史行业、历史中证 500 权重和一致预期字段时停止；
- `transparent_reconstruction`：只使用命名明确的简化风格模型，并披露遗漏；
- `ashare_executable`：生成符合 A 股交易约束的长仓目标，属于可比性 D。

Alpha143 的 `SELF` 绑定 t-1 因子值。需要 MKT、SMB、HML 的条目在输入
缺失时不会静默设零。

本地数据没有 2010-2017 的历史行业/指数权重快照，因此当前不能声称
复现论文策略收益。协议报告中的 `NOT_RUN`/`partial` 是验收结论的一部分。

