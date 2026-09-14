import pandas as pd
from strategies.indicators.indicators import ema

def generate_signals(df: pd.DataFrame) -> pd.Series:
    """Fast EMA cross. More trades, more whipsaw, more cost drag."""
    fast = ema(df["close"], 20)
    slow = ema(df["close"], 60)
    sig = pd.Series(0.0, index=df.index)
    sig[fast > slow] = 1.0
    return sig