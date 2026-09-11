# strategies/10_roc_momentum.py
import pandas as pd
from strategies.indicators import roc

def generate_signals(df: pd.DataFrame) -> pd.Series:
    N = 60
    threshold = 0.02   # require at least +2% move to go long
    m = roc(df["close"], N)

    sig = pd.Series(0.0, index=df.index)
    sig[m > threshold] = 1.0
    sig[m < -threshold] = -1.0
    return sig