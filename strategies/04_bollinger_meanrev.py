import numpy as np
import pandas as pd
from strategies.indicators.indicators import bollinger

def generate_signals(df: pd.DataFrame) -> pd.Series:
    lower, mid, upper = bollinger(df["close"], 20, 2.0)
    close = df["close"]

    enter = close < lower
    exit_ = close > mid

    state = pd.Series(np.nan, index=df.index)
    state[enter] = 1.0
    state[exit_] = 0.0
    return state.ffill().fillna(0.0).astype(float)