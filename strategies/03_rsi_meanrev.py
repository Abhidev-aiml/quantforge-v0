import numpy as np
import pandas as pd
from strategies.indicators.indicators import rsi, sma

def generate_signals(df: pd.DataFrame) -> pd.Series:
    r = rsi(df["close"], 2)
    trend = sma(df["close"], 200)

    enter = (r < 10) & (df["close"] > trend)
    exit_ = (r > 70)

    state = pd.Series(np.nan, index=df.index)
    state[enter] = 1.0
    state[exit_] = 0.0
    return state.ffill().fillna(0.0).astype(float)