# 测试策略

- 单元测试：金额、费用、订单状态机、PIT、分片选择、聚合与指标。
- 属性测试：现金/持仓守恒、随机成交序列、调整前后可逆性和结果确定性。
- 契约测试：真实 SQLite schema、只读拒写、字段与排序。
- Golden/Parity：固定数据上的原生/QMT 适配器同结果；与两套旧实现记录可解释差异。
- 集成测试：只读查询由 `DYADRESEARCH_DATA_ROOT` 指定的私有 SQLite 数据根目录。
- 性能测试：分片裁剪、查询行数和小型回测预算。
- Mutation：优先覆盖回测撮合、T+1、PIT 和费用判断。

CI 门槛：全项目 line coverage 不低于 90%；`dyadresearch.backtest` 不低于 95%；Ruff 和 strict mypy 必须通过。不得通过 exclude、pragma 或降低阈值掩盖缺口。

测试集包含真实 SQLite 集成、原生/QMT parity、固定结果哈希 Golden、Hypothesis 随机价格路径和交互式查询性能预算。最新数量与覆盖率只从自动生成的基线文件读取，不在本文手写。

高风险变异目标是 `backtest/broker.py`、`backtest/fees.py`、`data/financial.py` 的边界条件；这些判断均有针对性 sentinel 测试（下一 bar、T+1、整手、资金冻结、涨跌停、公告版本整份替换），后续可接入 mutmut 批量执行。
