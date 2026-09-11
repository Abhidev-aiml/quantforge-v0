import numpy as np
import pandas as pd
from strategies.indicators import donchian

def generate_signals(df: pd.DataFrame) -> pd.Series:
    N_ENTRY, N_EXIT = 20, 10
    _, upper_e = donchian(df["high"], df["low"], N_ENTRY)
    lower_x, _ = donchian(df["high"], df["low"], N_EXIT)
    close = df["close"]

    enter = close > upper_e.shift(1)
    exit_ = close < lower_x.shift(1)

    state = pd.Series(np.nan, index=df.index)
    state[enter] = 1.0
    state[exit_] = 0.0
    return state.ffill().fillna(0.0).astype(float)