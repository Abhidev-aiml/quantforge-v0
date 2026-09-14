"""
Tests for engine.data: loading, validation, dedup, hashing.
Uses static CSV fixtures from tests/fixtures/.
"""
from __future__ import annotations
from pathlib import Path

import pandas as pd
import pytest

from engine.data import load_csv

FIXTURES = Path(__file__).parent / "fixtures"


# ------------------------------------------------------------------ loading

def test_load_valid_ohlc():
    df = load_csv(FIXTURES / "valid_ohlc.csv")
    assert len(df) == 20
    assert df.index.name == "date"
    assert df.index.is_monotonic_increasing
    for col in ["open", "high", "low", "close", "volume"]:
        assert col in df.columns


def test_load_drops_bad_ohlc_rows():
    df = load_csv(FIXTURES / "bad_ohlc.csv")
    # 3 rows violate OHLC rules, loader should drop them
    assert len(df) == 17


def test_load_dedupes_dates():
    df = load_csv(FIXTURES / "dupes.csv")
    assert len(df) == 10
    assert not df.index.duplicated().any()


def test_load_rejects_missing_column():
    with pytest.raises((ValueError, KeyError)):
        load_csv(FIXTURES / "missing_column.csv")


def test_load_rejects_nonexistent_file():
    with pytest.raises((FileNotFoundError, ValueError)):
        load_csv(FIXTURES / "this_file_does_not_exist.csv")


# ------------------------------------------------------------------ hashing

def test_cache_returns_hash():
    from engine.data import cache
    df = load_csv(FIXTURES / "valid_ohlc.csv")
    h = cache(df, FIXTURES / "valid_ohlc.csv")
    assert isinstance(h, str)
    assert len(h) > 0


def test_cache_hash_is_deterministic():
    """Same DataFrame must produce the same hash, every time."""
    from engine.data import cache
    df1 = load_csv(FIXTURES / "valid_ohlc.csv")
    df2 = load_csv(FIXTURES / "valid_ohlc.csv")
    h1 = cache(df1, FIXTURES / "valid_ohlc.csv")
    h2 = cache(df2, FIXTURES / "valid_ohlc.csv")
    assert h1 == h2


def test_cache_hash_differs_for_different_data():
    from engine.data import cache
    df1 = load_csv(FIXTURES / "valid_ohlc.csv")
    df2 = load_csv(FIXTURES / "bad_ohlc.csv")
    h1 = cache(df1, FIXTURES / "valid_ohlc.csv")
    h2 = cache(df2, FIXTURES / "bad_ohlc.csv")
    assert h1 != h2


# ------------------------------------------------------------------ integrity

def test_loaded_data_is_numeric():
    df = load_csv(FIXTURES / "valid_ohlc.csv")
    for col in ["open", "high", "low", "close", "volume"]:
        assert pd.api.types.is_numeric_dtype(df[col])


def test_loaded_data_has_no_nans():
    df = load_csv(FIXTURES / "valid_ohlc.csv")
    assert not df.isna().any().any()