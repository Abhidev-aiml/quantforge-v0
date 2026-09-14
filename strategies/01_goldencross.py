import pandas as pd
from strategies.indicators.indicators import sma


def generate_signals(df: pd.DataFrame, params: dict | None = None) -> pd.Series:
    params = params or {}
    fast_n = params.get("fast", 50)
    slow_n = params.get("slow", 200)

    fast = sma(df["close"], fast_n)
    slow = sma(df["close"], slow_n)
    sig = pd.Series(0.0, index=df.index)
    sig[fast > slow] = 1.0
    return sig