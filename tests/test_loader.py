"""
Tests for engine.loader: strategy loading + signal validation.
Uses tmp_path to write temporary strategy files.
"""
from __future__ import annotations
from pathlib import Path

import pandas as pd
import pytest

from engine.loader import load_strategy, validate_signals, StrategyError


# ------------------------------------------------------------------ loading

def test_load_existing_strategy():
    fn = load_strategy("strategies/00_buy_hold.py")
    assert callable(fn)


def test_missing_file_raises():
    with pytest.raises(StrategyError):
        load_strategy("strategies/does_not_exist_at_all.py")


def test_non_py_file_raises(tmp_path):
    bad = tmp_path / "not_python.txt"
    bad.write_text("hello")
    with pytest.raises(StrategyError):
        load_strategy(bad)


def test_file_without_generate_signals_raises(tmp_path):
    bad = tmp_path / "no_func.py"
    bad.write_text("x = 42\n")
    with pytest.raises(StrategyError):
        load_strategy(bad)


def test_file_with_syntax_error_raises(tmp_path):
    bad = tmp_path / "syntax.py"
    bad.write_text("def generate_signals(df)\n    return 1\n")  # missing colon
    with pytest.raises(StrategyError):
        load_strategy(bad)


# ------------------------------------------------------------------ validation

def test_validate_accepts_valid_series(small_df):
    sig = pd.Series(1.0, index=small_df.index)
    clean = validate_signals(sig, small_df)
    assert isinstance(clean, pd.Series)
    assert clean.dtype == float
    assert (clean == 1.0).all()


def test_validate_rejects_list(small_df):
    with pytest.raises(StrategyError):
        validate_signals([1.0] * len(small_df), small_df)


def test_validate_rejects_wrong_length(small_df):
    sig = pd.Series([1.0] * 5)
    with pytest.raises(StrategyError):
        validate_signals(sig, small_df)


def test_validate_rejects_wrong_index(small_df):
    wrong_idx = pd.date_range("2025-01-01", periods=len(small_df), freq="B")
    sig = pd.Series(1.0, index=wrong_idx)
    with pytest.raises(StrategyError):
        validate_signals(sig, small_df)


def test_validate_rejects_leverage(small_df):
    sig = pd.Series(3.0, index=small_df.index)
    with pytest.raises(StrategyError):
        validate_signals(sig, small_df)


def test_validate_rejects_all_nan(small_df):
    sig = pd.Series(float("nan"), index=small_df.index)
    with pytest.raises(StrategyError):
        validate_signals(sig, small_df)


def test_validate_fills_nan_with_zero(small_df):
    sig = pd.Series([1.0, float("nan")] + [1.0] * (len(small_df) - 2),
                    index=small_df.index)
    clean = validate_signals(sig, small_df)
    assert clean.iloc[1] == 0.0
    assert clean.dtype == float


def test_validate_accepts_negative_weights(small_df):
    """-1.0 is a valid short signal."""
    sig = pd.Series(-1.0, index=small_df.index)
    clean = validate_signals(sig, small_df)
    assert (clean == -1.0).all()


def test_validate_converts_integer_dtype(small_df):
    """Integer 0/1 signals should become float."""
    sig = pd.Series([0, 1, 0, 1, 0, 1, 0, 1, 0, 1], index=small_df.index)
    clean = validate_signals(sig, small_df)
    assert clean.dtype == float