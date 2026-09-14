"""Tests for timeframe-aware MC annualization and cost consistency."""
import numpy as np
import pandas as pd
import pytest

from validation.monte_carlo import (
    bootstrap_returns_iid,
    bootstrap_returns_block,
    bootstrap_returns_under_null,
    bootstrap_trades,
    bootstrap_trades_block,
    signal_block_shuffle,
    _infer_periods_per_year,
)


@pytest.fixture
def hourly_equity():
    """~2000 hourly bars of mild positive drift."""
    rng = np.random.default_rng(0)
    n = 2000
    rets = rng.normal(0.0001, 0.002, size=n)
    eq = 100_000 * (1 + rets).cumprod()
    return pd.Series(eq, index=pd.date_range("2020-01-01", periods=n, freq="h"))


@pytest.fixture
def daily_equity():
    rng = np.random.default_rng(1)
    n = 1000
    rets = rng.normal(0.0004, 0.012, size=n)
    eq = 100_000 * (1 + rets).cumprod()
    return pd.Series(eq, index=pd.date_range("2020-01-01", periods=n, freq="B"))


def test_periods_per_year_inference_hourly(hourly_equity):
    """Hourly bars infer ~8760 periods/year, not 252."""
    ppy = _infer_periods_per_year(hourly_equity.index)
    assert 8000 < ppy < 9500, f"got {ppy}"


def test_periods_per_year_inference_daily(daily_equity):
    """Daily business-day bars infer ~252."""
    ppy = _infer_periods_per_year(daily_equity.index)
    assert 200 < ppy < 300, f"got {ppy}"


def test_iid_bootstrap_uses_inferred_ppy(hourly_equity):
    """The reported ppy should reflect hourly frequency."""
    r = bootstrap_returns_iid(hourly_equity, n_sims=200, seed=42)
    assert r["periods_per_year"] > 5000


def test_block_bootstrap_uses_inferred_ppy(hourly_equity):
    r = bootstrap_returns_block(hourly_equity, n_sims=200,
                                block_size=24, seed=42)
    assert r["periods_per_year"] > 5000


def test_null_bootstrap_uses_inferred_ppy(hourly_equity):
    r = bootstrap_returns_under_null(hourly_equity, n_sims=500,
                                     block_size=24, seed=42)
    assert r["periods_per_year"] > 5000


def test_explicit_ppy_overrides_inference(hourly_equity):
    """Caller can pin ppy to a specific value."""
    r = bootstrap_returns_iid(hourly_equity, n_sims=200,
                              periods_per_year=252, seed=42)
    assert r["periods_per_year"] == 252


def test_trade_bootstrap_infers_elapsed_years():
    """Trade bootstrap must derive elapsed_years from timestamps."""
    trades = pd.DataFrame({
        "entry_ts": pd.date_range("2015-01-01", periods=50, freq="30D"),
        "exit_ts":  pd.date_range("2015-01-15", periods=50, freq="30D"),
        "qty": [10] * 50,
        "entry_price": [50.0] * 50,
        "pnl": np.random.default_rng(0).normal(100, 500, size=50),
    })
    r = bootstrap_trades(trades, n_sims=200, seed=42)
    # 50 trades over ~4 years → ppy ~12.5, not 252
    assert 5 < r["periods_per_year"] < 30, f"got {r['periods_per_year']}"


def test_trade_block_bootstrap_infers_elapsed_years():
    trades = pd.DataFrame({
        "entry_ts": pd.date_range("2015-01-01", periods=50, freq="30D"),
        "exit_ts":  pd.date_range("2015-01-15", periods=50, freq="30D"),
        "qty": [10] * 50,
        "entry_price": [50.0] * 50,
        "pnl": np.random.default_rng(0).normal(100, 500, size=50),
    })
    r = bootstrap_trades_block(trades, n_sims=200, block_size=5, seed=42)
    assert 5 < r["periods_per_year"] < 30


def test_signal_block_shuffle_uses_provided_costs(daily_equity):
    """Cost parameters must affect the shuffled run."""
    # Build a tiny df + strategy that generates a fixed signal
    idx = daily_equity.index
    df = pd.DataFrame({
        "open": daily_equity.values,
        "high": daily_equity.values * 1.01,
        "low": daily_equity.values * 0.99,
        "close": daily_equity.values,
        "volume": [1_000_000] * len(idx),
    }, index=idx)

    def always_long(d):
        return pd.Series(1.0, index=d.index)

    # Zero-cost run
    r_free = signal_block_shuffle(
        df, always_long, block_size=20, n_sims=30,
        commission_bps=0, slippage_bps=0, seed=42,
    )
    # High-cost run
    r_cost = signal_block_shuffle(
        df, always_long, block_size=20, n_sims=30,
        commission_bps=20, slippage_bps=50, seed=42,
    )
    # Observed Sharpe should differ
    assert r_free["observed_sharpe"] != r_cost["observed_sharpe"]