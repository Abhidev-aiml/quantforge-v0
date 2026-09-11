import pandas as pd

def generate_signals(df):
    # CHEAT: uses tomorrow's return to decide today's position.
    # This is IMPOSSIBLE in real trading. It's here only to teach you
    # what a "too good to be true" backtest looks like.
    fwd = df["close"].pct_change().shift(-1)
    sig = pd.Series(0.0, index=df.index)
    sig[fwd > 0] = 1.0
    return sig