import pandas as pd
from strategies.indicators.indicators import sma

def generate_signals(df: pd.DataFrame) -> pd.Series:
    """Classic Golden Cross: SMA 50/200. Long-only."""
    fast = sma(df["close"], 50)
    slow = sma(df["close"], 200)
    sig = pd.Series(0.0, index=df.index)
    sig[fast > slow] = 1.0
    return sig