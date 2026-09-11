import pandas as pd

def generate_signals(df: pd.DataFrame) -> pd.Series:
    fast = df["close"].rolling(20).mean()
    slow = df["close"].rolling(100).mean()
    sig = pd.Series(0.0, index=df.index)
    sig[fast > slow] = 1.0
    sig[fast < slow] = -1.0
    return sig