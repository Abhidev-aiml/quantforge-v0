"""21 — NY 30M ORB: retest + confirmation close-location filter.

CLV definition:
    (close - low) / (high - low)

Long confirmation:
    CLV >= 0.70

Short confirmation:
    CLV <= 0.30

No body-size filter is applied, so this tests CLV independently.
"""

from strategies.orb_utils import generate_orb_signals


def generate_signals(df):
    return generate_orb_signals(
        df,
        mode="clv",
        min_clv=0.70,
        entry_cutoff="15:30",
    )
