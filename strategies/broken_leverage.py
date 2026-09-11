import pandas as pd

def generate_signals(df):
    return pd.Series(3.0, index=df.index)   # 300% — way out of range