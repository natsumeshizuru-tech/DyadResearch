STRATEGY = {
    "type": "low_volume_ratio_momentum",
    "title": "低量比动量策略",
    "description": (
        "沪深主板、市值小于300亿元; 涨幅超过7%且5日实时量比低于0.6时触发, "
        "下一分钟开盘未涨停则买入20%总仓位, 最多持有5只, 次日开盘全仓卖出。"
    ),
    "parameters": {
        "market_cap_max": 30000000000,
        "rise_threshold": 0.07,
        "volume_ratio_max": 0.60,
        "volume_lookback_days": 5,
        "allocation_ratio": 0.20,
        "max_positions": 5,
    },
}
