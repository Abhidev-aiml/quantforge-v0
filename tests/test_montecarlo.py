"""
Tests for validation.monte_carlo.

Verifies determinism, distributional correctness, and CI ordering.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import pytest

from validation.monte_carlo import (
    bootstrap_returns_iid,
    bootstrap_returns_under_null,
    bootstrap_returns_block,
    bootstrap_trades,
)


@pytest.fixture
def realistic_equity():
    """~1000 bars of realistic-looking daily returns."""
    rng = np.random.default_rng(0)
    returns = rng.normal(0.0004, 0.012, size=1000)
    eq = 100_000 * (1 + returns).cumprod()
    return pd.Series(eq, index=pd.date_range("2020-01-01", periods=1000, freq="B"))


# ------------------------------------------------------------------ determinism

def test_iid_bootstrap_is_deterministic(realistic_equity):
    r1 = bootstrap_returns_iid(realistic_equity, n_sims=200, seed=42)
    r2 = bootstrap_returns_iid(realistic_equity, n_sims=200, seed=42)
    assert r1["sharpe_mean"] == r2["sharpe_mean"]


def test_block_bootstrap_is_deterministic(realistic_equity):
    r1 = bootstrap_returns_block(realistic_equity, n_sims=200, block_size=20, seed=42)
    r2 = bootstrap_returns_block(realistic_equity, n_sims=200, block_size=20, seed=42)
    assert r1["sharpe_mean"] == r2["sharpe_mean"]


# ------------------------------------------------------------------ null bootstrap

def test_null_bootstrap_is_centered_near_zero(realistic_equity):
    """After subtracting the mean, the null Sharpe distribution centers on 0."""
    r = bootstrap_returns_under_null(realistic_equity, n_sims=2000, seed=42)
    assert abs(r["null_sharpe_mean"]) < 0.10
    # p-value is well-defined
    assert 0.0 <= r["p_value_one_sided"] <= 1.0
    assert 0.0 <= r["p_value_two_sided"] <= 1.0


def test_null_bootstrap_se_matches_theory(realistic_equity):
    """Standard error of Sharpe ≈ sqrt(1/Years)."""
    r = bootstrap_returns_under_null(realistic_equity, n_sims=3000,
                                     block_size=20, seed=42)
    years = len(realistic_equity) / 252
    theoretical_se = np.sqrt(1.0 / years)  # for Sharpe=0
    # Block bootstrap has fatter tails than IID, so allow 3× slack
    assert r["null_sharpe_std"] < theoretical_se * 3.0
    assert r["null_sharpe_std"] > theoretical_se * 0.3


# ------------------------------------------------------------------ distribution sanity

def test_iid_bootstrap_bounds_are_ordered(realistic_equity):
    r = bootstrap_returns_iid(realistic_equity, n_sims=500, seed=42)
    assert r["sharpe_p05"] < r["sharpe_p50"] < r["sharpe_p95"]
    assert r["sharpe_p05"] < r["sharpe_mean"] < r["sharpe_p95"]


# ------------------------------------------------------------------ trade bootstrap

def test_trade_bootstrap_requires_minimum_trades():
    trades = pd.DataFrame({"pnl": [1.0, 2.0], "qty": [1, 1],
                           "entry_price": [10.0, 10.0]})
    r = bootstrap_trades(trades, n_sims=100, seed=42)
    assert "error" in r


def test_trade_bootstrap_returns_ci():
    rng = np.random.default_rng(0)
    pnls = rng.normal(50, 200, size=50)
    trades = pd.DataFrame({
        "pnl": pnls,
        "qty": [10] * 50,
        "entry_price": [50.0] * 50,
    })
    r = bootstrap_trades(trades, n_sims=500, seed=42)
    assert r["sharpe_p05"] <= r["sharpe_p50"] <= r["sharpe_p95"]
    assert 0.0 <= r["p_value_sharpe"] <= 1.0