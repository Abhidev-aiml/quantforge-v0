"""22 — NY 30M ORB: retest + ORB-range/ATR filter.

The ORB range is measured as:
    ORB high - ORB low

It is accepted only when:
    0.50 <= ORB range / pre-breakout ATR(14) <= 2.50

Both thresholds are research parameters, not established edges.
Change one threshold at a time during the experiment.
"""

from strategies.orb_utils import generate_orb_signals


def generate_signals(df):
    return generate_orb_signals(
        df,
        mode="orb_atr",
        orb_atr_min=0.50,
        orb_atr_max=2.50,
        entry_cutoff="15:30",
    )
