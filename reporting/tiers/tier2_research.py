"""
Tier 2 — Full research report.

Assembles performance, risk, trade, MC, walk-forward, RC, and regime
sections into one comprehensive HTML report.
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from reporting.engine import ReportEngine, RunArtifacts
from reporting.tiers.tier1_executive import (
    kpi_tiles,
    build_verdict,
    _fmt_pct,
    _fmt_num,
    _fmt_ratio,
)

# Tier 1 charts (reused)
from reporting.charts.performance import (
    chart_equity_curve, chart_cumulative_return, chart_excess_return,
    chart_rolling_cagr, chart_annual_returns, chart_monthly_heatmap,
    chart_return_distribution,
)
from reporting.charts.risk import (
    chart_rolling_volatility, chart_rolling_var, chart_qq_plot,
    chart_rolling_tail_ratio, chart_drawdown, chart_top_drawdowns,
    top_drawdowns_table,
)
# Tier 2 charts (new)
from reporting.charts.trades import (
    chart_trade_pnl_distribution, chart_cumulative_trade_pnl,
    chart_holding_period_distribution, chart_consecutive_streaks,
    chart_win_loss_breakdown, chart_trade_timeline,
)
from reporting.charts.monte_carlo import (
    chart_mc_null_sharpe, chart_mc_iid_ci, chart_mc_trade_ci,
    chart_mc_block_sweep, chart_mc_cagr_ci, chart_mc_prob_ruin,
    chart_mc_fan_paths, chart_mc_terminal_wealth, chart_mc_drawdown_distribution,
)
from reporting.charts.walk_forward import (
    chart_wf_is_vs_oos_scatter, chart_wf_oos_sharpe_series,
    chart_wf_excess_sharpe, chart_wf_trade_counts, chart_wf_summary_bars,
)
from reporting.charts.whites_rc import (
    chart_rc_v_distribution, chart_rc_top_combos, chart_rc_combo_distribution,
)
from reporting.charts.regime import (
    chart_regime_overlay, chart_regime_performance,
    chart_bull_bear_performance, chart_rolling_beta,
)


TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _render(fig) -> str:
    if fig is None:
        return ""
    return fig.to_html(
        include_plotlyjs=False, full_html=False,
        config={"displayModeBar": False, "responsive": True},
    )


def _metrics_table(metrics: dict) -> list[tuple[str, str]]:
    rows = []
    for key in sorted(metrics.keys()):
        v = metrics[key]
        if isinstance(v, float) and np.isnan(v):
            formatted = "—"
        elif key in {"CAGR", "volatility", "max_drawdown", "avg_drawdown",
                     "VaR_95", "VaR_99", "CVaR_95", "CVaR_99",
                     "expectancy_pct", "avg_win_pct", "avg_loss_pct",
                     "win_rate"}:
            formatted = _fmt_pct(v) if isinstance(v, (int, float)) else str(v)
        else:
            formatted = _fmt_num(v)
        rows.append((key, formatted))
    return rows


def build_tier2(
    run_dir: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    art = ReportEngine(run_dir).load()
    output_path = Path(output_path) if output_path else (
        art.run_dir / "report_full.html"
    )

    # ---- prepare common inputs ----
    kpis = kpi_tiles(art.metrics)
    verdict = build_verdict(art)
    has_trades = art.trades is not None and not art.trades.empty
    has_mc = art.monte_carlo is not None
    has_wf = art.walk_forward is not None
    has_rc = art.whites_rc is not None

    # ---- Section A: performance ----
    perf_charts = {
        "equity":       _render(chart_equity_curve(art.equity, art.benchmark)),
        "cumret":       _render(chart_cumulative_return(art.equity, art.benchmark)),
        "excess":       _render(chart_excess_return(art.equity, art.benchmark))
                        if art.benchmark is not None else "",
        "rolling_cagr": _render(chart_rolling_cagr(art.equity)),
        "annual":       _render(chart_annual_returns(art.equity)),
        "monthly":      _render(chart_monthly_heatmap(art.equity)),
        "ret_dist":     _render(chart_return_distribution(art.returns)),
    }

    # ---- Section B: risk ----
    risk_charts = {
        "vol":  _render(chart_rolling_volatility(art.equity)),
        "var":  _render(chart_rolling_var(art.equity)),
        "qq":   _render(chart_qq_plot(art.returns)),
        "tail": _render(chart_rolling_tail_ratio(art.equity)),
    }

    # ---- Section C: drawdowns ----
    dd_charts = {
        "underwater": _render(chart_drawdown(art.equity)),
        "top_dd":     _render(chart_top_drawdowns(art.equity)),
    }
    dd_table = top_drawdowns_table(art.equity, top_n=10)
    dd_html = (dd_table.to_html(index=False, classes="trades-table", border=0)
               if not dd_table.empty else "<p class='muted'>No drawdowns</p>")

    # ---- Section D: trades ----
    trade_charts: dict[str, str] = {}
    if has_trades:
        trade_charts = {
            "pnl_dist": _render(chart_trade_pnl_distribution(art.trades)),
            "cum_pnl":  _render(chart_cumulative_trade_pnl(art.trades)),
            "holding":  _render(chart_holding_period_distribution(art.trades)),
            "streaks":  _render(chart_consecutive_streaks(art.trades)),
            "win_loss": _render(chart_win_loss_breakdown(art.trades)),
            "timeline": _render(chart_trade_timeline(art.trades)),
        }
        trades_head = art.trades.head(50).to_html(
            index=False, classes="trades-table", border=0
        )
    else:
        trades_head = "<p class='muted'>No trades recorded</p>"

    # ---- Section E: Monte Carlo ----
    mc_charts: dict[str, str] = {}
    if has_mc:
        mc_charts = {
            "fan":      _render(chart_mc_fan_paths(art.monte_carlo)),
            "terminal": _render(chart_mc_terminal_wealth(art.monte_carlo)),
            "drawdown": _render(chart_mc_drawdown_distribution(art.monte_carlo)),
            "null":     _render(chart_mc_null_sharpe(art.monte_carlo)),
            "iid":      _render(chart_mc_iid_ci(art.monte_carlo)),
            "trade":    _render(chart_mc_trade_ci(art.monte_carlo)),
            "sweep":    _render(chart_mc_block_sweep(art.monte_carlo)),
            "cagr":     _render(chart_mc_cagr_ci(art.monte_carlo)),
            "ruin":     _render(chart_mc_prob_ruin(art.monte_carlo)),
        }

    # ---- Section F: walk-forward ----
    wf_charts: dict[str, str] = {}
    if has_wf:
        wf_charts = {
            "scatter": _render(chart_wf_is_vs_oos_scatter(art.walk_forward_windows)),
            "oos_ser": _render(chart_wf_oos_sharpe_series(art.walk_forward_windows)),
            "excess":  _render(chart_wf_excess_sharpe(art.walk_forward_windows)),
            "counts":  _render(chart_wf_trade_counts(art.walk_forward_windows)),
            "summary": _render(chart_wf_summary_bars(art.walk_forward)),
        }

    # ---- Section G: White's RC ----
    rc_charts: dict[str, str] = {}
    if has_rc:
        rc_charts = {
            "v_dist": _render(chart_rc_v_distribution(art.whites_rc)),
            "top":    _render(chart_rc_top_combos(art.whites_rc)),
            "combo":  _render(chart_rc_combo_distribution(art.whites_rc)),
        }

    # ---- Section H: regime ----
    regime_charts = {
        "overlay":  _render(chart_regime_overlay(art.equity)),
        "perf":     _render(chart_regime_performance(art.equity)),
        "bullbear": _render(chart_bull_bear_performance(art.equity, art.benchmark)),
        "beta":     _render(chart_rolling_beta(art.equity, art.benchmark)),
    }

    # ---- render ----
    template = _jinja_env.get_template("tier2.html")
    html = template.render(
        manifest=art.manifest,
        run_id=art.run_id,
        kpis=kpis,
        metrics_rows=_metrics_table(art.metrics),
        verdict=verdict,
        perf=perf_charts,
        risk=risk_charts,
        dd=dd_charts,
        dd_table=dd_html,
        trade=trade_charts,
        trades_head=trades_head,
        mc=mc_charts,
        wf=wf_charts,
        rc=rc_charts,
        regime=regime_charts,
        has_benchmark=art.benchmark is not None,
        has_trades=has_trades,
        has_mc=has_mc,
        has_wf=has_wf,
        has_rc=has_rc,
        wf_aggregate=art.walk_forward or {},
        rc_aggregate=art.whites_rc or {},
    )
    output_path.write_text(html)
    return output_path