"""Tests for walk-forward validation."""
import numpy as np
import pandas as pd
import pytest

from validation.walk_forward import (
    walk_forward,
    windows_to_dataframe,
)


@pytest.fixture
def long_series():
    """2000 bars, ~2 years of business days, mild uptrend."""
    idx = pd.date_range("2020-01-01", periods=2000, freq="B")
    prices = 100.0 * (1.0003 ** np.arange(2000)) + \
             np.random.default_rng(0).normal(0, 1.0, size=2000)
    prices = np.maximum(prices, 1.0)
    return pd.DataFrame({
        "open":   prices,
        "high":   prices * 1.005,
        "low":    prices * 0.995,
        "close":  prices,
        "volume": [1_000_000] * 2000,
    }, index=idx)


def always_long(df):
    return pd.Series(1.0, index=df.index)


def always_flat(df):
    return pd.Series(0.0, index=df.index)


def test_requires_enough_data(long_series):
    """Raise if train+test exceeds data length."""
    with pytest.raises(ValueError, match="exceeds data length"):
        walk_forward(long_series, always_long,
                     train_bars=3000, test_bars=252)


def test_produces_expected_window_count(long_series):
    """2000 bars, train=500, test=250, step=250 → 6 windows."""
    windows, agg = walk_forward(
        long_series, always_long,
        train_bars=500, test_bars=250, step_bars=250,
    )
    # Windows start at 0, 250, 500, 750, 1000, 1250 (each needs 500+250)
    # Last valid start: 2000 - 500 - 250 = 1250
    assert len(windows) == 6
    assert agg["n_windows"] == 6


def test_windows_are_non_overlapping_oos(long_series):
    """Each OOS window must not overlap the previous IS/OOS boundary."""
    windows, _ = walk_forward(
        long_series, always_long,
        train_bars=500, test_bars=250, step_bars=250,
    )
    for i in range(1, len(windows)):
        assert windows[i].oos_start > windows[i-1].oos_start


def test_oos_window_length_is_test_bars(long_series):
    """Each OOS equity slice must be exactly test_bars long."""
    windows, _ = walk_forward(
        long_series, always_long,
        train_bars=500, test_bars=250, step_bars=250,
    )
    for w in windows:
        assert w.oos_bars == 250


def test_flat_strategy_has_zero_sharpe(long_series):
    """Always-flat strategy → no trades → zero-ish Sharpe."""
    windows, agg = walk_forward(
        long_series, always_flat,
        train_bars=500, test_bars=250, step_bars=250,
    )
    # All OOS Sharpes should be NaN or 0 (no variation in flat equity)
    for w in windows:
        s = w.oos_metrics.get("sharpe", np.nan)
        assert np.isnan(s) or abs(s) < 0.01


def test_buy_and_hold_oos_sharpe_reflects_underlying(long_series):
    """Buy-and-hold OOS Sharpe should be meaningfully positive on
    a rising series."""
    windows, agg = walk_forward(
        long_series, always_long,
        train_bars=500, test_bars=250, step_bars=250,
    )
    assert agg["mean_OOS_sharpe"] > 0.5
    assert agg["pct_positive_OOS"] >= 0.7


def test_aggregate_includes_degradation(long_series):
    """Aggregate must include all key fields."""
    _, agg = walk_forward(
        long_series, always_long,
        train_bars=500, test_bars=250, step_bars=250,
    )
    for key in ["n_windows", "mean_IS_sharpe", "mean_OOS_sharpe",
                "pct_positive_OOS", "degradation_ratio", "robust"]:
        assert key in agg


def test_windows_to_dataframe(long_series):
    """Flattening to DataFrame preserves window count."""
    windows, _ = walk_forward(
        long_series, always_long,
        train_bars=500, test_bars=250, step_bars=250,
    )
    df = windows_to_dataframe(windows)
    assert len(df) == len(windows)
    assert "is_sharpe" in df.columns
    assert "oos_sharpe" in df.columns
    assert "degradation_ratio" not in df.columns  # aggregate-only


def test_strategy_params_are_passed(long_series):
    """Strategies with (df, params) receive the params dict."""
    def parameterized(df, params=None):
        val = (params or {}).get("weight", 0.5)
        return pd.Series(val, index=df.index)

    windows, _ = walk_forward(
        long_series, parameterized,
        strategy_params={"weight": 0.75},
        train_bars=500, test_bars=250, step_bars=250,
    )
    # Just confirm it runs without error
    assert len(windows) > 0

def test_benchmark_computed_per_window(long_series):
    """Per-window benchmark metrics must be present when enabled."""
    windows, agg = walk_forward(
        long_series, always_long,
        train_bars=500, test_bars=250, step_bars=250,
        compute_benchmark=True,
    )
    for w in windows:
        assert "sharpe" in w.oos_benchmark_metrics


def test_excess_sharpe_aggregate_present(long_series):
    """Aggregate must include excess Sharpe summary."""
    _, agg = walk_forward(
        long_series, always_long,
        train_bars=500, test_bars=250, step_bars=250,
        compute_benchmark=True,
    )
    assert "mean_OOS_excess_sharpe" in agg
    assert "pct_positive_excess_OOS" in agg


def test_buy_and_hold_excess_sharpe_near_zero(long_series):
    """Always-long strategy's benchmark = itself, so excess Sharpe ≈ 0.

    Tolerance is 0.15 (not 0.05) because the engine executes the first
    trade at bar 1's open while the benchmark uses close-to-close from
    bar 0. This produces a small but legitimate offset.
    """
    _, agg = walk_forward(
        long_series, always_long,
        train_bars=500, test_bars=250, step_bars=250,
        compute_benchmark=True,
        commission_bps=0, slippage_bps=0,
    )
    assert abs(agg["mean_OOS_excess_sharpe"]) < 0.15


def test_chained_oos_equity_is_built(long_series):
    """Chained OOS equity should exist and span the OOS period."""
    _, agg = walk_forward(
        long_series, always_long,
        train_bars=500, test_bars=250, step_bars=250,
    )
    assert "chained_OOS_sharpe" in agg
    assert agg["chained_OOS_bars"] > 500
    assert not np.isnan(agg["chained_OOS_sharpe"])


def test_chained_excess_sharpe_present(long_series):
    """Chained excess Sharpe should be computed when benchmark is on."""
    _, agg = walk_forward(
        long_series, always_long,
        train_bars=500, test_bars=250, step_bars=250,
        compute_benchmark=True,
    )
    assert "chained_OOS_excess_sharpe" in agg
    assert "chained_OOS_benchmark_sharpe" in agg


def test_low_confidence_flag_for_flat_strategy(long_series):
    """Flat strategy produces no trades → all windows low-confidence."""
    _, agg = walk_forward(
        long_series, always_flat,
        train_bars=500, test_bars=250, step_bars=250,
        min_trades_high_confidence=5,
    )
    assert agg["n_low_confidence_windows"] == agg["n_windows"]


def test_has_edge_verdict_field(long_series):
    """Aggregate must include has_edge boolean."""
    _, agg = walk_forward(
        long_series, always_long,
        train_bars=500, test_bars=250, step_bars=250,
    )
    assert "has_edge" in agg
    assert isinstance(agg["has_edge"], bool)


def test_windows_to_dataframe_new_columns(long_series):
    """DataFrame export must include benchmark + confidence columns."""
    windows, _ = walk_forward(
        long_series, always_long,
        train_bars=500, test_bars=250, step_bars=250,
        compute_benchmark=True,
    )
    df = windows_to_dataframe(windows)
    for col in ["oos_benchmark_sharpe", "oos_excess_sharpe",
                "oos_excess_CAGR", "low_confidence"]:
        assert col in df.columns