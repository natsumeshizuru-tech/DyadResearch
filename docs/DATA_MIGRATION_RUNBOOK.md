# SQLite 物理迁移与回滚

迁移日期：2026-07-18。

## 当前布局

- 主数据根目录：`./data/sqlite`
- 只读回滚副本：`../DyadTetrade/data/sqlite`
- DyadResearch 配置：`config/research.yaml`
- EOD 写入配置：`../DyadTetrade/config/market_data.yaml`

新旧目录包含相同的 45 个数据库。切换时的数据库文件总大小为
49,645,150,208 bytes。逐文件 SHA-256、`PRAGMA integrity_check`、表行数、日期边界和
主键重复结果位于 `reports/migration/physical_data_validation_20260718.json`。

## 切换流程

1. 禁用计划任务 `DyadTetrade Market Data EOD`。
2. 确认没有 Python 数据写入进程。
3. 对 45 个数据库执行 `PRAGMA wal_checkpoint(TRUNCATE)`。
4. 使用保留时间戳的安全复制建立新根目录。
5. 完成全量校验后，才更新两侧配置。
6. 用新根目录运行 doctor、真实日线/分钟/PIT 查询和测试。
7. 将计划任务动作固定到显式配置文件后重新启用。

## 回滚

若新根目录发生异常：

1. 立即禁用 EOD 计划任务。
2. 将 `config/research.yaml` 和 DyadTetrade 的 `config/market_data.yaml` 中 `storage.root`
   恢复为相邻仓库的 `../DyadTetrade/data/sqlite`。
3. 运行 `dyadresearch doctor` 和日线烟雾查询。
4. 校验通过后重新启用计划任务。

旧目录在完成至少一个 EOD 周期和人工验收前不得删除。`dyadtetrade.db` 仍是旧应用业务库；
DyadResearch 不读取该库，旧应用的 `DYADTETRADE_SQLITE_URL` 也继续指向旧目录，避免研究数据
迁移影响交易工作台业务状态。
