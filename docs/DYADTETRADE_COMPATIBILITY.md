# DyadTetrade 交付兼容性

当前状态：DyadResearch 与 DyadTetrade 不通过 Python 导入互相调用。研究成果只通过版本化的 `StrategyReleaseBundle` 文件契约交付；数据下载例外地通过 loopback HTTP 调用 DyadTetrade 的受控 XtData 数据面，使两个前端使用同一下载目录和共享 SQLite。Research 对行情库仍保持只读，两个进程和依赖环境保持独立。

数据控制面：

- Research 默认请求 `http://127.0.0.1:8000/api/v1/market/xtdata/*`，可用 `DYADRESEARCH_XTDATA_API` 覆盖。
- 控制面只接受 loopback 地址，不暴露 XtTrader 或报单能力。
- 原始 `1d`、`1m` 和财务/参考数据可受控导入共享库；其他 XtData 类别只下载到 MiniQMT 缓存。

默认交付路径：

- DyadResearch 导出：`reports/releases/<strategy>-<experiment>-<hash>/`
- DyadTetrade 收件箱：`data/strategy_bundles/inbox/<bundle-name>/`
- DyadTetrade 验收回执：`data/strategy_bundles/receipts/`

可用 `DYADTETRADE_STRATEGY_BUNDLE_INBOX` 覆盖交易端收件箱。复制发布包后，调用交易端 `GET /api/strategy-bundles` 查看目录，再调用 `POST /api/strategy-bundles/{bundle_name}/validate` 验证哈希、版本、数据能力、风险预算、策略白名单和证据侧文件。验证失败时交易端拒绝接纳（fail closed）。

旧的 `dyadtetrade.research_compat` Python 兼容层已移除。历史迁移回归仅可使用 `dyadtetrade.api.legacy_app`，该应用不是产品启动入口，也不得部署到交易环境。
