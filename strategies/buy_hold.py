import pandas as pd

def generate_signals(df: pd.DataFrame) -> pd.Series:
    return pd.Series(1.0, index=df.index)