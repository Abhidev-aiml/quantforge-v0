import pandas as pd
from strategies.indicators.indicators import ema

def generate_signals(df: pd.DataFrame) -> pd.Series:
    """Golden Cross with EMA 50/200. EMA reacts faster than SMA."""
    fast = ema(df["close"], 50)
    slow = ema(df["close"], 200)
    sig = pd.Series(0.0, index=df.index)
    sig[fast > slow] = 1.0
    return sig