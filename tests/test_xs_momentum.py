"""Tests for cross_sectional_momentum."""
import numpy as np
import pandas as pd

from strategies.xs_momentum import cross_sectional_momentum


def test_long_short_produces_correct_count():
    """3 up, 3 down, long_short=True → 3 longs, 3 shorts."""
    idx = pd.date_range("2020-01-01", periods=500, freq="B")
    close = pd.DataFrame({
        "UP1": np.linspace(100, 200, 500),
        "UP2": np.linspace(100, 180, 500),
        "UP3": np.linspace(100, 160, 500),
        "DN1": np.linspace(100, 50, 500),
        "DN2": np.linspace(100, 60, 500),
        "DN3": np.linspace(100, 70, 500),
    }, index=idx)

    w = cross_sectional_momentum(close, lookback=100, skip=10,
                                 top_k=3, bottom_k=3, long_short=True)
    last = w.iloc[-1]
    positives = (last > 0).sum()
    negatives = (last < 0).sum()
    assert positives == 3
    assert negatives == 3


def test_long_only_has_no_shorts():
    idx = pd.date_range("2020-01-01", periods=500, freq="B")
    close = pd.DataFrame({
        "A": np.linspace(100, 200, 500),
        "B": np.linspace(100, 150, 500),
        "C": np.linspace(100, 50, 500),
    }, index=idx)

    w = cross_sectional_momentum(close, lookback=100, skip=10,
                                 top_k=1, long_short=False)
    assert (w >= 0).all().all()
    last = w.iloc[-1]
    assert (last > 0).sum() == 1


def test_weights_are_gross_normalized():
    idx = pd.date_range("2020-01-01", periods=500, freq="B")
    close = pd.DataFrame({
        "A": np.linspace(100, 200, 500),
        "B": np.linspace(100, 150, 500),
        "C": np.linspace(100, 50, 500),
        "D": np.linspace(100, 30, 500),
    }, index=idx)

    w = cross_sectional_momentum(close, lookback=100, skip=10,
                                 top_k=2, bottom_k=2,
                                 long_short=True, gross_exposure=1.0)
    last = w.iloc[-1]
    assert abs(last.abs().sum() - 1.0) < 1e-9


def test_weights_are_zero_during_warmup():
    """Before the momentum window fills, weights should be zero."""
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    close = pd.DataFrame({
        "A": np.linspace(100, 200, 300),
        "B": np.linspace(100, 150, 300),
    }, index=idx)

    w = cross_sectional_momentum(close, lookback=200, skip=20,
                                 top_k=1, long_short=False)
    # First 220 bars have no valid momentum value
    assert (w.iloc[:220].abs().sum(axis=1) == 0).all()