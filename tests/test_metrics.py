"""
Tests for analytics.metrics.

Uses simple, analytically-known series to verify Sharpe, MaxDD, CAGR,
and trade metrics.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import pytest

from analytics.metrics import compute_metrics, extract_trades


# ------------------------------------------------------------------ helpers

def _equity_from_returns(returns):
    """Build an equity curve with an explicit starting value.

    The equity has len(returns)+1 points: [100_000, 100_000*(1+r0), ...].
    Calling pct_change() on this exactly reproduces the input returns.
    """
    returns = np.asarray(returns, dtype=float)
    eq = np.empty(len(returns) + 1)
    eq[0] = 100_000.0
    for i, r in enumerate(returns):
        eq[i + 1] = eq[i] * (1.0 + r)
    return pd.Series(eq)


# ------------------------------------------------------------------ returns

def test_total_return_is_correct():
    equity = pd.Series([100.0, 110.0, 121.0])
    m = compute_metrics(equity)
    assert abs(m["total_return"] - 0.21) < 1e-9


def test_cagr_matches_manual_calc():
    returns = [0.0004] * 252
    equity = _equity_from_returns(returns)
    m = compute_metrics(equity)
    expected = (equity.iloc[-1] / equity.iloc[0]) ** (252 / 252) - 1
    assert abs(m["CAGR"] - expected) < 1e-3


# ------------------------------------------------------------------ drawdown

def test_max_drawdown_known_series():
    """Equity [100, 110, 105, 120, 90, 100]:
    - peak at 120, trough at 90 → drawdown = 90/120 - 1 = -0.25
    """
    equity = pd.Series([100.0, 110.0, 105.0, 120.0, 90.0, 100.0])
    m = compute_metrics(equity)
    assert abs(m["max_drawdown"] - (-0.25)) < 1e-9


def test_max_drawdown_monotonic_increasing_is_zero():
    equity = pd.Series([100.0, 105.0, 110.0, 120.0, 130.0])
    m = compute_metrics(equity)
    assert abs(m["max_drawdown"]) < 1e-9


# ------------------------------------------------------------------ Sharpe

def test_sharpe_matches_analytic():
    """Compute Sharpe analytically on a known return series."""
    returns = np.array([0.01, -0.005, 0.008, -0.003, 0.012,
                        0.002, -0.006, 0.009, 0.001, -0.004])
    equity = _equity_from_returns(returns)
    m = compute_metrics(equity, rf_annual=0.0)

    # Now pct_change() of equity reproduces exactly `returns`
    expected = returns.mean() / returns.std(ddof=1) * np.sqrt(252)
    assert abs(m["sharpe"] - expected) < 1e-6


def test_sharpe_is_zero_for_symmetric_random_walk():
    """Symmetric returns around 0 → Sharpe should be statistically
    indistinguishable from zero.

    With 10,000 samples, the standard error of Sharpe is ~0.16, so we
    allow up to 0.35 (~2.2 SE) before failing. This is a bug test, not
    a precision test.
    """
    rng = np.random.default_rng(42)
    returns = rng.normal(0, 0.01, size=10_000)
    equity = _equity_from_returns(returns)
    m = compute_metrics(equity, rf_annual=0.0)
    assert abs(m["sharpe"]) < 0.35


# ------------------------------------------------------------------ trades

def test_extract_trades_empty_fills():
    trades = extract_trades([])
    assert len(trades) == 0


def test_extract_trades_single_round_trip():
    fills = [
        {"timestamp": "2020-01-01", "qty": 100, "price": 50.0, "commission": 1.0},
        {"timestamp": "2020-01-05", "qty": -100, "price": 55.0, "commission": 1.0},
    ]
    trades = extract_trades(fills)
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["direction"] == "LONG"
    assert t["qty"] == 100
    assert abs(t["gross_pnl"] - 500.0) < 1e-9
    assert abs(t["pnl"] - 498.0) < 1e-9


def test_extract_trades_short_round_trip():
    fills = [
        {"timestamp": "2020-01-01", "qty": -100, "price": 50.0, "commission": 1.0},
        {"timestamp": "2020-01-05", "qty": 100, "price": 45.0, "commission": 1.0},
    ]
    trades = extract_trades(fills)
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["direction"] == "SHORT"
    assert abs(t["gross_pnl"] - 500.0) < 1e-9


def test_trade_metrics_all_wins():
    trades = pd.DataFrame({
        "pnl": [100.0, 200.0, 300.0],
        "qty": [10, 10, 10],
        "entry_price": [50.0, 50.0, 50.0],
    })
    equity = pd.Series([100_000, 100_500])
    m = compute_metrics(equity, trades=trades)
    assert m["win_rate"] == 1.0
    assert m["num_trades"] == 3
    assert m["profit_factor"] == float("inf")


def test_trade_metrics_mixed():
    trades = pd.DataFrame({
        "pnl": [100.0, -50.0, 200.0, -30.0],
        "qty": [10, 10, 10, 10],
        "entry_price": [50.0, 50.0, 50.0, 50.0],
    })
    equity = pd.Series([100_000, 100_220])
    m = compute_metrics(equity, trades=trades)
    assert m["win_rate"] == 0.5
    assert abs(m["profit_factor"] - 3.75) < 1e-9