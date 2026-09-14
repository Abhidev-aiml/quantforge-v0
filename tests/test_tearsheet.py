"""Tests for reporting.tearsheet."""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from reporting.tearsheet import (
    build_tearsheet,
    _monthly_returns,
    _format_metrics_table,
    _kpi_tiles,
)


# ---------------------------------------------------------------- fixtures

@pytest.fixture
def fake_run_dir(tmp_path):
    """Build a minimal valid run directory."""
    run_dir = tmp_path / "runs" / "test_run_001"
    run_dir.mkdir(parents=True)

    # Equity curve — 400 business days, mild uptrend
    idx = pd.date_range("2020-01-01", periods=400, freq="B")
    rng = np.random.default_rng(0)
    rets = rng.normal(0.0004, 0.012, size=400)
    equity = 100_000 * (1 + rets).cumprod()
    eq_df = pd.DataFrame({"timestamp": idx, "equity": equity})
    eq_df.to_csv(run_dir / "equity.csv", index=False)

    # Manifest
    manifest = {
        "run_id": "test_run_001",
        "started_utc": "2020-01-01T00:00:00",
        "config_hash": "abc123",
        "data_hash": "def456",
        "git_sha": "xyz789",
        "git_dirty": False,
        "config": {
            "data": {"path": "data/raw/daily/xauusd_1D_comma.csv", "symbol": "XAUUSD"},
            "strategy": {"path": "strategies/01_goldencross.py"},
        },
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest))

    # Metrics
    metrics = {
        "sharpe": 0.85,
        "CAGR": 0.09,
        "max_drawdown": -0.21,
        "calmar": 0.42,
        "volatility": 0.14,
        "sortino": 1.1,
        "win_rate": 0.55,
        "num_trades": 42,
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics))

    # Trades
    trades = pd.DataFrame({
        "entry_ts": pd.date_range("2020-01-01", periods=10, freq="30D"),
        "exit_ts":  pd.date_range("2020-01-15", periods=10, freq="30D"),
        "direction": ["LONG"] * 5 + ["SHORT"] * 5,
        "qty": [10] * 10,
        "entry_price": [50.0] * 10,
        "exit_price":  [55.0] * 5 + [48.0] * 5,
        "pnl": [500, 520, 480, 510, 490, 200, -150, 180, -100, 250],
    })
    trades.to_csv(run_dir / "trades.csv", index=False)

    return run_dir


# ---------------------------------------------------------------- helpers

def test_monthly_returns_pivot():
    idx = pd.date_range("2020-01-01", "2021-12-31", freq="B")
    equity = pd.Series(np.linspace(100_000, 150_000, len(idx)), index=idx)
    monthly = _monthly_returns(equity)
    assert monthly is not None
    assert 2020 in monthly.index
    assert 2021 in monthly.index
    assert 1 in monthly.columns
    assert 12 in monthly.columns


def test_format_metrics_table_applies_percentage():
    metrics = {"CAGR": 0.10, "sharpe": 0.85, "num_trades": 42}
    rows = dict(_format_metrics_table(metrics))
    assert "%" in rows["CAGR"]
    assert "0.85" in rows["sharpe"] or "+0.85" in rows["sharpe"]
    assert rows["num_trades"] == "42"


def test_kpi_tiles_have_six_entries():
    metrics = {"sharpe": 0.85, "CAGR": 0.09, "max_drawdown": -0.21,
               "calmar": 0.42, "volatility": 0.14, "sortino": 1.1}
    tiles = _kpi_tiles(metrics)
    assert len(tiles) == 6
    labels = [t[0] for t in tiles]
    assert "Sharpe" in labels
    assert "CAGR" in labels


def test_kpi_class_positive_for_positive_sharpe():
    metrics = {"sharpe": 0.85}
    tiles = _kpi_tiles(metrics)
    sharpe_tile = [t for t in tiles if t[0] == "Sharpe"][0]
    assert sharpe_tile[2] == "pos"


def test_kpi_class_negative_for_negative_maxdd():
    metrics = {"max_drawdown": -0.21}
    tiles = _kpi_tiles(metrics)
    dd_tile = [t for t in tiles if t[0] == "Max Drawdown"][0]
    assert dd_tile[2] == "neg"


# ---------------------------------------------------------------- build

def test_build_tearsheet_creates_file(fake_run_dir):
    out = build_tearsheet(fake_run_dir)
    assert out.exists()
    assert out.name == "report.html"


def test_build_tearsheet_contains_expected_content(fake_run_dir):
    out = build_tearsheet(fake_run_dir)
    html = out.read_text()
    # Header
    assert "test_run_001" in html
    # Strategy path
    assert "strategies/01_goldencross.py" in html
    # Plotly CDN
    assert "cdn.plot.ly" in html
    # Metric values present
    assert "0.85" in html or "+0.85" in html
    assert "9.00%" in html or "+9.00%" in html
    # Section headers
    assert "Equity Curve" in html
    assert "Drawdown" in html
    assert "Monthly Returns" in html
    assert "Rolling Sharpe" in html


def test_build_tearsheet_handles_missing_trades(tmp_path):
    """Run directory without trades.csv still produces a valid report."""
    run_dir = tmp_path / "no_trades"
    run_dir.mkdir()

    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    eq_df = pd.DataFrame({
        "timestamp": idx,
        "equity": np.linspace(100_000, 120_000, len(idx)),
    })
    eq_df.to_csv(run_dir / "equity.csv", index=False)

    (run_dir / "manifest.json").write_text(json.dumps({
        "run_id": "no_trades",
        "config_hash": "x", "data_hash": "y", "git_sha": "z",
        "git_dirty": False, "started_utc": "2020-01-01",
        "config": {
            "data": {"path": "x", "symbol": "X"},
            "strategy": {"path": "y"},
        },
    }))
    (run_dir / "metrics.json").write_text(json.dumps({"sharpe": 0.5}))

    out = build_tearsheet(run_dir)
    assert out.exists()
    html = out.read_text()
    assert "Trade PnL Distribution" not in html  # no trades section


def test_build_tearsheet_custom_output_path(fake_run_dir, tmp_path):
    target = tmp_path / "custom_name.html"
    out = build_tearsheet(fake_run_dir, output_path=target)
    assert out == target
    assert target.exists()


def test_build_tearsheet_raises_on_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_tearsheet(tmp_path / "does_not_exist")


def test_build_tearsheet_raises_on_missing_manifest(tmp_path):
    run_dir = tmp_path / "empty"
    run_dir.mkdir()
    (run_dir / "metrics.json").write_text("{}")
    with pytest.raises(FileNotFoundError, match="manifest"):
        build_tearsheet(run_dir)