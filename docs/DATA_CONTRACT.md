# 数据契约

所有行情、目录和财务库使用 SQLite URI `file:///...?...mode=ro` 打开。连接建立后设置 `PRAGMA query_only=ON`。查询层不执行迁移、建表、WAL checkpoint、VACUUM 或任何 DML。

原始 bar 主键为 `(symbol, ts)`；核心字段是 `symbol, ts, trade_date, open, high, low, close, volume, amount, settlement_price, open_interest, pre_close, suspend_flag, source, ingested_at, source_hash`。

## 分片规则

- 日线：`bars_1d.db`。
- 分钟线：`bars_1m_{SH|SZ|BJ}_{YYYYMM}.db`，查询必须按证券市场和月份裁剪。
- 财务：`fundamentals_{YYYY}.db`，跨年查询需要合并分片。
- 目录与公司行动：`catalog.db`。

所有输出按 `(ts, symbol)` 稳定排序并去重；缺失分片不会静默等同于空行情，而是记录 capability warning，严格模式可直接拒绝。

输入 manifest 至少包含配置规范化 JSON、实际数据库路径/大小/mtime、查询范围、字段、证券列表、调整方式、行数和内容 SHA-256。相同 manifest 与随机种子必须产生相同结果 hash。
