"""17 — NY 30M ORB: pure breakout.

ORB:
    09:30–10:00 America/New_York = exactly six 5M bars.

Entry signal:
    First 5M candle after 10:00 whose CLOSE breaks the ORB high/low.

Execution:
    QuantForge executes the signal on the next bar open.
"""

from strategies.orb_utils import generate_orb_signals


def generate_signals(df):
    return generate_orb_signals(
        df,
        mode="breakout",
        entry_cutoff="15:30",
    )
