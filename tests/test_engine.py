"""
Tests for engine.core.BacktestEngine.

These pin down the exact contract of the engine:
  - next-bar execution (no look-ahead)
  - cash accounting correctness
  - cost direction (buy pays more, sell receives less)
  - exact flat exit
  - equity curve length matches data length
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import pytest

from engine.core import BacktestEngine


# ------------------------------------------------------------------ construction

def test_engine_constructs():
    eng = BacktestEngine(initial_cash=100_000)
    assert eng.pf.cash == 100_000
    assert eng.pf.positions == {}


# ------------------------------------------------------------------ equity math

def test_buy_and_hold_zero_costs_matches_price_return(linear_up_df):
    """With zero costs, buy-and-hold equity return == price return."""
    df = linear_up_df
    signals = pd.Series(1.0, index=df.index)

    eng = BacktestEngine(initial_cash=100_000,
                         commission_bps=0, slippage_bps=0)
    equity = eng.run(df, signals)

    # Price return from bar 1's open to bar N's close
    price_return = df["close"].iloc[-1] / df["open"].iloc[1] - 1
    eq_return = equity.iloc[-1] / equity.iloc[0] - 1

    assert abs(eq_return - price_return) < 1e-6


def test_flat_signal_stays_in_cash(linear_up_df):
    """Signal = 0 everywhere → no trades, equity never changes."""
    df = linear_up_df
    signals = pd.Series(0.0, index=df.index)

    eng = BacktestEngine(initial_cash=100_000)
    equity = eng.run(df, signals)

    assert np.allclose(equity.values, 100_000.0)
    assert len(eng.pf.fills) == 0


def test_short_position_loses_on_rising_price(linear_up_df):
    """Short signal on rising prices → equity must fall."""
    df = linear_up_df
    signals = pd.Series(-1.0, index=df.index)

    eng = BacktestEngine(initial_cash=100_000,
                         commission_bps=0, slippage_bps=0)
    equity = eng.run(df, signals)

    assert equity.iloc[-1] < equity.iloc[0]


def test_long_position_gains_on_rising_price(linear_up_df):
    """Long signal on rising prices → equity must rise."""
    df = linear_up_df
    signals = pd.Series(1.0, index=df.index)

    eng = BacktestEngine(initial_cash=100_000,
                         commission_bps=0, slippage_bps=0)
    equity = eng.run(df, signals)

    assert equity.iloc[-1] > equity.iloc[0]


# ------------------------------------------------------------------ costs

def test_costs_reduce_returns(linear_up_df):
    """Adding commission + slippage must lower final equity."""
    df = linear_up_df
    signals = pd.Series(1.0, index=df.index)

    eng_free = BacktestEngine(initial_cash=100_000,
                              commission_bps=0, slippage_bps=0)
    eng_cost = BacktestEngine(initial_cash=100_000,
                              commission_bps=5, slippage_bps=20)

    eq_free = eng_free.run(df, signals)
    eq_cost = eng_cost.run(df, signals)

    assert eq_cost.iloc[-1] < eq_free.iloc[-1]


# ------------------------------------------------------------------ execution timing

def test_last_bar_signal_never_executes(linear_up_df):
    """Signal on last bar has no next bar to execute → no trade."""
    df = linear_up_df
    signals = pd.Series(0.0, index=df.index)
    signals.iloc[-1] = 1.0

    eng = BacktestEngine(initial_cash=100_000)
    equity = eng.run(df, signals)

    assert len(eng.pf.fills) == 0
    assert np.allclose(equity.values, 100_000.0)


def test_signal_executes_one_bar_later(linear_up_df):
    """Signal on bar 0 must NOT trade until bar 1's open."""
    df = linear_up_df
    signals = pd.Series(0.0, index=df.index)
    signals.iloc[0] = 1.0
    signals.iloc[1] = 0.0

    eng = BacktestEngine(initial_cash=100_000)
    eng.run(df, signals)

    # One trade should have occurred (long at bar 1, flat at bar 2)
    # At minimum, one fill must exist
    assert len(eng.pf.fills) >= 1
    # The first fill must be at bar 1's open (not bar 0)
    first_fill_ts = eng.pf.fills[0]["timestamp"]
    assert first_fill_ts == df.index[1]


# ------------------------------------------------------------------ exit precision

def test_flat_target_returns_position_to_exactly_zero(linear_up_df):
    """Long then flat → final position must be exactly 0.0 (not dust)."""
    df = linear_up_df
    signals = pd.Series(0.0, index=df.index)
    signals.iloc[0:5] = 1.0
    signals.iloc[5:] = 0.0

    eng = BacktestEngine(initial_cash=100_000,
                         commission_bps=1, slippage_bps=5)
    eng.run(df, signals)

    # Position must be exactly zero, not 1e-10
    assert eng.pf.positions["ASSET"] == 0.0


def test_equity_curve_length_matches_data(linear_up_df):
    """Equity Series must have the same number of bars as the data."""
    df = linear_up_df
    signals = pd.Series(1.0, index=df.index)

    eng = BacktestEngine(initial_cash=100_000)
    equity = eng.run(df, signals)

    assert len(equity) == len(df)
    assert equity.index.equals(df.index)


# ------------------------------------------------------------------ determinism

def test_engine_is_deterministic(linear_up_df):
    """Same inputs → identical equity curve, every run."""
    df = linear_up_df
    signals = pd.Series(1.0, index=df.index)

    eng1 = BacktestEngine(initial_cash=100_000,
                          commission_bps=1, slippage_bps=5)
    eng2 = BacktestEngine(initial_cash=100_000,
                          commission_bps=1, slippage_bps=5)
    eq1 = eng1.run(df, signals)
    eq2 = eng2.run(df, signals)

    assert eq1.equals(eq2)


# ------------------------------------------------------------------ fills

def test_fills_have_required_fields(linear_up_df):
    """Every fill must contain timestamp, side, qty, price, commission."""
    df = linear_up_df
    signals = pd.Series([1.0, 1.0, 0.0, 0.0] + [0.0] * 16,
                        index=df.index)

    eng = BacktestEngine(initial_cash=100_000)
    eng.run(df, signals)

    assert len(eng.pf.fills) >= 1
    for fill in eng.pf.fills:
        assert "timestamp" in fill
        assert "side" in fill
        assert "qty" in fill
        assert "price" in fill
        assert "commission" in fill
        assert fill["side"] in ("BUY", "SELL")
    
def test_no_phantom_flip_on_flat_exit(linear_up_df):
    """Long → flat must not produce a residual short position.

    Regression test for the overshoot bug: when target is 0, the fill
    quantity must equal exactly -current_pos, so the extract_trades
    sees a clean close, not a phantom sign flip.
    """
    import pandas as pd
    from analytics.metrics import extract_trades

    df = linear_up_df
    # Long for 10 bars, flat for 10 bars
    signals = pd.Series([1.0] * 10 + [0.0] * 10, index=df.index)

    eng = BacktestEngine(initial_cash=100_000,
                         commission_bps=1, slippage_bps=5)
    eng.run(df, signals)

    # Final position exactly zero
    assert eng.pf.positions["ASSET"] == 0.0

    # Extract trades: must be exactly 1 round-trip, LONG, no shorts
    trades = extract_trades(eng.pf.fills)
    assert len(trades) == 1
    assert trades.iloc[0]["direction"] == "LONG"