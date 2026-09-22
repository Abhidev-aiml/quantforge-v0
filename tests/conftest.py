"""
Shared pytest configuration and fixtures for the entire test suite.

Contains:
  - DataFrames for engine / loader tests (small_df, linear_up_df,
    linear_down_df, flat_df)
  - DataFrames for reporting tests (synthetic_equity, synthetic_returns,
    synthetic_run_dir)
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


# ====================================================================
# Engine / loader fixtures
# ====================================================================

@pytest.fixture
def flat_df() -> pd.DataFrame:
    """20 business days, all prices = 100.0. Zero drift."""
    idx = pd.date_range("2020-01-01", periods=20, freq="B")
    return pd.DataFrame(
        {
            "open":   [100.0] * 20,
            "high":   [100.0] * 20,
            "low":    [100.0] * 20,
            "close":  [100.0] * 20,
            "volume": [1_000_000] * 20,
        },
        index=idx,
    )


@pytest.fixture
def linear_up_df() -> pd.DataFrame:
    """20 business days, price rises 1% per bar. Deterministic."""
    idx = pd.date_range("2020-01-01", periods=20, freq="B")
    prices = [100.0 * (1.01 ** i) for i in range(20)]
    return pd.DataFrame(
        {
            "open":   prices,
            "high":   [p * 1.001 for p in prices],
            "low":    [p * 0.999 for p in prices],
            "close":  prices,
            "volume": [1_000_000] * 20,
        },
        index=idx,
    )


@pytest.fixture
def linear_down_df() -> pd.DataFrame:
    """20 business days, price falls 1% per bar. Deterministic."""
    idx = pd.date_range("2020-01-01", periods=20, freq="B")
    prices = [100.0 * (0.99 ** i) for i in range(20)]
    return pd.DataFrame(
        {
            "open":   prices,
            "high":   [p * 1.001 for p in prices],
            "low":    [p * 0.999 for p in prices],
            "close":  prices,
            "volume": [1_000_000] * 20,
        },
        index=idx,
    )


@pytest.fixture
def small_df() -> pd.DataFrame:
    """10 business days, small linear uptrend. Used by loader tests."""
    idx = pd.date_range("2020-01-01", periods=10, freq="B")
    return pd.DataFrame(
        {
            "open":   list(range(100, 110)),
            "high":   list(range(101, 111)),
            "low":    list(range(99, 109)),
            "close":  list(range(100, 110)),
            "volume": [1_000_000] * 10,
        },
        index=idx,
    )


# ====================================================================
# Reporting fixtures
# ====================================================================

@pytest.fixture
def synthetic_equity():
    """800 business days of mild positive-drift returns."""
    idx = pd.date_range("2020-01-01", periods=800, freq="B")
    rng = np.random.default_rng(0)
    rets = rng.normal(0.0004, 0.012, size=800)
    return pd.Series(100_000 * (1 + rets).cumprod(), index=idx, name="equity")


@pytest.fixture
def synthetic_returns(synthetic_equity):
    return synthetic_equity.pct_change().dropna()


@pytest.fixture
def synthetic_run_dir(tmp_path, synthetic_equity):
    """
    Minimal run directory with all artifacts ReportEngine needs:
    equity.csv, manifest.json, metrics.json, monte_carlo.json.
    """
    run_dir = tmp_path / "runs" / "test_001"
    run_dir.mkdir(parents=True)

    df = synthetic_equity.reset_index()
    df.columns = ["timestamp", "equity"]
    df.to_csv(run_dir / "equity.csv", index=False)

    data_csv = tmp_path / "prices.csv"
    prices = synthetic_equity.values / synthetic_equity.values[0] * 100.0
    pd.DataFrame({
        "date": synthetic_equity.index,
        "open": prices, "high": prices, "low": prices,
        "close": prices, "volume": [1_000_000] * len(prices),
    }).to_csv(data_csv, index=False)

    (run_dir / "manifest.json").write_text(json.dumps({
        "run_id": "test_001",
        "started_utc": "2020-01-01T00:00:00",
        "config_hash": "abc123", "data_hash": "def456",
        "git_sha": "abc", "git_dirty": False,
        "config": {
            "data": {"path": str(data_csv), "symbol": "TEST"},
            "strategy": {"path": "strategies/test.py"},
        },
    }))

    (run_dir / "metrics.json").write_text(json.dumps({
        "sharpe": 0.85, "sortino": 1.1, "CAGR": 0.09,
        "max_drawdown": -0.21, "calmar": 0.42, "volatility": 0.14,
        "win_rate": 0.55, "num_trades": 42,
    }))

    (run_dir / "monte_carlo.json").write_text(json.dumps({
        "null_bootstrap": {
            "observed_sharpe": 0.85, "null_sharpe_mean": 0.0,
            "null_sharpe_std": 0.2, "null_sharpe_p05": -0.3,
            "null_sharpe_p95": 0.3, "p_value_one_sided": 0.02,
        },
        "iid_ci": {
            "real_sharpe": 0.85, "sharpe_p50": 0.85,
            "sharpe_p05": 0.5, "sharpe_p95": 1.2,
            "real_CAGR": 0.09, "cagr_p05": 0.03, "cagr_p95": 0.15,
            "prob_ruin": 0.01,
        },
    }))

    return run_dir