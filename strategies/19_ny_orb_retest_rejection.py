"""19 — NY 30M ORB: retest + rejection confirmation.

Adds a rejection-quality requirement to the retest:
    Long  -> retest touches ORB high and closes in upper half.
    Short -> retest touches ORB low and closes in lower half.

Then the following candle must confirm beyond the breakout candle extreme.
"""

from strategies.orb_utils import generate_orb_signals


def generate_signals(df):
    return generate_orb_signals(
        df,
        mode="retest_rejection",
        entry_cutoff="15:30",
    )
