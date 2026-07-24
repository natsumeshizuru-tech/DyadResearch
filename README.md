# DyadResearch

给 MiniQMT 配套的 A 股本地研究台。

MiniQMT 提供行情和基础数据，DyadResearch 负责把这些数据变成因子、策略、回测和研究报告。它不连接资金账户，也不提供委托、撤单或 `XtTrader` 能力；需要运行 Paper 或 QMT 策略时，由 [DyadTetrade](https://github.com/natsumeshizuru-tech/DyadTetrade) 接手。

## 能做什么

| 模块 | 用途 |
| --- | --- |
| 行情与数据 | 查看 SQLite 数据覆盖；通过本机 DyadTetrade 调用 XtData 下载历史、财务、板块、合约、节假日、可转债、ETF 和指数权重 |
| 因子 | 新建、编辑和运行因子；计算 IC、RankIC，保存参数与结果哈希 |
| 策略 | 新建策略、生成工作区文件，并直接用 VS Code 打开 |
| 回测 | 事件驱动撮合，处理下一 Bar 成交、T+1、涨跌停、停牌、费用、复权和公司行动 |
| 实验 | 保存、比较和复现实验，导出 HTML、JSON 与 CSV 报告 |
| 发布 | 生成带 Schema 和 SHA-256 校验的 `StrategyReleaseBundle`，交给 DyadTetrade 验收 |

## 和 DyadTetrade 怎么配合

```text
MiniQMT / XtData
        │
        ▼
DyadTetrade  ── 下载、导入、维护共享 SQLite
        │
        ▼ 只读
DyadResearch ── 因子、策略、回测、报告
        │
        ▼ StrategyReleaseBundle
DyadTetrade  ── Paper / qmt_sim / 受控实盘
```

两个项目各管一段边界：

- DyadResearch 只做研究，读取历史数据，不碰账户和订单。
- DyadTetrade 管 MiniQMT 接入、实时行情、数据写入、OMS、风控和执行。
- 两端不互相导入 Python 包；数据控制走本机 HTTP，策略交付走版本化发布包。

## 快速开始

下面的命令会生成一套合成数据，不需要安装 MiniQMT。

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[research,web,dev]"
.venv\Scripts\dyadresearch demo generate-data
.venv\Scripts\dyadresearch doctor
.venv\Scripts\dyadresearch-web
```

启动前端：

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm run dev
```

常用命令：

```powershell
.venv\Scripts\dyadresearch factor run --name momentum_20 --symbols 000001.SZ --period 1d --start 20240102 --end 20240325
.venv\Scripts\dyadresearch backtest run --strategy buy_and_hold --symbols 000001.SZ --period 1d --start 20240102 --end 20240325
.venv\Scripts\dyadresearch reproduce run reproductions/specs/momentum.yaml
```

## 使用 MiniQMT 数据

1. 先启动并登录 MiniQMT。
2. 在 DyadTetrade 中配置 XtData 和共享 SQLite，启动数据控制面。
3. 将 `config/research.example.yaml` 复制为 `config/research.yaml`，确认数据目录指向同一套 SQLite。
4. 在“行情与数据”页面检查覆盖率，再下载或导入需要的数据。

`config/research.yaml` 属于本机配置，已被 Git 忽略。公开仓库不包含 QMT 缓存、券商 SDK、账户信息或授权行情数据库。

## 研究约束

- 行情库按只读方式打开，研究过程不会改写源数据。
- 财务数据按公告时点可见，缺少历史快照时会明确报错。
- 成交默认发生在下一根可交易 Bar，费用和交易规则进入实际计算。
- 每次运行保存配置、数据指纹、结果哈希和环境信息。
- 仓库内演示数据由固定规则生成，不拿当前数据冒充历史数据。

已知数据边界见 [KNOWN_DATA_LIMITATIONS.md](docs/KNOWN_DATA_LIMITATIONS.md)，回测规则见 [BACKTEST_SEMANTICS.md](docs/BACKTEST_SEMANTICS.md)。

## 开发检查

```powershell
.venv\Scripts\python -m ruff check src tests
.venv\Scripts\python -m ruff format --check src tests
.venv\Scripts\python -m mypy -p dyadresearch
.venv\Scripts\python -m pytest

cd frontend
pnpm run test
pnpm run lint
pnpm run build
```

架构和数据约定见 [ARCHITECTURE.md](docs/ARCHITECTURE.md)、[DATA_CONTRACT.md](docs/DATA_CONTRACT.md) 与 [POINT_IN_TIME_POLICY.md](docs/POINT_IN_TIME_POLICY.md)。许可证和安全说明见 [DEPENDENCY_LICENSES.md](DEPENDENCY_LICENSES.md)、[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [SECURITY.md](SECURITY.md)。
