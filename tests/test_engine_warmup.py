import numpy as np
import pandas as pd
from engine.core import BacktestEngine


def test_warmup_suppresses_early_signals(linear_up_df):
    df = linear_up_df
    signals = pd.Series(1.0, index=df.index)

    eng = BacktestEngine(initial_cash=100_000, warmup_bars=5,
                         commission_bps=0, slippage_bps=0)
    equity = eng.run(df, signals)

    # No trade before bar 6
    if eng.pf.fills:
        assert eng.pf.fills[0]["timestamp"] >= df.index[6]

    # Equity flat during warmup
    for i in range(5):
        assert abs(equity.iloc[i] - 100_000.0) < 1e-9


def test_warmup_zero_is_unchanged(linear_up_df):
    df = linear_up_df
    signals = pd.Series(1.0, index=df.index)

    eng = BacktestEngine(initial_cash=100_000, warmup_bars=0,
                         commission_bps=0, slippage_bps=0)
    equity = eng.run(df, signals)
    assert equity.iloc[-1] > equity.iloc[0]