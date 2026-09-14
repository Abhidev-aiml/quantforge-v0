"""Tests for tier2 charts and the full research report."""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import plotly.graph_objects as go

from reporting.charts import trades as T
from reporting.charts import monte_carlo as MC
from reporting.charts import walk_forward as WF
from reporting.charts import whites_rc as RC
from reporting.charts import regime as RG
from reporting.tiers.tier2_research import build_tier2


# ---------------------------------------------------------------- fixtures

@pytest.fixture
def synthetic_trades():
    rng = np.random.default_rng(1)
    n = 60
    entries = pd.date_range("2020-01-01", periods=n, freq="5D")
    exits = entries + pd.Timedelta(days=4)
    return pd.DataFrame({
        "entry_ts": entries, "exit_ts": exits,
        "direction": ["LONG"] * n,
        "entry_price": [100.0] * n,
        "exit_price": [100.0 + rng.normal(2, 5) for _ in range(n)],
        "qty": [10] * n,
        "gross_pnl": rng.normal(100, 500, size=n),
        "commission": [1.0] * n,
        "pnl": rng.normal(100, 500, size=n),
        "scale_ins": [0] * n,
    })


@pytest.fixture
def synthetic_windows():
    rows = []
    for i in range(8):
        rows.append({
            "window": i + 1,
            "oos_start": pd.Timestamp("2015-01-01") + pd.Timedelta(days=365 * i),
            "oos_end":   pd.Timestamp("2016-01-01") + pd.Timedelta(days=365 * i),
            "is_sharpe": float(np.random.default_rng(i).normal(0.7, 0.3)),
            "oos_sharpe": float(np.random.default_rng(i + 100).normal(0.4, 0.5)),
            "oos_excess_sharpe": float(np.random.default_rng(i + 200).normal(-0.1, 0.4)),
            "oos_n_trades": int(np.random.default_rng(i + 300).integers(1, 40)),
        })
    return pd.DataFrame(rows)


@pytest.fixture
def synthetic_wf_aggregate():
    return {
        "n_windows": 8, "n_oos_clean": 8,
        "mean_IS_sharpe": 0.7, "mean_OOS_sharpe": 0.4,
        "chained_OOS_sharpe": 0.42,
        "chained_OOS_benchmark_sharpe": 0.75,
        "chained_OOS_excess_sharpe": -0.33,
        "robust": True, "has_edge": False,
    }


@pytest.fixture
def synthetic_rc():
    return {
        "V_observed": 0.030, "V_bootstrap_mean": 0.029,
        "V_bootstrap_p95": 0.052, "V_bootstrap_p99": 0.067,
        "p_value": 0.41, "best_combo": "ema × brent",
        "n_combos_with_positive_mean": 51,
        "n_combos_with_negative_mean": 92,
        "top_5_combos": [
            {"label": f"combo {i}", "annualized_excess_return": 0.10 - 0.02 * i}
            for i in range(5)
        ],
    }


@pytest.fixture
def synthetic_mc():
    return {
        "null_bootstrap": {
            "observed_sharpe": 0.637, "null_sharpe_mean": -0.05,
            "null_sharpe_std": 0.22, "null_sharpe_p05": -0.40,
            "null_sharpe_p95": 0.30, "p_value_one_sided": 0.01,
        },
        "iid_ci": {
            "real_sharpe": 0.637, "sharpe_p50": 0.64,
            "sharpe_p05": 0.29, "sharpe_p95": 0.98,
            "real_CAGR": 0.09, "cagr_p05": -0.01, "cagr_p95": 0.15,
            "prob_ruin": 0.056,
        },
        "trade_ci": {
            "n_trades": 67, "real_sharpe": 0.29,
            "sharpe_p50": 0.29, "sharpe_p05": -0.07, "sharpe_p95": 0.50,
            "cagr_p05": -0.01, "cagr_p95": 0.12,
        },
        "signal_shuffle_sweep": [
            {"block": b, "p_value": p}
            for b, p in zip([2, 5, 20, 40, 80, 160],
                            [0.013, 0.123, 0.263, 0.283, 0.317, 0.393])
        ],
    }


# ---------------------------------------------------------------- trades

def test_trade_pnl_distribution(synthetic_trades):
    fig = T.chart_trade_pnl_distribution(synthetic_trades)
    assert isinstance(fig, go.Figure)


def test_trade_pnl_distribution_empty():
    fig = T.chart_trade_pnl_distribution(None)
    assert len(fig.data) == 0


def test_cumulative_trade_pnl(synthetic_trades):
    fig = T.chart_cumulative_trade_pnl(synthetic_trades)
    assert isinstance(fig, go.Figure)


def test_holding_period(synthetic_trades):
    fig = T.chart_holding_period_distribution(synthetic_trades)
    assert isinstance(fig, go.Figure)


def test_streaks(synthetic_trades):
    fig = T.chart_consecutive_streaks(synthetic_trades)
    assert isinstance(fig, go.Figure)


def test_win_loss_breakdown(synthetic_trades):
    fig = T.chart_win_loss_breakdown(synthetic_trades)
    assert isinstance(fig, go.Figure)


def test_trade_timeline(synthetic_trades):
    fig = T.chart_trade_timeline(synthetic_trades)
    assert isinstance(fig, go.Figure)


# ---------------------------------------------------------------- MC

def test_mc_null_sharpe(synthetic_mc):
    fig = MC.chart_mc_null_sharpe(synthetic_mc)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 2  # band + observed


def test_mc_null_sharpe_empty():
    fig = MC.chart_mc_null_sharpe(None)
    assert len(fig.data) == 0


def test_mc_iid_ci(synthetic_mc):
    fig = MC.chart_mc_iid_ci(synthetic_mc)
    assert isinstance(fig, go.Figure)


def test_mc_trade_ci(synthetic_mc):
    fig = MC.chart_mc_trade_ci(synthetic_mc)
    assert isinstance(fig, go.Figure)


def test_mc_block_sweep(synthetic_mc):
    fig = MC.chart_mc_block_sweep(synthetic_mc)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1


def test_mc_cagr_ci(synthetic_mc):
    fig = MC.chart_mc_cagr_ci(synthetic_mc)
    assert isinstance(fig, go.Figure)


def test_mc_prob_ruin(synthetic_mc):
    fig = MC.chart_mc_prob_ruin(synthetic_mc)
    assert isinstance(fig, go.Figure)


# ---------------------------------------------------------------- WF

def test_wf_scatter(synthetic_windows):
    fig = WF.chart_wf_is_vs_oos_scatter(synthetic_windows)
    assert isinstance(fig, go.Figure)


def test_wf_oos_series(synthetic_windows):
    fig = WF.chart_wf_oos_sharpe_series(synthetic_windows)
    assert isinstance(fig, go.Figure)


def test_wf_excess(synthetic_windows):
    fig = WF.chart_wf_excess_sharpe(synthetic_windows)
    assert isinstance(fig, go.Figure)


def test_wf_trade_counts(synthetic_windows):
    fig = WF.chart_wf_trade_counts(synthetic_windows)
    assert isinstance(fig, go.Figure)


def test_wf_summary(synthetic_wf_aggregate):
    fig = WF.chart_wf_summary_bars(synthetic_wf_aggregate)
    assert isinstance(fig, go.Figure)


def test_wf_empty():
    fig = WF.chart_wf_is_vs_oos_scatter(None)
    assert len(fig.data) == 0


# ---------------------------------------------------------------- RC

def test_rc_v_distribution(synthetic_rc):
    fig = RC.chart_rc_v_distribution(synthetic_rc)
    assert isinstance(fig, go.Figure)


def test_rc_top_combos(synthetic_rc):
    fig = RC.chart_rc_top_combos(synthetic_rc)
    assert isinstance(fig, go.Figure)


def test_rc_combo_distribution(synthetic_rc):
    fig = RC.chart_rc_combo_distribution(synthetic_rc)
    assert isinstance(fig, go.Figure)


def test_rc_empty():
    fig = RC.chart_rc_v_distribution(None)
    assert len(fig.data) == 0


# ---------------------------------------------------------------- regime

@pytest.fixture
def equity_long():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2015-01-01", periods=1500, freq="B")
    rets = rng.normal(0.0003, 0.012, 1500)
    return pd.Series(100_000 * (1 + rets).cumprod(), index=idx)


def test_regime_classify(equity_long):
    labels = RG.classify_regimes(equity_long, window=63)
    assert not labels.empty
    assert set(labels.unique()).issubset({"low", "mid", "high"})


def test_regime_overlay(equity_long):
    fig = RG.chart_regime_overlay(equity_long)
    assert isinstance(fig, go.Figure)


def test_regime_performance(equity_long):
    fig = RG.chart_regime_performance(equity_long)
    assert isinstance(fig, go.Figure)


def test_bull_bear_performance(equity_long):
    bench = equity_long * 1.05
    fig = RG.chart_bull_bear_performance(equity_long, bench)
    assert isinstance(fig, go.Figure)


def test_rolling_beta(equity_long):
    bench = equity_long * 1.05
    fig = RG.chart_rolling_beta(equity_long, bench, window=100)
    assert isinstance(fig, go.Figure)


def test_rolling_beta_no_benchmark(equity_long):
    fig = RG.chart_rolling_beta(equity_long, None)
    assert len(fig.data) == 0


# ---------------------------------------------------------------- tier 2

def test_build_tier2_produces_file(synthetic_run_dir):
    out = build_tier2(synthetic_run_dir)
    assert out.exists()
    assert out.name == "report_full.html"
    html = out.read_text()
    assert "Research Report" in html
    assert "Section A" in html
    assert "Section I" in html

# ---------------------------------------------------------------- MC paths

@pytest.fixture
def synthetic_mc_with_paths():
    """MC dict that includes the new `paths` section."""
    rng = np.random.default_rng(0)
    n_sims = 200
    n_bars = 200
    sims = np.cumprod(1 + rng.normal(0.0003, 0.01, size=(n_sims, n_bars)), axis=1)

    bands = {
        "p05": np.percentile(sims, 5, axis=0).tolist(),
        "p25": np.percentile(sims, 25, axis=0).tolist(),
        "p50": np.percentile(sims, 50, axis=0).tolist(),
        "p75": np.percentile(sims, 75, axis=0).tolist(),
        "p95": np.percentile(sims, 95, axis=0).tolist(),
    }
    dd = (sims / np.maximum.accumulate(sims, axis=1) - 1).min(axis=1)

    return {
        "null_bootstrap": {
            "observed_sharpe": 0.5, "null_sharpe_mean": 0.0,
            "null_sharpe_std": 0.2, "null_sharpe_p05": -0.3,
            "null_sharpe_p95": 0.3, "p_value_one_sided": 0.02,
        },
        "iid_ci": {
            "real_sharpe": 0.5, "sharpe_p50": 0.5,
            "sharpe_p05": 0.2, "sharpe_p95": 0.8,
            "real_CAGR": 0.05, "cagr_p05": -0.01, "cagr_p95": 0.10,
            "prob_ruin": 0.02,
        },
        "paths": {
            "n_sims": n_sims,
            "n_paths_saved": 50,
            "n_bars": n_bars,
            "percentile_bands": bands,
            "paths_sample": sims[:50].tolist(),
            "terminal_wealth": sims[:, -1].tolist(),
            "max_drawdown": dd.tolist(),
            "observed_equity": sims[0].tolist(),
        },
    }


def test_mc_fan_paths(synthetic_mc_with_paths):
    fig = MC.chart_mc_fan_paths(synthetic_mc_with_paths)
    assert isinstance(fig, go.Figure)
    # 50 paths + 3 bands (5-95, 25-75, median) + 1 observed = 54 traces
    assert len(fig.data) >= 50


def test_mc_fan_paths_no_data():
    fig = MC.chart_mc_fan_paths(None)
    assert len(fig.data) == 0


def test_mc_terminal_wealth(synthetic_mc_with_paths):
    fig = MC.chart_mc_terminal_wealth(synthetic_mc_with_paths)
    assert isinstance(fig, go.Figure)
    assert any(isinstance(t, go.Histogram) for t in fig.data)


def test_mc_drawdown_distribution(synthetic_mc_with_paths):
    fig = MC.chart_mc_drawdown_distribution(synthetic_mc_with_paths)
    assert isinstance(fig, go.Figure)
    assert any(isinstance(t, go.Histogram) for t in fig.data)