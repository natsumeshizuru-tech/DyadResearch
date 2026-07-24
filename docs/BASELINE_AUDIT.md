# DyadResearch 拆分基线审计

审计日期：2026-07-18（Asia/Shanghai）

## 源工作区保护

- 源仓库：相邻的 `../DyadTetrade` 仓库
- Git 分支：`main`
- 基线提交：`2fbb5b9d7d0555f2af4d0f62ff960334039fb2cd`
- 审计时工作区已有大量修改和未跟踪文件。本拆分不清理、不重置、不覆盖这些内容。
- 新项目：当前 `DyadResearch` 仓库。不复制源仓库，不复制约 46.24 GiB 的 SQLite 数据。

## 可复现的实测基线

- Python：3.12.10；QMT sidecar Python：3.11.9。
- Node：24.14.0；npm：11.9.0。
- `pytest -q`：281 passed。
- `ruff check`：通过。
- strict mypy：153 个源文件通过。
- 覆盖率插桩全量测试：281 passed；13,649 statements，3,050 missed，总覆盖率 78%。原始 JSON 位于源仓库 `reports/data/baseline_coverage_dyadresearch_20260718.json`。

## 数据基线

- 45 个 SQLite 数据库；总大小 49,645,076,480 bytes（46.236 GiB）。
- 所有库 `PRAGMA integrity_check=ok`；主键重复 0。
- 日线：3,290,811 行，5,528 个证券，2024-01-02 至 2026-07-17；614 个交易日，最小单日生命周期覆盖率 99.1815%。
- 分钟线：315,077,919 行。SH/SZ 从 2025-07-11 开始；BJ 从 2025-07-16 开始；截至 2026-07-17。
- 财务：1,481,070 行，2024 年 644,356、2025 年 647,635、2026 年 189,079；共 8 类表。
- 参考数据：2026-07-17 单一快照；7,049 个板块、610 个指数代码。
- 数据证据源：相邻仓库中的私有本地验证报告（不随公开仓库分发）。

## 既有实现盘点

源项目同时存在两套回测实现：

1. `dyadtetrade.modules.backtest`：包含下一 bar 成交、T+1、涨跌停、停牌、部分成交、冻结资金、佣金和滑点等较完整语义，但服务层仍通过 DuckDB/Parquet 取数，并依赖旧领域、数据库和报告模块。
2. `dyadtetrade.data.backtest`：直接使用 SQLite 和本地 XtData 兼容层，能运行 QMT 风格策略，但成交模型只有 pending/filled/rejected，不支持部分成交和下单时冻结资金。

相关研究、策略、优化与报告模块也通过 SQLAlchemy、DuckDB 或旧回测结果类型互相耦合。`dyadtetrade.data` 是最适合提炼的数据层，但不能在独立项目中反向导入它。

## 拆分决策

- 在 DyadResearch 重新实现窄而明确的只读 SQLite 端口。
- 只保留一个事件驱动回测内核；原生策略和 QMT 风格策略仅作为适配器。
- 研究元数据写入独立 `research.db`，从不写源行情库。
- Stage 6 才允许在 DyadTetrade 中增加薄兼容包装；DyadResearch 永不依赖 DyadTetrade。

## 已知风险

- 2024-01-01 至 2025-07-10 的分钟线未从本机 miniQMT/大QMT 缓存找到，不能合成或标记为完整。
- 板块和指数成分只有 2026-07-17 快照，历史时点成员查询必须拒绝。
- “包含退市证券的完整历史股票池”不能由当前快照证明。
- 当前源项目总覆盖率 78%，不能继承为新项目的质量标准；新项目目标是整体不低于 90%、核心回测不低于 95%。
