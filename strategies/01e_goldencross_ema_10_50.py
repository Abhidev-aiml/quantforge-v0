import pandas as pd
from strategies.indicators.indicators import ema

def generate_signals(df: pd.DataFrame) -> pd.Series:
    """Very fast EMA cross. This is the 'whipsaw' end of the spectrum.
    Included to show what NOT to do on a trending asset."""
    fast = ema(df["close"], 10)
    slow = ema(df["close"], 50)
    sig = pd.Series(0.0, index=df.index)
    sig[fast > slow] = 1.0
    return sig