FACTOR = {
    "title": "20周期平均成交额",
    "description": "20-bar average traded amount",
    "expression": "mean(amount)",
    "input_fields": ["amount"],
    "lookback": 20,
    "frequency": "1d",
    "higher_is_better": True,
}
