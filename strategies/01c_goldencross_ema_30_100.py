import pandas as pd
from strategies.indicators.indicators import ema

def generate_signals(df: pd.DataFrame) -> pd.Series:
    """Faster EMA Golden Cross. 30/100 is a common institutional pair."""
    fast = ema(df["close"], 30)
    slow = ema(df["close"], 100)
    sig = pd.Series(0.0, index=df.index)
    sig[fast > slow] = 1.0
    return sig