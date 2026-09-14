"""18 — NY 30M ORB: breakout + immediate retest + confirmation.

Long:
    1. 5M close > ORB high.
    2. Immediately following 5M candle touches ORB high and closes above it.
    3. Next 5M candle closes above breakout candle high.

Short is the exact mirror.

Signal is emitted at confirmation close; QuantForge enters next bar open.
"""

from strategies.orb_utils import generate_orb_signals


def generate_signals(df):
    return generate_orb_signals(
        df,
        mode="retest",
        entry_cutoff="15:30",
    )
