# strategies/07_absolute_momentum.py
import pandas as pd
from strategies.indicators import roc

def generate_signals(df: pd.DataFrame) -> pd.Series:
    lookback = 252   # 12 months
    mom = roc(df["close"], lookback)
    sig = pd.Series(0.0, index=df.index)
    sig[mom > 0] = 1.0
    sig[mom < 0] = 0    # or 0.0 for long-flat version
    return sig