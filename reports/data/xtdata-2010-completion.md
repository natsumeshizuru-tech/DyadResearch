# XtData 2010+ 数据补全终验（2026-07-20 恢复后复核）

## 结论

- 最终审计：`accepted=true`；日线、财务、目录生命周期、PIT、SQLite 完整性全部通过。
- 日线：2010-01-04 至 2026-07-17，8,010 个标的，17,617,130 条，来源均为 `xtdata`。
- 全范围没有未解释的日线缺口。可审计空结果为 60 个未上市 ETF 占位合约、6 个深市统计指数、3 个退市股。
- 财务：5,813/5,813 个股票范围检查点完成，17 个年度分库共 6,981,918 条，8 张表均存在，所有 `quick_check=ok`。
- 数据质量：负价格、OHLC 关系错误、负成交量、负成交额、范围外日线、无日期财务、未来公告、坏 JSON 和未解决硬错误均为 0。
- 复权：20 个公司行动较多的代表股票 × 5 种模式，共 100 组与原生 xtdata 逐行一致；最大价格绝对误差 `5.4569682106375694e-11`，最大量额相对误差 `2.3794026206914057e-16`。

## 财务表

| 表 | 行数 | 覆盖股票数 |
|---|---:|---:|
| Balance | 279,188 | 5,753 |
| Income | 323,400 | 5,753 |
| CashFlow | 262,059 | 5,753 |
| Capital | 364,108 | 5,810 |
| HolderNum | 412,988 | 5,772 |
| PershareIndex | 264,638 | 5,761 |
| Top10FlowHolder | 2,409,452 | 5,760 |
| Top10Holder | 2,666,085 | 5,761 |

安装版 xtdata 没有独立 `PerShare` 表；每股指标由 `PershareIndex` 提供。表内没有记录的标的仍有精确范围完成检查点，表示上游在该范围内返回空结果。

## 可复现证据

- 全库审计：`reports/data/xtdata-2010-audit.json`
- 官方退市目录种子：`reports/data/official-delisted-universe-2010.json`
- 本次财务恢复日志：`reports/data/recovery/financial-stdout.log`、`reports/data/recovery/financial-stderr.log`
- 财务恢复 job id：`financial-backfill-20260720T002704-5d5b3aa8`
- 复权黄金对照：`../DyadTetrade/reports/data/adjustment_golden_20260719.json`（私有工作目录证据，不进入公开导出）
- 一键续跑：`scripts/Continue-XtData-2010-Backfill.ps1`

目录来源只用于补齐历史代码与上市生命周期；行情、复权因子和财务载荷仍来自本机迅投 xtdata。官方参考：迅投 XtData 文档、上交所终止上市清单、深交所终止上市清单。
