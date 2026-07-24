# Factor Atlas

The atlas compares normalized structural fingerprints, input dependencies,
lookback, delay and implementation status. It does not publish backtest
performance for protocols that did not run.

## Summary

| Paper | Records | Status counts |
| --- | ---: | --- |
| worldquant101 | 101 | normalized=15, unavailable_dependency=18, not_implemented=68 |
| gtja_short_cycle | 191 | normalized=28, unavailable_dependency=1, not_implemented=162 |

## Formula records

| Paper | Factor | Status | Family | Fields | History | Delay | Page | Fingerprint |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| worldquant101 | alpha001 | not_implemented | volatility | close, returns | 20 | 1 | 8 | `d2274c33df8b8046` |
| worldquant101 | alpha002 | normalized | correlation | open, close, volume | 6 | 1 | 8 | `768618923487cfcf` |
| worldquant101 | alpha003 | normalized | correlation | open, volume | 10 | 1 | 8 | `85a1f49b60c67fd9` |
| worldquant101 | alpha004 | normalized | position | low | 9 | 1 | 8 | `f8d396202fb0a752` |
| worldquant101 | alpha005 | normalized | open_gap_or_intraday | open, close, vwap | 10 | 1 | 8 | `cc5f03b549d307c8` |
| worldquant101 | alpha006 | normalized | correlation | open, volume | 10 | 1 | 8 | `585b92af7f166aa8` |
| worldquant101 | alpha007 | not_implemented | liquidity_or_volume | close, volume | 60 | 1 | 8 | `4506aabe47f479de` |
| worldquant101 | alpha008 | not_implemented | momentum_or_reversal | open, returns | 10 | 1 | 9 | `09a28cdd374d3d0d` |
| worldquant101 | alpha009 | not_implemented | momentum_or_reversal | close | 5 | 1 | 9 | `bdf3dc946916b2d7` |
| worldquant101 | alpha010 | not_implemented | momentum_or_reversal | close | 4 | 1 | 9 | `7f918e9fe5d8abeb` |
| worldquant101 | alpha011 | not_implemented | liquidity_or_volume | close, volume, vwap | 3 | 1 | 9 | `6b019b2200c60e23` |
| worldquant101 | alpha012 | normalized | liquidity_or_volume | close, volume | 1 | 1 | 9 | `c3ad34b05967d806` |
| worldquant101 | alpha013 | normalized | correlation | close, volume | 5 | 1 | 9 | `7f4820deba4b18a6` |
| worldquant101 | alpha014 | not_implemented | correlation | open, volume, returns | 10 | 1 | 9 | `052e405bf71e6651` |
| worldquant101 | alpha015 | normalized | correlation | high, volume | 3 | 1 | 9 | `742b8451987f68e1` |
| worldquant101 | alpha016 | not_implemented | correlation | high, volume | 5 | 1 | 9 | `60a934d0b25a9c5f` |
| worldquant101 | alpha017 | not_implemented | liquidity_or_volume | close, volume | 10 | 1 | 9 | `395d4d4a3b4d597e` |
| worldquant101 | alpha018 | normalized | correlation | open, close | 10 | 1 | 9 | `22d6c4e22884365d` |
| worldquant101 | alpha019 | not_implemented | momentum_or_reversal | close, returns | 250 | 1 | 9 | `589a84c123d29be6` |
| worldquant101 | alpha020 | normalized | open_gap_or_intraday | open, high, low, close | 1 | 1 | 9 | `a49fee8084bd70ed` |
| worldquant101 | alpha021 | not_implemented | volatility | close, volume | 8 | 1 | 9 | `4e4e407b1d5a3466` |
| worldquant101 | alpha022 | not_implemented | correlation | high, close, volume | 20 | 1 | 9 | `8c0368af9d0f4172` |
| worldquant101 | alpha023 | not_implemented | momentum_or_reversal | high | 20 | 1 | 9 | `5a712a40793cc4f2` |
| worldquant101 | alpha024 | not_implemented | momentum_or_reversal | close | 100 | 1 | 9 | `cb6a801df5b8db2b` |
| worldquant101 | alpha025 | not_implemented | liquidity_or_volume | high, close, vwap, returns | 1 | 1 | 10 | `357142b46f7cc854` |
| worldquant101 | alpha026 | not_implemented | correlation | high, volume | 5 | 1 | 10 | `ae6143df64e06733` |
| worldquant101 | alpha027 | not_implemented | correlation | volume, vwap | 6 | 1 | 10 | `8c2bb745942b69f0` |
| worldquant101 | alpha028 | not_implemented | correlation | high, low, close | 5 | 1 | 10 | `38acfe031a610098` |
| worldquant101 | alpha029 | not_implemented | momentum_or_reversal | close, returns | 6 | 1 | 10 | `25e5b8f984f9bdb5` |
| worldquant101 | alpha030 | not_implemented | liquidity_or_volume | close, volume | 20 | 1 | 10 | `0413cb4c8227aef9` |
| worldquant101 | alpha031 | not_implemented | correlation | low, close | 12 | 1 | 10 | `1c9010fba7caab40` |
| worldquant101 | alpha032 | not_implemented | correlation | close, vwap | 230 | 1 | 10 | `e5787c42a94b1d89` |
| worldquant101 | alpha033 | not_implemented | open_gap_or_intraday | open, close | 1 | 1 | 10 | `3528eae52516685f` |
| worldquant101 | alpha034 | not_implemented | volatility | close, returns | 5 | 1 | 10 | `83194edd75ab0bac` |
| worldquant101 | alpha035 | not_implemented | liquidity_or_volume | high, low, close, volume, returns | 32 | 1 | 10 | `c3e471e84c0b4a4e` |
| worldquant101 | alpha036 | not_implemented | correlation | open, close, volume, vwap, returns | 200 | 1 | 10 | `b35c7a217d097ec5` |
| worldquant101 | alpha037 | normalized | correlation | open, close | 200 | 1 | 10 | `e2f9d35761db6f6d` |
| worldquant101 | alpha038 | not_implemented | open_gap_or_intraday | open, close | 10 | 1 | 10 | `4f349248e853e38b` |
| worldquant101 | alpha039 | not_implemented | liquidity_or_volume | close, volume, returns | 250 | 1 | 10 | `e63f921598326934` |
| worldquant101 | alpha040 | not_implemented | correlation | high, volume | 10 | 1 | 10 | `cf397d797de1aa40` |
| worldquant101 | alpha041 | not_implemented | other | high, low, vwap | 1 | 1 | 10 | `ad80c72041834281` |
| worldquant101 | alpha042 | normalized | position | close, vwap | 1 | 0 | 10 | `fbd26ab0994ff247` |
| worldquant101 | alpha043 | not_implemented | liquidity_or_volume | close, volume | 20 | 1 | 10 | `a5edcfed278c9e6e` |
| worldquant101 | alpha044 | not_implemented | correlation | high, volume | 5 | 1 | 11 | `5ba50243e41d217e` |
| worldquant101 | alpha045 | not_implemented | correlation | close, volume | 20 | 1 | 11 | `61a371bd14bce825` |
| worldquant101 | alpha046 | not_implemented | momentum_or_reversal | close | 20 | 1 | 11 | `411b8fd35ac0934d` |
| worldquant101 | alpha047 | not_implemented | liquidity_or_volume | high, close, volume, vwap | 5 | 1 | 11 | `3ea6c8b08613f5b9` |
| worldquant101 | alpha048 | unavailable_dependency | correlation | close | 250 | 0 | 11 | `f76b0857c47a7cfd` |
| worldquant101 | alpha049 | not_implemented | momentum_or_reversal | close | 20 | 1 | 11 | `fdbf14b381164c66` |
| worldquant101 | alpha050 | not_implemented | correlation | volume, vwap | 5 | 1 | 11 | `48a0b2dcc839c6ea` |
| worldquant101 | alpha051 | not_implemented | momentum_or_reversal | close | 20 | 1 | 11 | `ce1565cc82ed4443` |
| worldquant101 | alpha052 | not_implemented | liquidity_or_volume | low, volume, returns | 240 | 1 | 11 | `8ced86cdf6240d9f` |
| worldquant101 | alpha053 | not_implemented | momentum_or_reversal | high, low, close | 9 | 0 | 11 | `85951e3e96f285eb` |
| worldquant101 | alpha054 | normalized | open_gap_or_intraday | open, high, low, close | 5 | 0 | 11 | `ac57c90727794965` |
| worldquant101 | alpha055 | not_implemented | correlation | high, low, close, volume | 12 | 1 | 11 | `a27069adedd02afe` |
| worldquant101 | alpha056 | not_implemented | momentum_or_reversal | returns, cap | 10 | 1 | 11 | `cbac00f1c3d6c488` |
| worldquant101 | alpha057 | not_implemented | position | close, vwap | 30 | 1 | 11 | `016d0a182260f058` |
| worldquant101 | alpha058 | unavailable_dependency | correlation | volume, vwap | 7 | 1 | 11 | `05027088b4b617dc` |
| worldquant101 | alpha059 | unavailable_dependency | correlation | volume, vwap | 16 | 1 | 11 | `5a0b96822f58ef90` |
| worldquant101 | alpha060 | not_implemented | volatility | high, low, close, volume | 10 | 1 | 11 | `eb81ed77f3097346` |
| worldquant101 | alpha061 | not_implemented | correlation | vwap | 80 | 1 | 12 | `54da1c3173d67a66` |
| worldquant101 | alpha062 | not_implemented | correlation | open, high, low, vwap | 22 | 1 | 12 | `68ae7d12e9a503f3` |
| worldquant101 | alpha063 | unavailable_dependency | correlation | open, close, vwap | 80 | 1 | 12 | `30b0094a9a5a284a` |
| worldquant101 | alpha064 | not_implemented | correlation | open, high, low, vwap | 20 | 1 | 12 | `a0f1b4ae82f06f47` |
| worldquant101 | alpha065 | normalized | correlation | open, vwap | 13 | 1 | 12 | `3a173e6f43735641` |
| worldquant101 | alpha066 | not_implemented | momentum_or_reversal | open, high, low, vwap | 11 | 1 | 12 | `d6fbeda05ee474a1` |
| worldquant101 | alpha067 | unavailable_dependency | correlation | high, vwap | 6 | 1 | 12 | `ec5f0d3db0c4324c` |
| worldquant101 | alpha068 | not_implemented | correlation | high, low, close | 13 | 1 | 12 | `c95b645798043fec` |
| worldquant101 | alpha069 | unavailable_dependency | correlation | close, vwap | 9 | 1 | 12 | `3348d67746e92c99` |
| worldquant101 | alpha070 | unavailable_dependency | correlation | close, vwap | 17 | 1 | 12 | `52b245aae6325a11` |
| worldquant101 | alpha071 | not_implemented | correlation | open, low, close, vwap | 80 | 1 | 12 | `70ac28dd8f611f5a` |
| worldquant101 | alpha072 | not_implemented | correlation | high, low, volume, vwap | 18 | 1 | 12 | `8fd4adf4c41c1581` |
| worldquant101 | alpha073 | not_implemented | momentum_or_reversal | open, low, vwap | 16 | 1 | 12 | `c3b842c8d61dc7e6` |
| worldquant101 | alpha074 | not_implemented | correlation | high, close, volume, vwap | 37 | 1 | 13 | `1f8a02d27adf8054` |
| worldquant101 | alpha075 | not_implemented | correlation | low, volume, vwap | 12 | 1 | 13 | `0ee0329ebf097b59` |
| worldquant101 | alpha076 | unavailable_dependency | correlation | low, vwap | 19 | 1 | 13 | `ccad7bc229e5004c` |
| worldquant101 | alpha077 | not_implemented | correlation | high, low, vwap | 20 | 1 | 13 | `71b6d1a92e6ae314` |
| worldquant101 | alpha078 | not_implemented | correlation | low, volume, vwap | 19 | 1 | 13 | `883b092dcbfb2aac` |
| worldquant101 | alpha079 | unavailable_dependency | correlation | open, close, vwap | 50 | 1 | 13 | `c16f83c7f2640e2b` |
| worldquant101 | alpha080 | unavailable_dependency | correlation | open, high | 5 | 1 | 13 | `d4c02b75aceed2dd` |
| worldquant101 | alpha081 | not_implemented | correlation | volume, vwap | 49 | 1 | 13 | `19a0fcd484f77075` |
| worldquant101 | alpha082 | unavailable_dependency | correlation | open, volume | 17 | 1 | 13 | `b998bd087d86bc82` |
| worldquant101 | alpha083 | not_implemented | volatility | high, low, close, volume, vwap | 5 | 1 | 13 | `75f5a64674e3a439` |
| worldquant101 | alpha084 | not_implemented | momentum_or_reversal | close, vwap | 20 | 1 | 13 | `c42cd2a0ccafb03a` |
| worldquant101 | alpha085 | not_implemented | correlation | high, low, close, volume | 10 | 1 | 13 | `838bdb38455be532` |
| worldquant101 | alpha086 | not_implemented | correlation | open, close, vwap | 20 | 1 | 13 | `aa7defafffaf2be3` |
| worldquant101 | alpha087 | unavailable_dependency | correlation | close, vwap | 14 | 1 | 14 | `2156330b462b7ce1` |
| worldquant101 | alpha088 | not_implemented | correlation | open, high, low, close | 20 | 1 | 14 | `a87da9eb26032d00` |
| worldquant101 | alpha089 | unavailable_dependency | correlation | low, vwap | 15 | 1 | 14 | `622f293e5b0430d3` |
| worldquant101 | alpha090 | unavailable_dependency | correlation | low, close | 5 | 1 | 14 | `9439f5715f36bdd7` |
| worldquant101 | alpha091 | unavailable_dependency | correlation | close, volume, vwap | 16 | 1 | 14 | `7799d4d83066a152` |
| worldquant101 | alpha092 | not_implemented | correlation | open, high, low, close | 18 | 1 | 14 | `41cd1d0ab54d45b9` |
| worldquant101 | alpha093 | unavailable_dependency | correlation | close, vwap | 19 | 1 | 14 | `5499b8f8a274a2f9` |
| worldquant101 | alpha094 | not_implemented | correlation | vwap | 19 | 1 | 14 | `c13d38c43aaf5252` |
| worldquant101 | alpha095 | not_implemented | correlation | open, high, low | 19 | 1 | 14 | `24a15db85980930b` |
| worldquant101 | alpha096 | not_implemented | correlation | close, volume, vwap | 14 | 1 | 14 | `a015c5da0f217e1c` |
| worldquant101 | alpha097 | unavailable_dependency | correlation | low, vwap | 20 | 1 | 14 | `649c0ad52fa31ae5` |
| worldquant101 | alpha098 | not_implemented | correlation | open, vwap | 26 | 1 | 15 | `8bda71b4ee7fc961` |
| worldquant101 | alpha099 | not_implemented | correlation | high, low, volume | 19 | 1 | 15 | `80626a900d6bdb62` |
| worldquant101 | alpha100 | unavailable_dependency | correlation | high, low, close, volume | 30 | 1 | 15 | `126f632caa0bace0` |
| worldquant101 | alpha101 | normalized | volatility | open, high, low, close | 1 | 1 | 15 | `eef27dd7a1306ff8` |
| gtja_short_cycle | alpha001 | normalized | correlation | open, close, volume | 6 | 1 | 11 | `1689a5e4441dba73` |
| gtja_short_cycle | alpha002 | normalized | volatility | high, low, close | 1 | 1 | 11 | `d1ab8334e1f66554` |
| gtja_short_cycle | alpha003 | not_implemented | momentum_or_reversal | high, low, close | 6 | 1 | 11 | `50bcfa25eb832ad9` |
| gtja_short_cycle | alpha004 | not_implemented | volatility | close, volume | 20 | 1 | 11 | `f21779c85e75ad19` |
| gtja_short_cycle | alpha005 | not_implemented | correlation | high, volume | 5 | 1 | 11 | `a54874ee213bd833` |
| gtja_short_cycle | alpha006 | normalized | momentum_or_reversal | open, high | 4 | 1 | 11 | `899dfc42b9b808c5` |
| gtja_short_cycle | alpha007 | not_implemented | liquidity_or_volume | close, volume, vwap | 3 | 1 | 11 | `806e470aa049ecd5` |
| gtja_short_cycle | alpha008 | normalized | momentum_or_reversal | high, low, vwap | 4 | 1 | 11 | `f824968695f4d5e7` |
| gtja_short_cycle | alpha009 | normalized | volatility | high, low, volume | 7 | 1 | 11 | `de57ca9d6f02d458` |
| gtja_short_cycle | alpha010 | not_implemented | volatility | close | 20 | 1 | 11 | `3ec0289900fde0c2` |
| gtja_short_cycle | alpha011 | not_implemented | volatility | high, low, close, volume | 6 | 1 | 11 | `3cdcbc41d5f69661` |
| gtja_short_cycle | alpha012 | not_implemented | open_gap_or_intraday | open, close, vwap | 10 | 1 | 11 | `21c9c7b7c7135411` |
| gtja_short_cycle | alpha013 | normalized | other | high, low, vwap | 1 | 1 | 11 | `4cb02a7c4f64e072` |
| gtja_short_cycle | alpha014 | normalized | momentum_or_reversal | close | 5 | 1 | 11 | `28d609c02746d3d4` |
| gtja_short_cycle | alpha015 | normalized | open_gap_or_intraday | open, close | 1 | 1 | 11 | `d92e1d106d03606d` |
| gtja_short_cycle | alpha016 | not_implemented | correlation | volume, vwap | 5 | 1 | 11 | `e3ed7c568eed3aab` |
| gtja_short_cycle | alpha017 | not_implemented | momentum_or_reversal | close, vwap | 15 | 1 | 11 | `0da50e9c1ecdd252` |
| gtja_short_cycle | alpha018 | normalized | momentum_or_reversal | close | 5 | 1 | 11 | `3a7792d5c083da5b` |
| gtja_short_cycle | alpha019 | not_implemented | momentum_or_reversal | close | 5 | 1 | 11 | `5d15f14fcae5e713` |
| gtja_short_cycle | alpha020 | normalized | momentum_or_reversal | close | 100 | 1 | 11 | `ba68710d2e4747e0` |
| gtja_short_cycle | alpha021 | not_implemented | other | close | 6 | 1 | 11 | `6eb349d956794b24` |
| gtja_short_cycle | alpha022 | not_implemented | momentum_or_reversal | close | 12 | 1 | 11 | `857bd5f58dce14bb` |
| gtja_short_cycle | alpha023 | not_implemented | volatility | close | 100 | 1 | 11 | `514b87e542527e6a` |
| gtja_short_cycle | alpha024 | not_implemented | momentum_or_reversal | close | 5 | 1 | 11 | `1af3eae0fd390dd8` |
| gtja_short_cycle | alpha025 | not_implemented | liquidity_or_volume | close, volume | 250 | 1 | 11 | `f7bcbd1d4deea7e2` |
| gtja_short_cycle | alpha026 | not_implemented | correlation | close, vwap | 230 | 1 | 11 | `d7ec8f6330023d67` |
| gtja_short_cycle | alpha027 | not_implemented | momentum_or_reversal | close | 100 | 1 | 11 | `c1bf6e2f72b2a472` |
| gtja_short_cycle | alpha028 | not_implemented | other | high, low, close | 100 | 1 | 11 | `a119c8bb834d586c` |
| gtja_short_cycle | alpha029 | not_implemented | liquidity_or_volume | close, volume | 6 | 1 | 11 | `e46bf9e5d3983fe9` |
| gtja_short_cycle | alpha030 | unavailable_dependency | momentum_or_reversal | close, mkt, smb, hml | 60 | 1 | 11 | `41bd49b2864b2da4` |
| gtja_short_cycle | alpha031 | normalized | other | close | 100 | 1 | 11 | `1662b3d752cc81ad` |
| gtja_short_cycle | alpha032 | not_implemented | correlation | high, volume | 3 | 1 | 11 | `aef2bffccda2e523` |
| gtja_short_cycle | alpha033 | not_implemented | liquidity_or_volume | low, volume | 240 | 1 | 11 | `de5ac56c80b9591d` |
| gtja_short_cycle | alpha034 | normalized | other | close | 12 | 1 | 11 | `15857fc3c178db2e` |
| gtja_short_cycle | alpha035 | not_implemented | correlation | open, volume | 17 | 1 | 11 | `2bc5edf2f762bf9f` |
| gtja_short_cycle | alpha036 | not_implemented | correlation | volume, vwap | 6 | 1 | 12 | `cf422f76f8016338` |
| gtja_short_cycle | alpha037 | not_implemented | momentum_or_reversal | open | 10 | 1 | 12 | `9588547ddd54bed8` |
| gtja_short_cycle | alpha038 | not_implemented | momentum_or_reversal | high | 20 | 1 | 12 | `5a712a40793cc4f2` |
| gtja_short_cycle | alpha039 | not_implemented | correlation | open, close, volume, vwap | 180 | 1 | 12 | `155c50e65e5427e3` |
| gtja_short_cycle | alpha040 | not_implemented | liquidity_or_volume | close, volume | 100 | 1 | 12 | `7964ee91ce712fba` |
| gtja_short_cycle | alpha041 | not_implemented | momentum_or_reversal | vwap | 5 | 1 | 12 | `d172fd2e42a61200` |
| gtja_short_cycle | alpha042 | not_implemented | correlation | high, volume | 10 | 1 | 12 | `930b43db6c7bb191` |
| gtja_short_cycle | alpha043 | not_implemented | liquidity_or_volume | close, volume | 6 | 1 | 12 | `3ab11ac09517a2e2` |
| gtja_short_cycle | alpha044 | not_implemented | correlation | low, volume, vwap | 15 | 1 | 12 | `769cfbdb00acbef0` |
| gtja_short_cycle | alpha045 | not_implemented | correlation | open, close, volume, vwap | 150 | 1 | 12 | `b7a538ca6823ad83` |
| gtja_short_cycle | alpha046 | not_implemented | other | close | 24 | 1 | 12 | `1a9e092bb5804747` |
| gtja_short_cycle | alpha047 | not_implemented | other | high, low, close | 100 | 1 | 12 | `661319413aadcd0e` |
| gtja_short_cycle | alpha048 | not_implemented | liquidity_or_volume | close, volume | 20 | 1 | 12 | `18d26f2a477f3c9c` |
| gtja_short_cycle | alpha049 | not_implemented | momentum_or_reversal | high, low | 12 | 1 | 12 | `bdd8b2aa4a947bfb` |
| gtja_short_cycle | alpha050 | not_implemented | momentum_or_reversal | high, low | 12 | 1 | 12 | `e1fe852641bf39c3` |
| gtja_short_cycle | alpha051 | not_implemented | momentum_or_reversal | high, low | 12 | 1 | 12 | `6e472feb3d42497e` |
| gtja_short_cycle | alpha052 | not_implemented | momentum_or_reversal | high, low, close | 100 | 1 | 12 | `261e57aad0962f2b` |
| gtja_short_cycle | alpha053 | normalized | momentum_or_reversal | close | 100 | 1 | 12 | `1e7b97d96d15b6fd` |
| gtja_short_cycle | alpha054 | not_implemented | correlation | open, close | 10 | 1 | 12 | `430e5e70165f6e51` |
| gtja_short_cycle | alpha055 | not_implemented | open_gap_or_intraday | open, high, low, close | 20 | 1 | 12 | `41d07deaa80c96e5` |
| gtja_short_cycle | alpha056 | not_implemented | correlation | open, high, low, volume | 40 | 1 | 12 | `43c181a3af65170c` |
| gtja_short_cycle | alpha057 | not_implemented | other | high, low, close | 100 | 1 | 12 | `a72b7c6b91b89ed2` |
| gtja_short_cycle | alpha058 | normalized | momentum_or_reversal | close | 100 | 1 | 12 | `091816c208863d78` |
| gtja_short_cycle | alpha059 | not_implemented | momentum_or_reversal | high, low, close | 20 | 1 | 13 | `587325fa7425d5b9` |
| gtja_short_cycle | alpha060 | not_implemented | volatility | high, low, close, volume | 20 | 1 | 13 | `7d077a169c4452dc` |
| gtja_short_cycle | alpha061 | not_implemented | correlation | low, volume, vwap | 80 | 1 | 13 | `6a0ea8b70b1d7776` |
| gtja_short_cycle | alpha062 | not_implemented | correlation | high, volume | 5 | 1 | 13 | `2af4c4fa1232e82b` |
| gtja_short_cycle | alpha063 | not_implemented | momentum_or_reversal | close | 100 | 1 | 13 | `f2bdd94031ee67ee` |
| gtja_short_cycle | alpha064 | not_implemented | correlation | close, volume, vwap | 60 | 1 | 13 | `1834199c06fa934d` |
| gtja_short_cycle | alpha065 | normalized | other | close | 6 | 1 | 13 | `2f676b2b1039285c` |
| gtja_short_cycle | alpha066 | normalized | other | close | 100 | 1 | 13 | `dc2e173ab772878d` |
| gtja_short_cycle | alpha067 | not_implemented | momentum_or_reversal | close | 100 | 1 | 13 | `3d57ea98c0080890` |
| gtja_short_cycle | alpha068 | not_implemented | volatility | high, low, volume | 15 | 1 | 13 | `cd26f5a610eb4894` |
| gtja_short_cycle | alpha069 | not_implemented | other | - | 20 | 1 | 13 | `597b676b5ffaaf76` |
| gtja_short_cycle | alpha070 | normalized | volatility | amount | 6 | 1 | 13 | `cec1a749d1228e4f` |
| gtja_short_cycle | alpha071 | normalized | other | close | 100 | 1 | 13 | `5bcd75b48c5bc0c5` |
| gtja_short_cycle | alpha072 | not_implemented | other | high, low, close | 100 | 1 | 13 | `e1081843ac6466a2` |
| gtja_short_cycle | alpha073 | not_implemented | correlation | close, volume, vwap | 30 | 1 | 13 | `189fb9ebb100f653` |
| gtja_short_cycle | alpha074 | not_implemented | correlation | low, volume, vwap | 40 | 1 | 13 | `115735d900570ed8` |
| gtja_short_cycle | alpha075 | not_implemented | open_gap_or_intraday | open, close | 50 | 1 | 13 | `477fb5fee21970ca` |
| gtja_short_cycle | alpha076 | not_implemented | volatility | close, volume | 20 | 1 | 13 | `35b77425f8036979` |
| gtja_short_cycle | alpha077 | not_implemented | correlation | high, low, volume, vwap | 40 | 1 | 13 | `83dc3fac7eb52357` |
| gtja_short_cycle | alpha078 | not_implemented | other | high, low, close | 12 | 1 | 13 | `b8402d21df7b01a5` |
| gtja_short_cycle | alpha079 | not_implemented | momentum_or_reversal | close | 100 | 1 | 13 | `888003523417142e` |
| gtja_short_cycle | alpha080 | normalized | liquidity_or_volume | volume | 100 | 1 | 13 | `4553556f3db91d69` |
| gtja_short_cycle | alpha081 | normalized | liquidity_or_volume | volume | 21 | 1 | 13 | `fbdc741f78ee24ad` |
| gtja_short_cycle | alpha082 | not_implemented | other | high, low, close | 100 | 1 | 13 | `55717c43a88675bf` |
| gtja_short_cycle | alpha083 | not_implemented | liquidity_or_volume | high, volume | 5 | 1 | 13 | `74eb9747b93f80ca` |
| gtja_short_cycle | alpha084 | not_implemented | liquidity_or_volume | close, volume | 20 | 1 | 13 | `8caa1033fbd92a05` |
| gtja_short_cycle | alpha085 | not_implemented | liquidity_or_volume | close, volume | 20 | 1 | 13 | `85bc2690a83cce91` |
| gtja_short_cycle | alpha086 | not_implemented | momentum_or_reversal | close | 20 | 1 | 13 | `411b8fd35ac0934d` |
| gtja_short_cycle | alpha087 | not_implemented | momentum_or_reversal | open, high, low, vwap | 11 | 1 | 13 | `011ccc559ff51c9f` |
| gtja_short_cycle | alpha088 | normalized | momentum_or_reversal | close | 100 | 1 | 13 | `3215daedfe9a94ce` |
| gtja_short_cycle | alpha089 | not_implemented | other | close | 27 | 1 | 13 | `e09cfcc1066061c2` |
| gtja_short_cycle | alpha090 | not_implemented | correlation | volume, vwap | 5 | 1 | 13 | `6371cecff5574e9b` |
| gtja_short_cycle | alpha091 | not_implemented | correlation | low, close, volume | 40 | 1 | 13 | `9735c11ebd16dbf5` |
| gtja_short_cycle | alpha092 | not_implemented | correlation | close, volume, vwap | 180 | 1 | 14 | `a592adab99e36460` |
| gtja_short_cycle | alpha093 | not_implemented | momentum_or_reversal | open, low | 20 | 1 | 14 | `28510ea29d5f8d43` |
| gtja_short_cycle | alpha094 | not_implemented | liquidity_or_volume | close, volume | 30 | 1 | 14 | `a6e2f71b6eb1f8b5` |
| gtja_short_cycle | alpha095 | normalized | volatility | amount | 20 | 1 | 14 | `64a4ed1d49bae32c` |
| gtja_short_cycle | alpha096 | not_implemented | other | high, low, close | 100 | 1 | 14 | `debbe12d1daa56be` |
| gtja_short_cycle | alpha097 | normalized | volatility | volume | 10 | 1 | 14 | `30bfa9a00aa76bac` |
| gtja_short_cycle | alpha098 | not_implemented | momentum_or_reversal | close | 100 | 1 | 14 | `621432e31bf844d8` |
| gtja_short_cycle | alpha099 | not_implemented | liquidity_or_volume | close, volume | 5 | 1 | 14 | `bf0fad800059166f` |
| gtja_short_cycle | alpha100 | normalized | volatility | volume | 20 | 1 | 14 | `6436df2da8da2595` |
| gtja_short_cycle | alpha101 | not_implemented | correlation | high, close, volume, vwap | 37 | 1 | 14 | `95691db180dee2b9` |
| gtja_short_cycle | alpha102 | normalized | liquidity_or_volume | volume | 100 | 1 | 14 | `7623e21dd1712dcf` |
| gtja_short_cycle | alpha103 | not_implemented | other | low | 100 | 1 | 14 | `523d44edb223fb89` |
| gtja_short_cycle | alpha104 | not_implemented | correlation | high, close, volume | 20 | 1 | 14 | `33806af6c54deceb` |
| gtja_short_cycle | alpha105 | not_implemented | correlation | open, volume | 10 | 1 | 14 | `4d02016cf4f1a1d6` |
| gtja_short_cycle | alpha106 | normalized | momentum_or_reversal | close | 20 | 1 | 14 | `cb20467d9440c4ca` |
| gtja_short_cycle | alpha107 | not_implemented | open_gap_or_intraday | open, high, low, close | 1 | 1 | 14 | `e2f2d04de99d6419` |
| gtja_short_cycle | alpha108 | not_implemented | correlation | high, volume, vwap | 120 | 1 | 14 | `4b1a3fd80d7703e2` |
| gtja_short_cycle | alpha109 | not_implemented | volatility | high, low | 10 | 1 | 14 | `a3e2f9cc9783caf3` |
| gtja_short_cycle | alpha110 | not_implemented | momentum_or_reversal | high, low, close | 100 | 1 | 14 | `7e6008902942e4d6` |
| gtja_short_cycle | alpha111 | not_implemented | volatility | high, low, close | 11 | 1 | 14 | `1618054c68eb8f4c` |
| gtja_short_cycle | alpha112 | not_implemented | momentum_or_reversal | close | 100 | 1 | 14 | `d7a770ffbcb338d7` |
| gtja_short_cycle | alpha113 | not_implemented | correlation | close, volume | 20 | 1 | 14 | `743de55b40dca7cc` |
| gtja_short_cycle | alpha114 | not_implemented | volatility | high, low, close, volume, vwap | 5 | 1 | 14 | `75f5a64674e3a439` |
| gtja_short_cycle | alpha115 | not_implemented | correlation | high, low, close, volume | 30 | 1 | 14 | `6d4e052446131928` |
| gtja_short_cycle | alpha116 | not_implemented | other | close | 20 | 1 | 14 | `067b383a8436c2ff` |
| gtja_short_cycle | alpha117 | not_implemented | liquidity_or_volume | high, low, close, volume | 32 | 1 | 14 | `df38571167517d31` |
| gtja_short_cycle | alpha118 | not_implemented | other | open, high, low | 100 | 1 | 14 | `adf74820c5ebef8c` |
| gtja_short_cycle | alpha119 | not_implemented | correlation | open, volume, vwap | 26 | 1 | 14 | `116ea53ca9ac44ce` |
| gtja_short_cycle | alpha120 | not_implemented | position | close, vwap | 1 | 1 | 14 | `c404abab04bf7ebe` |
| gtja_short_cycle | alpha121 | not_implemented | correlation | volume, vwap | 60 | 1 | 14 | `7a82143033f75250` |
| gtja_short_cycle | alpha122 | not_implemented | momentum_or_reversal | close | 13 | 1 | 14 | `d065dc12b97cc723` |
| gtja_short_cycle | alpha123 | not_implemented | correlation | high, low, volume | 60 | 1 | 14 | `3911169050157bca` |
| gtja_short_cycle | alpha124 | not_implemented | position | close, vwap | 30 | 1 | 14 | `5757761c54099369` |
| gtja_short_cycle | alpha125 | not_implemented | correlation | close, volume, vwap | 80 | 1 | 15 | `d2b34703baac15cf` |
| gtja_short_cycle | alpha126 | not_implemented | other | high, low, close | 3 | 1 | 15 | `8f8fdae72f0349a0` |
| gtja_short_cycle | alpha127 | not_implemented | other | close | 100 | 1 | 15 | `20e8492aa8123109` |
| gtja_short_cycle | alpha128 | not_implemented | liquidity_or_volume | high, low, close, volume | 100 | 1 | 15 | `e8fddd26f435e42d` |
| gtja_short_cycle | alpha129 | not_implemented | momentum_or_reversal | close | 12 | 1 | 15 | `41be5f8787dc1a1c` |
| gtja_short_cycle | alpha130 | not_implemented | correlation | high, low, volume, vwap | 40 | 1 | 15 | `77291063d054c037` |
| gtja_short_cycle | alpha131 | not_implemented | correlation | close, volume, vwap | 50 | 1 | 15 | `6e50628af8a8d421` |
| gtja_short_cycle | alpha132 | not_implemented | liquidity_or_volume | amount | 20 | 1 | 15 | `0b3368faf1234d25` |
| gtja_short_cycle | alpha133 | not_implemented | other | high, low | 100 | 1 | 15 | `9ed79c95aa586b42` |
| gtja_short_cycle | alpha134 | not_implemented | liquidity_or_volume | close, volume | 12 | 1 | 15 | `a3e1411626f49ab6` |
| gtja_short_cycle | alpha135 | not_implemented | momentum_or_reversal | close | 20 | 1 | 15 | `de5807b27e743589` |
| gtja_short_cycle | alpha136 | not_implemented | correlation | open, volume | 10 | 1 | 15 | `54d556efcf3adac3` |
| gtja_short_cycle | alpha137 | not_implemented | open_gap_or_intraday | open, high, low, close | 16 | 1 | 15 | `4fb7d9b6e6c52fe1` |
| gtja_short_cycle | alpha138 | not_implemented | correlation | low, volume, vwap | 60 | 1 | 15 | `437c7f0d2d8cca14` |
| gtja_short_cycle | alpha139 | not_implemented | correlation | open, volume | 10 | 1 | 15 | `ed8394b1bbfe8a9b` |
| gtja_short_cycle | alpha140 | not_implemented | correlation | open, high, low, close, volume | 60 | 1 | 15 | `75f0b7afae0536ff` |
| gtja_short_cycle | alpha141 | not_implemented | correlation | high, volume | 15 | 1 | 15 | `0fb984551a3b7af8` |
| gtja_short_cycle | alpha142 | not_implemented | liquidity_or_volume | close, volume | 20 | 1 | 15 | `f4b0c2522923e6e1` |
| gtja_short_cycle | alpha143 | normalized | momentum_or_reversal | close | 1 | 1 | 15 | `2b367f84a49cf863` |
| gtja_short_cycle | alpha144 | not_implemented | liquidity_or_volume | close, amount | 20 | 1 | 15 | `6273460e50797fd4` |
| gtja_short_cycle | alpha145 | not_implemented | liquidity_or_volume | volume | 100 | 1 | 15 | `5e4df0e1cf7376d6` |
| gtja_short_cycle | alpha146 | not_implemented | momentum_or_reversal | close | 61 | 1 | 15 | `f5b7c38d8df44506` |
| gtja_short_cycle | alpha147 | not_implemented | other | close | 12 | 1 | 15 | `39d1ba0810f807b4` |
| gtja_short_cycle | alpha148 | not_implemented | correlation | open, volume | 60 | 1 | 15 | `e52827b8fffb849f` |
| gtja_short_cycle | alpha149 | not_implemented | momentum_or_reversal | close | 252 | 1 | 15 | `29d4ad4b93229906` |
| gtja_short_cycle | alpha150 | not_implemented | liquidity_or_volume | high, low, close, volume | 3 | 1 | 15 | `225ba2a36fa2d59f` |
| gtja_short_cycle | alpha151 | not_implemented | momentum_or_reversal | close | 20 | 1 | 15 | `c9d74bf28398267b` |
| gtja_short_cycle | alpha152 | not_implemented | momentum_or_reversal | close | 26 | 1 | 16 | `c818e700e748585a` |
| gtja_short_cycle | alpha153 | not_implemented | other | close | 24 | 1 | 16 | `4fbad60533321da1` |
| gtja_short_cycle | alpha154 | not_implemented | correlation | volume, vwap | 180 | 1 | 16 | `131be270719f4e7a` |
| gtja_short_cycle | alpha155 | not_implemented | liquidity_or_volume | volume | 27 | 1 | 16 | `c1d9de5994ccc077` |
| gtja_short_cycle | alpha156 | not_implemented | momentum_or_reversal | open, low, vwap | 5 | 1 | 16 | `80990872cd045755` |
| gtja_short_cycle | alpha157 | not_implemented | momentum_or_reversal | close | 6 | 1 | 16 | `2eeefb868ffe1208` |
| gtja_short_cycle | alpha158 | not_implemented | other | high, low, close | 15 | 1 | 16 | `91790b0cade21f83` |
| gtja_short_cycle | alpha159 | not_implemented | momentum_or_reversal | low, close | 100 | 1 | 16 | `3eaf60836ac24521` |
| gtja_short_cycle | alpha160 | not_implemented | volatility | close | 20 | 1 | 16 | `fa80cdb30a11be20` |
| gtja_short_cycle | alpha161 | not_implemented | volatility | high, low, close | 12 | 1 | 16 | `b18798fa8a87d0b3` |
| gtja_short_cycle | alpha162 | not_implemented | momentum_or_reversal | close | 100 | 1 | 16 | `e3caab3c921c8b65` |
| gtja_short_cycle | alpha163 | not_implemented | liquidity_or_volume | high, close, volume, vwap | 20 | 1 | 16 | `72cc485b3a297a8f` |
| gtja_short_cycle | alpha164 | not_implemented | volatility | high, low, close | 100 | 1 | 16 | `24ad01ca759e29e2` |
| gtja_short_cycle | alpha165 | not_implemented | volatility | close | 48 | 1 | 16 | `a96b521517d467c5` |
| gtja_short_cycle | alpha166 | not_implemented | momentum_or_reversal | close | 20 | 1 | 16 | `bbcb91a4e13b832b` |
| gtja_short_cycle | alpha167 | not_implemented | momentum_or_reversal | close | 12 | 1 | 16 | `c247d8f051131f5c` |
| gtja_short_cycle | alpha168 | not_implemented | liquidity_or_volume | volume | 20 | 1 | 16 | `e959867bbde03296` |
| gtja_short_cycle | alpha169 | not_implemented | momentum_or_reversal | close | 26 | 1 | 16 | `8f4eb963daadb730` |
| gtja_short_cycle | alpha170 | not_implemented | liquidity_or_volume | high, close, volume, vwap | 20 | 1 | 16 | `4e01bc24547f4567` |
| gtja_short_cycle | alpha171 | not_implemented | open_gap_or_intraday | open, high, low, close | 5 | 1 | 16 | `8748e40738ee6182` |
| gtja_short_cycle | alpha172 | not_implemented | other | - | 100 | 1 | 16 | `b5189476253085db` |
| gtja_short_cycle | alpha173 | not_implemented | other | close | 13 | 1 | 16 | `f1e8ca3566ff2528` |
| gtja_short_cycle | alpha174 | not_implemented | volatility | close | 20 | 1 | 16 | `2b068ce6b10b06da` |
| gtja_short_cycle | alpha175 | not_implemented | volatility | high, low, close | 6 | 1 | 16 | `f0e39452e002b0c9` |
| gtja_short_cycle | alpha176 | not_implemented | correlation | high, low, close, volume | 12 | 1 | 16 | `dccafba32a62a72d` |
| gtja_short_cycle | alpha177 | not_implemented | other | high | 100 | 1 | 16 | `1ed15cdcec0c9f24` |
| gtja_short_cycle | alpha178 | not_implemented | liquidity_or_volume | close, volume | 1 | 1 | 16 | `47a8b2f3aa0c023b` |
| gtja_short_cycle | alpha179 | not_implemented | correlation | low, volume, vwap | 50 | 1 | 16 | `866fadbc1f2f6eee` |
| gtja_short_cycle | alpha180 | not_implemented | liquidity_or_volume | close, volume | 60 | 1 | 16 | `2d344567f2b8d1cd` |
| gtja_short_cycle | alpha181 | not_implemented | momentum_or_reversal | close | 20 | 1 | 17 | `8c91dabb6a262b8f` |
| gtja_short_cycle | alpha182 | not_implemented | open_gap_or_intraday | open, close | 20 | 1 | 17 | `5bef04747e7f5462` |
| gtja_short_cycle | alpha183 | not_implemented | volatility | close | 24 | 1 | 17 | `a5fd0b1ea3dc7be8` |
| gtja_short_cycle | alpha184 | not_implemented | correlation | open, close | 200 | 1 | 17 | `46d03f0f170f54ef` |
| gtja_short_cycle | alpha185 | not_implemented | open_gap_or_intraday | open, close | 2 | 1 | 17 | `4e925b76fd7d81f3` |
| gtja_short_cycle | alpha186 | not_implemented | momentum_or_reversal | - | 100 | 1 | 17 | `ab75de712d709d98` |
| gtja_short_cycle | alpha187 | not_implemented | momentum_or_reversal | open, high | 20 | 1 | 17 | `7660281c308d1fff` |
| gtja_short_cycle | alpha188 | not_implemented | volatility | high, low | 100 | 1 | 17 | `6b6511996ceaaf78` |
| gtja_short_cycle | alpha189 | not_implemented | other | close | 6 | 1 | 17 | `6c75a74fa500b88e` |
| gtja_short_cycle | alpha190 | not_implemented | momentum_or_reversal | close | 20 | 1 | 17 | `770e4be95c6299e1` |
| gtja_short_cycle | alpha191 | normalized | correlation | high, low, close, volume | 20 | 1 | 17 | `222ecca6fbc5596a` |

Machine-readable records and exact-fingerprint links are in
`reports/reproduction/factor_atlas.json`.
