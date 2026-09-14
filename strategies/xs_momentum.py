"""
Cross-sectional momentum signal generator.

Ranks symbols by past momentum and produces target weights that go
long the top-k and (optionally) short the bottom-k. Weights are held
constant between monthly rebalances.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def cross_sectional_momentum(
    close_prices: pd.DataFrame,
    lookback: int = 252,
    skip: int = 21,
    top_k: int = 3,
    bottom_k: int = 3,
    rebalance_freq: str = "MS",   # month start
    long_short: bool = True,
    gross_exposure: float = 1.0,  # total absolute weight
) -> pd.DataFrame:
    """Return a DataFrame of target weights (dates × symbols).

    Args:
        close_prices:   DataFrame of close prices (dates × symbols)
        lookback:       momentum lookback in bars (default 252 ≈ 12 months)
        skip:           bars to skip near present (avoids short-term reversal)
        top_k:          number of symbols to long
        bottom_k:       number of symbols to short (ignored if long_short=False)
        rebalance_freq: pandas frequency string for rebalance dates
        long_short:     if False, only long top_k (bottom_k ignored)
        gross_exposure: total |weight| (1.0 = fully invested)
    """
    close = close_prices.sort_index().copy()

    # Momentum: return from (t-lookback-skip) to (t-skip)
    mom = close.shift(skip) / close.shift(lookback + skip) - 1.0

    # Rebalance dates: intersect freq with actual trading days
    all_dates = close.index
    target_dates = pd.date_range(all_dates.min(), all_dates.max(),
                                 freq=rebalance_freq)
    # Snap each target to the first available trading day >= target
    rebalance_dates = []
    for d in target_dates:
        candidates = all_dates[all_dates >= d]
        if len(candidates):
            rebalance_dates.append(candidates[0])
    rebalance_dates = sorted(set(rebalance_dates))

    # Sparse weights, only set on rebalance dates, then ffill
    sparse = pd.DataFrame(np.nan, index=close.index, columns=close.columns)

    for rb in rebalance_dates:
        if rb not in mom.index:
            continue
        row = mom.loc[rb].dropna()
        if len(row) < top_k + (bottom_k if long_short else 0):
            continue

        ranked = row.sort_values(ascending=False)
        longs = list(ranked.head(top_k).index)

        if long_short:
            shorts = list(ranked.tail(bottom_k).index)
            # gross_exposure split equally between long and short legs
            long_w = (gross_exposure / 2.0) / top_k
            short_w = -((gross_exposure / 2.0) / bottom_k)
            for sym in longs:
                sparse.loc[rb, sym] = long_w
            for sym in shorts:
                sparse.loc[rb, sym] = short_w
        else:
            long_w = gross_exposure / top_k
            for sym in longs:
                sparse.loc[rb, sym] = long_w

    weights = sparse.ffill().fillna(0.0)
    return weights