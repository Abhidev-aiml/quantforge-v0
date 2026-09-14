"""Tests for strategy parameter wiring."""
import pandas as pd
import pytest

from engine.loader import call_strategy


def test_call_strategy_without_params_arg(small_df):
    """Strategies with only (df) still work."""
    def strat(df):
        return pd.Series(1.0, index=df.index)

    result = call_strategy(strat, small_df, params={"fast": 10})
    assert (result == 1.0).all()


def test_call_strategy_with_params_arg(small_df):
    """Strategies with (df, params) receive the params dict."""
    def strat(df, params=None):
        fast = params.get("fast", 5)
        return pd.Series(float(fast), index=df.index)

    result = call_strategy(strat, small_df, params={"fast": 20})
    assert (result == 20.0).all()


def test_call_strategy_with_kwargs(small_df):
    """Strategies using **kwargs still work."""
    def strat(df, **kwargs):
        return pd.Series(0.5, index=df.index)

    result = call_strategy(strat, small_df, params={"x": 1})
    assert (result == 0.5).all()


def test_call_strategy_handles_no_params_supplied(small_df):
    """Calling without a params dict defaults to empty."""
    def strat(df, params=None):
        assert params == {}
        return pd.Series(0.0, index=df.index)

    result = call_strategy(strat, small_df)
    assert (result == 0.0).all()