"""
Generate static CSV fixtures for test_data.py.

Run once: python -m tests.fixtures.generate
Or let conftest.py generate them on first test run.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd


FIXTURES_DIR = Path(__file__).parent


def _write(df: pd.DataFrame, name: str) -> None:
    path = FIXTURES_DIR / name
    df.to_csv(path, index=False)


def make_valid_ohlc() -> None:
    """20 clean bars, monotonic uptrend."""
    idx = pd.date_range("2020-01-01", periods=20, freq="B")
    prices = [100.0 + i for i in range(20)]
    _write(pd.DataFrame({
        "date":   idx,
        "open":   prices,
        "high":   [p + 1 for p in prices],
        "low":    [p - 1 for p in prices],
        "close":  prices,
        "volume": [1_000_000] * 20,
    }), "valid_ohlc.csv")


def make_bad_ohlc() -> None:
    """20 bars, 3 of which violate OHLC rules. Loader should drop them."""
    idx = pd.date_range("2020-01-01", periods=20, freq="B")
    prices = [100.0 + i for i in range(20)]
    df = pd.DataFrame({
        "date":   idx,
        "open":   prices,
        "high":   [p + 1 for p in prices],
        "low":    [p - 1 for p in prices],
        "close":  prices,
        "volume": [1_000_000] * 20,
    })
    # Row 5: low > open (violates low <= open)
    df.loc[5, "low"] = df.loc[5, "open"] + 10
    # Row 10: high < close (violates high >= close)
    df.loc[10, "high"] = df.loc[10, "close"] - 10
    # Row 15: negative close
    df.loc[15, "close"] = -1.0
    _write(df, "bad_ohlc.csv")


def make_dupes() -> None:
    """10 bars with 2 duplicated dates."""
    idx = pd.date_range("2020-01-01", periods=10, freq="B")
    prices = [100.0 + i for i in range(10)]
    df = pd.DataFrame({
        "date":   idx,
        "open":   prices,
        "high":   [p + 1 for p in prices],
        "low":    [p - 1 for p in prices],
        "close":  prices,
        "volume": [1_000_000] * 10,
    })
    # Duplicate the 3rd row
    df = pd.concat([df, df.iloc[[2]]], ignore_index=True)
    _write(df, "dupes.csv")


def make_missing_column() -> None:
    """Valid OHLC but missing 'volume'."""
    idx = pd.date_range("2020-01-01", periods=10, freq="B")
    prices = [100.0 + i for i in range(10)]
    _write(pd.DataFrame({
        "date":  idx,
        "open":  prices,
        "high":  [p + 1 for p in prices],
        "low":   [p - 1 for p in prices],
        "close": prices,
    }), "missing_column.csv")


def ensure_all() -> None:
    """Idempotent — safe to call from conftest.py on every run."""
    FIXTURES_DIR.mkdir(exist_ok=True)
    make_valid_ohlc()
    make_bad_ohlc()
    make_dupes()
    make_missing_column()


if __name__ == "__main__":
    ensure_all()
    print(f"✅ Fixtures written to {FIXTURES_DIR}")