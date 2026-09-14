"""23 — NY 30M ORB: retest + elevated-ATR regime filter.

Requires the pre-breakout ATR(14) to be at or above its own historical
intraday median (50th percentile), using only observations available
before the breakout candle.

This is deliberately a simple regime test. Do not optimize the percentile
until the baseline is measured out-of-sample.
"""

from strategies.orb_utils import generate_orb_signals


def generate_signals(df):
    return generate_orb_signals(
        df,
        mode="atr_regime",
        atr_regime_quantile=0.50,
        entry_cutoff="15:30",
    )
