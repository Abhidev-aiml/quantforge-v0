import pandas as pd
from strategies.indicators import ema

def generate_signals(df: pd.DataFrame) -> pd.Series:
    fast = ema(df["close"], 12)
    slow = ema(df["close"], 26)
    sig = pd.Series(0.0, index=df.index)
    sig[fast > slow] = 1.0
    sig[fast < slow] = -1.0
    return sig