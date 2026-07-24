# 大 QMT ContextInfo 部署

交付代码在 `qmt_big/`。盘后研究生成次日目标权重 CSV，大 QMT 脚本只做
校验、订单规划和可选执行。

关键安全设置：

- `ENABLE_LIVE_TRADING = False`；
- 账号为空；
- `QUICK_TRADE = 0`，脚本拒绝 2；
- 目标日期、哈希、权重和、白名单、持仓数、单票权重、换手与金额均校验；
- 先卖后买，买入按 100 股取整，T+1 不可卖数量明确写入计划；
- `strategyName` 和 `userOrderId` 防止重复提交；
- 普通委托与 TWAP/VWAP 需要在用户安装的实际大 QMT 版本中复核 API 签名。

本仓库测试只调用纯订单规划函数，不读取真实账户、不连接 QMT、不发送委托。

