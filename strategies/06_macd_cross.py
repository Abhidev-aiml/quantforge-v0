# strategies/06_macd_cross.py
import pandas as pd
from strategies.indicators import macd

def generate_signals(df: pd.DataFrame) -> pd.Series:
    line, sig_line, hist = macd(df["close"], 12, 26, 9)
    s = pd.Series(0.0, index=df.index)
    s[line > sig_line] = 1.0
    s[line < sig_line] = -1.0
    return s