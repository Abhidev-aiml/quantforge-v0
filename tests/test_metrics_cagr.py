import numpy as np
import pandas as pd
from analytics.metrics import compute_metrics


def test_cagr_uses_calendar_days_when_index_is_datetime():
    """Two-year doubling → CAGR ≈ 41.4%."""
    idx = pd.date_range("2020-01-01", "2022-01-01", freq="B")
    equity = pd.Series(np.linspace(100_000, 200_000, len(idx)), index=idx)
    m = compute_metrics(equity)
    assert abs(m["CAGR"] - 0.4142) < 0.02


def test_cagr_auto_detects_elapsed_years():
    """No elapsed_years arg, but datetime index → still correct."""
    idx = pd.date_range("2020-01-01", periods=500, freq="B")
    equity = pd.Series(np.linspace(100_000, 150_000, 500), index=idx)
    m = compute_metrics(equity)
    # Roughly 2 years span → CAGR should be ~22-23%
    assert 0.15 < m["CAGR"] < 0.30