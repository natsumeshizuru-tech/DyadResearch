from __future__ import annotations

import math

import pandas as pd

from dyadresearch.reproductions.common.operators import standardize


def reduced_style_model(
    close: pd.DataFrame,
    float_market_cap: pd.DataFrame,
    amount: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Explicit reduced model used only by transparent reconstruction.

    It intentionally does not pretend to be CNE5: consensus earnings/growth
    fields and historical classifications are absent.
    """

    size = standardize(
        float_market_cap.where(float_market_cap > 0).map(math.log, na_action="ignore")
    )
    momentum = standardize(close.pct_change(252, fill_method=None).shift(21))
    liquidity = standardize(
        amount.rolling(21, min_periods=21).mean().map(math.log, na_action="ignore")
    )
    return {"size": size, "momentum": momentum, "liquidity": liquidity}
