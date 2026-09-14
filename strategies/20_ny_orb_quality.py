"""20 — NY 30M ORB: breakout + retest + high-quality confirmation.

Confirmation candle filters:
    - body/range >= 0.60
    - close location value >= 0.70 for long
    - close location value <= 0.30 for short

This isolates strong continuation candles rather than adding several
unrelated filters.
"""

from strategies.orb_utils import generate_orb_signals


def generate_signals(df):
    return generate_orb_signals(
        df,
        mode="quality",
        min_body_ratio=0.60,
        min_clv=0.70,
        entry_cutoff="15:30",
    )
