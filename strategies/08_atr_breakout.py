import numpy as np
import pandas as pd
from strategies.indicators import ema, atr

def generate_signals(df: pd.DataFrame) -> pd.Series:
    mid = ema(df["close"], 20)
    a = atr(df["high"], df["low"], df["close"], 14)
    close = df["close"]
    k = 1.5

    upper = mid + k * a
    lower = mid - k * a

    enter_long = close > upper
    enter_short = close < lower
    exit_ = (close <= upper) & (close >= lower)

    state = pd.Series(np.nan, index=df.index)
    state[enter_long] = 1.0
    state[enter_short] = -1.0
    state[exit_] = 0.0
    return state.ffill().fillna(0.0).astype(float)