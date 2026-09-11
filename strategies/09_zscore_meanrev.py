import numpy as np
import pandas as pd
from strategies.indicators import zscore

def generate_signals(df: pd.DataFrame) -> pd.Series:
    z = zscore(df["close"], 20)

    enter_long = z < -2.0
    enter_short = z > 2.0
    exit_ = z.abs() < 0.5

    state = pd.Series(np.nan, index=df.index)
    state[enter_long] = 1.0
    state[enter_short] = -1.0
    state[exit_] = 0.0
    return state.ffill().fillna(0.0).astype(float)