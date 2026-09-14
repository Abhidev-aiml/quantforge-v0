import numpy as np
import pandas as pd
from validation.monte_carlo import (
    same_exposure_benchmark_cost_adjusted,
    bootstrap_trades_block,
)


def test_cost_adjusted_benchmark_lower_than_no_cost(linear_up_df):
    """With a signal that produces turnover, costs must reduce the
    benchmark equity curve."""
    df = linear_up_df
    # Alternate 1 / 0 / 1 / 0 → ~1.0 turnover per bar
    signals = pd.Series([1.0 if i % 2 == 0 else 0.0
                         for i in range(len(df))],
                        index=df.index)

    eq_free, _ = same_exposure_benchmark_cost_adjusted(
        df, signals, commission_bps=0, slippage_bps=0)
    eq_cost, _ = same_exposure_benchmark_cost_adjusted(
        df, signals, commission_bps=5, slippage_bps=20)

    assert eq_cost.iloc[-1] < eq_free.iloc[-1]

def test_cost_adjusted_benchmark_weight():
    idx = pd.date_range("2020-01-01", periods=20, freq="B")
    df = pd.DataFrame({
        "open": [100.0] * 20, "high": [100.0] * 20,
        "low": [100.0] * 20, "close": [100.0] * 20,
        "volume": [1_000_000] * 20,
    }, index=idx)
    signals = pd.Series(0.5, index=idx)
    _, w = same_exposure_benchmark_cost_adjusted(df, signals)
    assert w == 0.5


def test_block_trade_bootstrap_runs():
    rng = np.random.default_rng(0)
    trades = pd.DataFrame({
        "pnl": rng.normal(50, 200, size=60),
        "qty": [10] * 60,
        "entry_price": [50.0] * 60,
    })
    r = bootstrap_trades_block(trades, n_sims=200, block_size=5, seed=42)
    assert "error" not in r
    assert r["sharpe_p05"] <= r["sharpe_p95"]