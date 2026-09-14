"""Tests for the reporting layer: engine, theme, charts, tier1."""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import plotly.graph_objects as go

from reporting.theme import apply_theme, empty_figure, COLORS
from reporting.engine import ReportEngine, RunArtifacts
from reporting.charts import performance as P
from reporting.charts import risk as R
from reporting.tiers.tier1_executive import build_tier1, build_verdict


# Note: synthetic_equity, synthetic_returns, and synthetic_run_dir
# fixtures are defined in tests/conftest.py and available project-wide.


# ---------------------------------------------------------------- theme

def test_apply_theme_sets_colors():
    """Verify the theme applies the light paper color and white chart bg."""
    fig = go.Figure()
    apply_theme(fig)
    # Paper (outer) is the light panel; plot area is white so charts read
    # as cards against the page background.
    assert fig.layout.paper_bgcolor == COLORS["panel"]
    assert fig.layout.plot_bgcolor == COLORS["panel"]
    # Text color must be dark for readability on light background
    assert fig.layout.font.color == COLORS["text"]


def test_empty_figure_has_annotation():
    fig = empty_figure("nothing here")
    assert len(fig.layout.annotations) == 1
    assert "nothing" in fig.layout.annotations[0].text


# ---------------------------------------------------------------- engine

def test_engine_loads_minimal_run(synthetic_run_dir):
    art = ReportEngine(synthetic_run_dir).load()
    assert isinstance(art, RunArtifacts)
    assert art.run_id == "test_001"
    assert len(art.equity) == 800
    assert art.metrics["sharpe"] == 0.85
    assert art.benchmark is not None
    assert len(art.benchmark) == len(art.equity)


def test_engine_missing_run_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ReportEngine(tmp_path / "does_not_exist").load()


def test_engine_missing_manifest_raises(tmp_path):
    d = tmp_path / "no_manifest"
    d.mkdir()
    with pytest.raises(FileNotFoundError):
        ReportEngine(d).load()


def test_engine_benchmark_scaled_to_capital(synthetic_run_dir):
    art = ReportEngine(synthetic_run_dir).load()
    assert abs(art.benchmark.iloc[0] - art.equity.iloc[0]) < 1e-6


def test_artifacts_returns_and_drawdown(synthetic_run_dir):
    art = ReportEngine(synthetic_run_dir).load()
    assert len(art.returns) == len(art.equity) - 1
    assert art.drawdown.iloc[0] == 0.0
    assert art.drawdown.min() <= 0.0


# ---------------------------------------------------------------- performance charts

def test_equity_curve_returns_figure(synthetic_equity):
    fig = P.chart_equity_curve(synthetic_equity)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1


def test_equity_curve_with_benchmark(synthetic_equity):
    bench = synthetic_equity * 1.1
    fig = P.chart_equity_curve(synthetic_equity, bench)
    assert len(fig.data) == 2


def test_equity_curve_short_series_returns_empty():
    short = pd.Series([100.0], index=pd.date_range("2020-01-01", periods=1))
    fig = P.chart_equity_curve(short)
    # empty figure has an annotation instead of traces
    assert len(fig.data) == 0


def test_cumulative_return(synthetic_equity):
    fig = P.chart_cumulative_return(synthetic_equity)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_excess_return(synthetic_equity):
    bench = synthetic_equity * 1.05
    fig = P.chart_excess_return(synthetic_equity, bench)
    assert isinstance(fig, go.Figure)


def test_excess_return_no_benchmark():
    eq = pd.Series([100.0, 101.0], index=pd.date_range("2020-01-01", periods=2))
    fig = P.chart_excess_return(eq, None)
    assert len(fig.data) == 0


def test_rolling_cagr(synthetic_equity):
    fig = P.chart_rolling_cagr(synthetic_equity, windows=(60, 120))
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_annual_returns(synthetic_equity):
    fig = P.chart_annual_returns(synthetic_equity)
    assert isinstance(fig, go.Figure)


def test_monthly_heatmap(synthetic_equity):
    fig = P.chart_monthly_heatmap(synthetic_equity)
    assert isinstance(fig, go.Figure)
    assert any(isinstance(t, go.Heatmap) for t in fig.data)


def test_return_distribution(synthetic_returns):
    fig = P.chart_return_distribution(synthetic_returns)
    assert isinstance(fig, go.Figure)
    # histogram + normal overlay
    assert len(fig.data) == 2


# ---------------------------------------------------------------- risk charts

def test_rolling_volatility(synthetic_equity):
    fig = R.chart_rolling_volatility(synthetic_equity, windows=(21, 63))
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_rolling_var(synthetic_equity):
    fig = R.chart_rolling_var(synthetic_equity, window=100)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2  # VaR + CVaR


def test_qq_plot(synthetic_returns):
    fig = R.chart_qq_plot(synthetic_returns)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_qq_plot_short_returns():
    fig = R.chart_qq_plot(pd.Series([1.0, 2.0]))
    assert len(fig.data) == 0


def test_tail_ratio(synthetic_equity):
    fig = R.chart_rolling_tail_ratio(synthetic_equity, window=100)
    assert isinstance(fig, go.Figure)


def test_drawdown(synthetic_equity):
    fig = R.chart_drawdown(synthetic_equity)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1


def test_top_drawdowns(synthetic_equity):
    fig = R.chart_top_drawdowns(synthetic_equity, top_n=3)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_top_drawdowns_table(synthetic_equity):
    df = R.top_drawdowns_table(synthetic_equity, top_n=5)
    if not df.empty:
        assert "depth_pct" in df.columns
        assert df["depth_pct"].iloc[0] < 0


# ---------------------------------------------------------------- tier1

def test_build_verdict_no_wf(synthetic_run_dir):
    art = ReportEngine(synthetic_run_dir).load()
    verdict = build_verdict(art)
    assert verdict["wf_robust"] == "—"
    assert verdict["has_edge"] == "—"


def test_build_tier1_produces_file(synthetic_run_dir):
    out = build_tier1(synthetic_run_dir)
    assert out.exists()
    assert out.name == "report_executive.html"
    html = out.read_text()
    assert "test_001" in html
    assert "Sharpe" in html
    assert "Equity Curve" in html
    assert "cdn.plot.ly" in html