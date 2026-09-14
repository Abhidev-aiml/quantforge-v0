"""Tests for engine.multi_core.MultiAssetBacktestEngine."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.multi_core import MultiAssetBacktestEngine


# ------------------------------------------------------------ fixtures

@pytest.fixture
def two_asset_data():
    """Two symbols, both rising linearly at 1% per bar, 20 bars."""
    idx = pd.date_range("2020-01-01", periods=20, freq="B")

    def make(start_price):
        prices = [start_price * (1.01 ** i) for i in range(20)]
        return pd.DataFrame({
            "open":   prices,
            "high":   [p * 1.001 for p in prices],
            "low":    [p * 0.999 for p in prices],
            "close":  prices,
            "volume": [1_000_000] * 20,
        }, index=idx)

    return {"AAA": make(100.0), "BBB": make(200.0)}


@pytest.fixture
def two_asset_data_flat():
    """Two symbols, flat at 100 and 200. Tests absence of drift."""
    idx = pd.date_range("2020-01-01", periods=20, freq="B")

    def make(px):
        return pd.DataFrame({
            "open":   [px] * 20,
            "high":   [px] * 20,
            "low":    [px] * 20,
            "close":  [px] * 20,
            "volume": [1_000_000] * 20,
        }, index=idx)

    return {"AAA": make(100.0), "BBB": make(200.0)}


# ------------------------------------------------------------ construction

def test_engine_constructs():
    eng = MultiAssetBacktestEngine(symbols=["A", "B"], initial_cash=100_000)
    assert eng.pf.cash == 100_000
    assert eng.pf.positions == {}


# ------------------------------------------------------------ basic runs

def test_buy_and_hold_no_costs_matches_price_return(two_asset_data):
    """Equal-weight buy-and-hold on two identical returning assets."""
    data = two_asset_data
    idx = data["AAA"].index
    signals = pd.DataFrame(0.5, index=idx, columns=["AAA", "BBB"])

    eng = MultiAssetBacktestEngine(
        symbols=["AAA", "BBB"],
        initial_cash=100_000,
        commission_bps=0,
        slippage_bps=0,
    )
    equity = eng.run(data, signals)

    # Price return from bar 1 open to bar N close
    price_return = data["AAA"]["close"].iloc[-1] / data["AAA"]["open"].iloc[1] - 1
    eq_return = equity.iloc[-1] / equity.iloc[0] - 1
    assert abs(eq_return - price_return) < 1e-3


def test_all_flat_signals_leave_cash_unchanged(two_asset_data):
    data = two_asset_data
    signals = pd.DataFrame(0.0, index=data["AAA"].index, columns=["AAA", "BBB"])

    eng = MultiAssetBacktestEngine(symbols=["AAA", "BBB"], initial_cash=100_000)
    equity = eng.run(data, signals)

    assert np.allclose(equity.values, 100_000.0)
    assert len(eng.pf.fills) == 0


def test_short_position_loses_on_rising_price(two_asset_data):
    data = two_asset_data
    signals = pd.DataFrame(
        {"AAA": -0.5, "BBB": -0.5},
        index=data["AAA"].index,
    )

    eng = MultiAssetBacktestEngine(
        symbols=["AAA", "BBB"],
        initial_cash=100_000,
        commission_bps=0,
        slippage_bps=0,
    )
    equity = eng.run(data, signals)

    assert equity.iloc[-1] < equity.iloc[0]


# ------------------------------------------------------------ flat exit precision

def test_flat_target_returns_position_to_exactly_zero(two_asset_data):
    data = two_asset_data
    idx = data["AAA"].index
    sig = pd.DataFrame(0.0, index=idx, columns=["AAA", "BBB"])
    sig.iloc[0:10] = 0.5
    sig.iloc[10:] = 0.0

    eng = MultiAssetBacktestEngine(
        symbols=["AAA", "BBB"],
        initial_cash=100_000,
        commission_bps=1,
        slippage_bps=5,
    )
    eng.run(data, sig)

    assert eng.pf.positions["AAA"] == 0.0
    assert eng.pf.positions["BBB"] == 0.0


# ------------------------------------------------------------ costs

def test_costs_reduce_returns(two_asset_data):
    data = two_asset_data
    signals = pd.DataFrame(0.5, index=data["AAA"].index, columns=["AAA", "BBB"])

    eng_free = MultiAssetBacktestEngine(
        symbols=["AAA", "BBB"], initial_cash=100_000,
        commission_bps=0, slippage_bps=0,
    )
    eng_cost = MultiAssetBacktestEngine(
        symbols=["AAA", "BBB"], initial_cash=100_000,
        commission_bps=5, slippage_bps=20,
    )
    eq_free = eng_free.run(data, signals)
    eq_cost = eng_cost.run(data, signals)

    assert eq_cost.iloc[-1] < eq_free.iloc[-1]


# ------------------------------------------------------------ determinism

def test_engine_is_deterministic(two_asset_data):
    data = two_asset_data
    signals = pd.DataFrame(0.5, index=data["AAA"].index, columns=["AAA", "BBB"])

    eng1 = MultiAssetBacktestEngine(symbols=["AAA", "BBB"], initial_cash=100_000)
    eng2 = MultiAssetBacktestEngine(symbols=["AAA", "BBB"], initial_cash=100_000)
    eq1 = eng1.run(data, signals)
    eq2 = eng2.run(data, signals)

    assert eq1.equals(eq2)


# ------------------------------------------------------------ allow_short

def test_allow_short_false_prevents_negative_positions(two_asset_data):
    data = two_asset_data
    signals = pd.DataFrame(-0.5, index=data["AAA"].index, columns=["AAA", "BBB"])

    eng = MultiAssetBacktestEngine(
        symbols=["AAA", "BBB"],
        initial_cash=100_000,
        allow_short=False,
    )
    eng.run(data, signals)

    assert eng.pf.positions.get("AAA", 0.0) >= 0.0
    assert eng.pf.positions.get("BBB", 0.0) >= 0.0


# ------------------------------------------------------------ fills

def test_fills_have_symbol_field(two_asset_data):
    data = two_asset_data
    signals = pd.DataFrame(0.5, index=data["AAA"].index, columns=["AAA", "BBB"])

    eng = MultiAssetBacktestEngine(symbols=["AAA", "BBB"], initial_cash=100_000)
    eng.run(data, signals)

    for f in eng.pf.fills:
        assert "symbol" in f
        assert f["symbol"] in ("AAA", "BBB")