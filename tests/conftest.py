"""
Shared pytest configuration and fixtures for the reporting layer.

Fixtures here are visible to every test module in tests/.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


# ---- shared equity fixtures -----------------------------------------

@pytest.fixture
def synthetic_equity():
    """800 business days of mild positive-drift returns."""
    idx = pd.date_range("2020-01-01", periods=800, freq="B")
    rng = np.random.default_rng(0)
    rets = rng.normal(0.0004, 0.012, size=800)
    return pd.Series(100_000 * (1 + rets).cumprod(), index=idx, name="equity")


@pytest.fixture
def synthetic_returns(synthetic_equity):
    return synthetic_equity.pct_change().dropna()


# ---- shared run directory fixture -----------------------------------

@pytest.fixture
def synthetic_run_dir(tmp_path, synthetic_equity):
    """
    Minimal run directory with all artifacts ReportEngine needs.

    Layout:
        <tmp>/runs/test_001/
            equity.csv
            manifest.json
            metrics.json
        <tmp>/prices.csv   (benchmark source)
    """
    run_dir = tmp_path / "runs" / "test_001"
    run_dir.mkdir(parents=True)

    # equity
    df = synthetic_equity.reset_index()
    df.columns = ["timestamp", "equity"]
    df.to_csv(run_dir / "equity.csv", index=False)

    # price data used for buy-and-hold benchmark
    data_csv = tmp_path / "prices.csv"
    prices = synthetic_equity.values / synthetic_equity.values[0] * 100.0
    pd.DataFrame({
        "date": synthetic_equity.index,
        "open": prices, "high": prices, "low": prices,
        "close": prices, "volume": [1_000_000] * len(prices),
    }).to_csv(data_csv, index=False)

    # manifest
    (run_dir / "manifest.json").write_text(json.dumps({
        "run_id": "test_001",
        "started_utc": "2020-01-01T00:00:00",
        "config_hash": "abc123", "data_hash": "def456",
        "git_sha": "abc", "git_dirty": False,
        "config": {
            "data": {"path": str(data_csv), "symbol": "TEST"},
            "strategy": {"path": "strategies/test.py"},
        },
    }))

    # metrics
    (run_dir / "metrics.json").write_text(json.dumps({
        "sharpe": 0.85, "sortino": 1.1, "CAGR": 0.09,
        "max_drawdown": -0.21, "calmar": 0.42, "volatility": 0.14,
        "win_rate": 0.55, "num_trades": 42,
    }))

    return run_dir