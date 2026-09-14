"""
Tier 1 — Executive tearsheet.

One page. The report a portfolio manager reads before deciding whether
to look at the full research report.
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
from jinja2 import Template

from reporting.engine import ReportEngine, RunArtifacts
from reporting.charts.performance import (
    chart_equity_curve,
    chart_cumulative_return,
    chart_excess_return,
    chart_rolling_cagr,
    chart_annual_returns,
    chart_monthly_heatmap,
    chart_return_distribution,
)
from reporting.charts.risk import (
    chart_rolling_volatility,
    chart_rolling_var,
    chart_qq_plot,
    chart_rolling_tail_ratio,
    chart_drawdown,
    chart_top_drawdowns,
    top_drawdowns_table,
)


TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "tier1.html"


# ---- formatting helpers ---------------------------------------------

def _fmt_pct(x, d=2) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x*100:+.{d}f}%"


def _fmt_ratio(x, d=3) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x:+.{d}f}"


def _fmt_num(x) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    if isinstance(x, (int, np.integer)):
        return f"{int(x):,}"
    if isinstance(x, float):
        return f"{x:,.4f}" if abs(x) < 100 else f"{x:,.0f}"
    return str(x)


def _cls(x) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "neutral"
    return "pos" if x > 0 else ("neg" if x < 0 else "neutral")


# ---- KPI tiles -------------------------------------------------------

def kpi_tiles(metrics: dict) -> list[tuple[str, str, str]]:
    return [
        ("Sharpe",       _fmt_ratio(metrics.get("sharpe")),   _cls(metrics.get("sharpe"))),
        ("Sortino",      _fmt_ratio(metrics.get("sortino")),  _cls(metrics.get("sortino"))),
        ("CAGR",         _fmt_pct(metrics.get("CAGR")),       _cls(metrics.get("CAGR"))),
        ("Max Drawdown", _fmt_pct(metrics.get("max_drawdown")), _cls(metrics.get("max_drawdown"))),
        ("Calmar",       _fmt_ratio(metrics.get("calmar")),   _cls(metrics.get("calmar"))),
        ("Volatility",   _fmt_pct(metrics.get("volatility")), "neutral"),
    ]


# ---- verdict ---------------------------------------------------------

def build_verdict(art: RunArtifacts) -> dict:
    """
    Combine WF + excess Sharpe + RC into a structured verdict.
    """
    verdict = {
        "wf_robust": "—",
        "has_edge": "—",
        "rc_significant": "—",
        "summary": "No walk-forward or cross-asset validation available.",
    }

    # walk-forward
    wf = art.walk_forward
    if wf is not None:
        robust = wf.get("robust", False)
        verdict["wf_robust"] = "YES" if robust else "NO"

        chained_excess = wf.get("chained_OOS_excess_sharpe")
        has_edge = wf.get("has_edge", False)
        if chained_excess is None or (isinstance(chained_excess, float) and np.isnan(chained_excess)):
            verdict["has_edge"] = "—"
        else:
            verdict["has_edge"] = "YES" if has_edge else "NO"

        if robust and has_edge:
            verdict["summary"] = (
                "Walk-forward robust with positive excess Sharpe. Real edge."
            )
        elif robust and not has_edge:
            verdict["summary"] = (
                "Walk-forward robust, but no excess return over a passive "
                "same-exposure position. Beta capture, not alpha."
            )
        else:
            verdict["summary"] = (
                "Fails walk-forward robustness. Overfit to the full sample."
            )

    # White's RC
    rc = art.whites_rc
    if rc is not None:
        p = rc.get("p_value")
        if p is not None:
            verdict["rc_significant"] = "YES" if p < 0.05 else "NO"
            verdict["rc_p_value"] = p
            verdict["rc_best_combo"] = rc.get("best_combo", "—")

    return verdict


# ---- chart renderer --------------------------------------------------

def _render(fig) -> str:
    if fig is None:
        return ""
    return fig.to_html(
        include_plotlyjs=False,
        full_html=False,
        config={"displayModeBar": False, "responsive": True},
    )


# ---- main entry ------------------------------------------------------

def build_tier1(
    run_dir: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    art = ReportEngine(run_dir).load()
    output_path = Path(output_path) if output_path else (
        art.run_dir / "report_executive.html"
    )

    # KPIs
    kpis = kpi_tiles(art.metrics)
    verdict = build_verdict(art)

    # charts
    charts = {
        "equity":       _render(chart_equity_curve(art.equity, art.benchmark)),
        "cumret":       _render(chart_cumulative_return(art.equity, art.benchmark)),
        "excess":       _render(chart_excess_return(art.equity, art.benchmark))
                        if art.benchmark is not None else "",
        "rolling_cagr": _render(chart_rolling_cagr(art.equity)),
        "annual":       _render(chart_annual_returns(art.equity)),
        "monthly":      _render(chart_monthly_heatmap(art.equity)),
        "ret_dist":     _render(chart_return_distribution(art.returns)),
        "vol":          _render(chart_rolling_volatility(art.equity)),
        "var":          _render(chart_rolling_var(art.equity)),
        "qq":           _render(chart_qq_plot(art.returns)),
        "tail":         _render(chart_rolling_tail_ratio(art.equity)),
        "drawdown":     _render(chart_drawdown(art.equity)),
        "top_dd":       _render(chart_top_drawdowns(art.equity)),
    }

    # tables
    top_dd_df = top_drawdowns_table(art.equity, top_n=10)
    top_dd_html = (
        top_dd_df.to_html(index=False, classes="trades-table", border=0)
        if not top_dd_df.empty else "<p class='muted'>No drawdowns</p>"
    )

    metrics_rows = []
    for key in sorted(art.metrics.keys()):
        v = art.metrics[key]
        if isinstance(v, float) and np.isnan(v):
            formatted = "—"
        elif key in {"CAGR", "volatility", "max_drawdown", "avg_drawdown",
                     "VaR_95", "VaR_99", "CVaR_95", "CVaR_99",
                     "expectancy_pct", "avg_win_pct", "avg_loss_pct",
                     "win_rate"}:
            formatted = _fmt_pct(v) if isinstance(v, (int, float)) else str(v)
        else:
            formatted = _fmt_num(v)
        metrics_rows.append((key, formatted))

    template = Template(TEMPLATE_PATH.read_text())
    html = template.render(
        manifest=art.manifest,
        run_id=art.run_id,
        kpis=kpis,
        metrics_rows=metrics_rows,
        verdict=verdict,
        charts=charts,
        top_dd_table=top_dd_html,
        has_benchmark=art.benchmark is not None,
        has_mc=art.monte_carlo is not None,
        has_wf=art.walk_forward is not None,
        has_rc=art.whites_rc is not None,
    )
    output_path.write_text(html)
    return output_path