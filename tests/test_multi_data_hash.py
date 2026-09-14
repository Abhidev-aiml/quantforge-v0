"""Tests for universe-level data hashing."""
import pandas as pd
import pytest

from engine.multi_data import compute_universe_hash


@pytest.fixture
def universe():
    idx = pd.date_range("2020-01-01", periods=10, freq="B")
    def make(base):
        return pd.DataFrame({
            "open":   [base + i for i in range(10)],
            "high":   [base + i + 1 for i in range(10)],
            "low":    [base + i - 1 for i in range(10)],
            "close":  [base + i for i in range(10)],
            "volume": [1_000_000] * 10,
        }, index=idx)
    return {"AAA": make(100), "BBB": make(200)}


def test_hash_is_deterministic(universe):
    h1 = compute_universe_hash(universe)
    h2 = compute_universe_hash(universe)
    assert h1 == h2


def test_hash_is_order_independent(universe):
    """Dict insertion order shouldn't affect the hash."""
    reordered = {k: universe[k] for k in reversed(list(universe.keys()))}
    assert compute_universe_hash(universe) == compute_universe_hash(reordered)


def test_hash_changes_on_content_change(universe):
    modified = {k: v.copy() for k, v in universe.items()}
    modified["AAA"].iloc[0, 0] = 999.0
    assert compute_universe_hash(universe) != compute_universe_hash(modified)


def test_hash_changes_on_symbol_added(universe):
    extended = dict(universe)
    extended["CCC"] = universe["AAA"].copy()
    assert compute_universe_hash(universe) != compute_universe_hash(extended)