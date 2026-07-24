# 迁移映射

| 源能力 | DyadResearch 目标 | 处理方式 |
|---|---|---|
| `dyadtetrade.data.sqlite.*` | `dyadresearch.data.*` | 根据已验证 schema 独立实现只读查询，不反向导入 |
| `dyadtetrade.data.adjustments` | `dyadresearch.data.adjustments` | 保留 PIT 调整原则，增加能力拒绝 |
| 两套 backtest | `dyadresearch.backtest` | 合并为单内核；适配器不拥有成交逻辑 |
| `modules.strategy` | `dyadresearch.strategy` | 提炼最小 SDK，去除执行/账户依赖 |
| `modules.research` | `dyadresearch.factors` | FactorSpec、注册表、评估器和实验持久化 |
| `modules.optimization` | `dyadresearch.experiments` | 确定性网格、walk-forward、Monte Carlo |
| `modules.reporting` | `dyadresearch.reporting` | 静态 HTML/JSON/CSV，不依赖旧结果类型 |
| DyadTetrade 调用方 | `StrategyReleaseBundle` | 只允许带校验回执的文件契约，不允许 Python/API 反向依赖 |

明确不迁移：账户管理、OMS、纸面/实盘交易、行情订阅、XtTrader、Web 前端和 46 GiB 数据文件。
