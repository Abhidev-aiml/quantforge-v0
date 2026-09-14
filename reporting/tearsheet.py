"""
Static HTML tearsheet generator.

Reads artifacts from a canonical run directory
(results/runs/<run_id>/) and produces a self-contained report.html
with interactive Plotly charts and a minimalist dark theme.

Usage:
    from reporting.tearsheet import build_tearsheet
    build_tearsheet("results/runs/20260913_090414_457833")
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from jinja2 import Template


TEMPLATE_PATH = Path(__file__).parent / "templates" / "tearsheet.html"


# ---------------------------------------------------------------- public API

def build_tearsheet(
    run_dir: str | Path,
    output_path: Optional[str | Path] = None,
    benchmark_equity: Optional[pd.Series] = None,
) -> Path:
    """Build a self-contained HTML tearsheet from a run directory.

    Args:
        run_dir:           path to results/runs/<run_id>/
        output_path:       default: <run_dir>/report.html
        benchmark_equity:  optional benchmark equity Series to overlay

    Returns:
        Path to the written report.html
    """
    run_dir = Path(run_dir)
    if not run_dir.exists():
        raise FileNotFoundError(f"run directory not found: {run_dir}")

    manifest_path = run_dir / "manifest.json"
    metrics_path = run_dir / "metrics.json"

    if not manifest_path.exists():
        raise FileNotFoundError(f"missing manifest: {manifest_path}")
    if not metrics_path.exists():
        raise FileNotFoundError(f"missing metrics: {metrics_path}")

    manifest = _load_json(manifest_path)
    metrics = _load_json(metrics_path)
    equity = _load_equity(run_dir / "equity.csv")
    trades = _load_trades(run_dir / "trades.csv")

    charts = {
        "equity":         _render_chart(_chart_equity(equity, benchmark_equity)),
        "drawdown":       _render_chart(_chart_drawdown(equity)),
        "monthly":        _render_chart(_chart_monthly_heatmap(equity)),
        "rolling_sharpe": _render_chart(_chart_rolling_sharpe(equity)),
        "trade_hist":     _render_chart(_chart_trade_distribution(trades))
                          if trades is not None and not trades.empty else "",
    }

    template = Template(TEMPLATE_PATH.read_text())
    html = template.render(
        manifest=manifest,
        kpis=_kpi_tiles(metrics),
        metrics_rows=_format_metrics_table(metrics),
        charts=charts,
        has_trades=trades is not None and not trades.empty,
        trades_head=trades.head(50) if trades is not None and not trades.empty else None,
    )

    if output_path is None:
        output_path = run_dir / "report.html"
    output_path = Path(output_path)
    output_path.write_text(html)
    return output_path


# ---------------------------------------------------------------- loaders

def _load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _load_equity(path: Path) -> pd.Series:
    if not path.exists():
        raise FileNotFoundError(f"missing equity: {path}")
    df = pd.read_csv(path)
    # Locate the timestamp column: "timestamp" preferred, "date" fallback,
    # otherwise assume the first column is the index.
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
    elif "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    else:
        first = df.columns[0]
        df[first] = pd.to_datetime(df[first])
        df = df.set_index(first)
    # First numeric column is the equity value
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) == 0:
        raise ValueError(f"no numeric column found in {path}")
    return df[numeric_cols[0]].astype(float).sort_index()


def _load_trades(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    df = pd.read_csv(path)
    for col in ("entry_ts", "exit_ts"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df


# ---------------------------------------------------------------- formatting

def _fmt_pct(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v*100:+.2f}%"


def _fmt_ratio(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:+.3f}"


def _fmt_num(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if isinstance(v, (int, np.integer)):
        return f"{int(v):,}"
    if isinstance(v, float):
        if abs(v) >= 100:
            return f"{v:,.0f}"
        return f"{v:.4f}"
    return str(v)


def _cls_num(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "neutral"
    if v > 0:
        return "pos"
    if v < 0:
        return "neg"
    return "neutral"


def _cls_ratio(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "neutral"
    return "pos" if v > 0 else "neg"


def _kpi_tiles(metrics: dict) -> list[tuple[str, str, str]]:
    """Return list of (label, value_str, css_class) for top-line KPIs."""
    return [
        ("Sharpe",       _fmt_ratio(metrics.get("sharpe")),      _cls_ratio(metrics.get("sharpe"))),
        ("CAGR",         _fmt_pct(metrics.get("CAGR")),          _cls_num(metrics.get("CAGR"))),
        ("Max Drawdown", _fmt_pct(metrics.get("max_drawdown")),  _cls_num(metrics.get("max_drawdown"))),
        ("Calmar",       _fmt_ratio(metrics.get("calmar")),      _cls_ratio(metrics.get("calmar"))),
        ("Volatility",   _fmt_pct(metrics.get("volatility")),    "neutral"),
        ("Sortino",      _fmt_ratio(metrics.get("sortino")),     _cls_ratio(metrics.get("sortino"))),
    ]


_PCT_KEYS = {
    "CAGR", "volatility", "max_drawdown", "avg_drawdown",
    "VaR_95", "VaR_99", "CVaR_95", "CVaR_99",
    "expectancy_pct", "avg_win_pct", "avg_loss_pct",
    "win_rate",
}


def _format_metrics_table(metrics: dict) -> list[tuple[str, str]]:
    """Return sorted (key, formatted_value) pairs."""
    rows = []
    for key in sorted(metrics.keys()):
        v = metrics[key]
        if isinstance(v, float) and np.isnan(v):
            formatted = "—"
        elif key in _PCT_KEYS and isinstance(v, (int, float)):
            formatted = _fmt_pct(v)
        elif isinstance(v, float):
            formatted = _fmt_ratio(v) if abs(v) < 100 else f"{v:,.2f}"
        elif isinstance(v, int):
            formatted = f"{v:,}"
        else:
            formatted = str(v)
        rows.append((key, formatted))
    return rows


# ---------------------------------------------------------------- charts

def _dark_layout() -> dict:
    """Shared Plotly layout settings for the dark minimalist theme."""
    return dict(
        paper_bgcolor="#161b22",
        plot_bgcolor="#0d1117",
        font=dict(color="#c9d1d9", family="ui-monospace, SFMono-Regular, Menlo, monospace", size=12),
        margin=dict(l=50, r=20, t=20, b=40),
        xaxis=dict(gridcolor="#30363d", linecolor="#30363d"),
        yaxis=dict(gridcolor="#30363d", linecolor="#30363d"),
        showlegend=True,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
        hovermode="x unified",
    )


def _chart_equity(equity: pd.Series, benchmark: Optional[pd.Series] = None) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity.index, y=equity.values,
        name="Strategy", mode="lines",
        line=dict(color="#58a6ff", width=2),
    ))
    if benchmark is not None:
        bm = benchmark.reindex(equity.index).ffill()
        # Normalize benchmark to same start value
        bm = bm / bm.iloc[0] * equity.iloc[0]
        fig.add_trace(go.Scatter(
            x=bm.index, y=bm.values,
            name="Benchmark", mode="lines",
            line=dict(color="#8b949e", width=1.5, dash="dot"),
        ))
    fig.update_layout(**_dark_layout())
    fig.update_yaxes(title_text="Equity")
    return fig


def _chart_drawdown(equity: pd.Series) -> go.Figure:
    dd = (equity / equity.cummax() - 1.0) * 100.0
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dd.index, y=dd.values,
        fill="tozeroy", mode="lines",
        line=dict(color="#f85149", width=1),
        fillcolor="rgba(248, 81, 73, 0.25)",
        name="Drawdown %",
    ))
    fig.update_layout(**_dark_layout())
    fig.update_layout(showlegend=False)
    fig.update_yaxes(title_text="Drawdown %")
    return fig


def _monthly_returns(equity: pd.Series) -> Optional[pd.DataFrame]:
    monthly = equity.resample("ME").last()
    rets = monthly.pct_change().dropna()
    if len(rets) == 0:
        return None
    df = pd.DataFrame({
        "year": rets.index.year,
        "month": rets.index.month,
        "return": rets.values,
    })
    return df.pivot(index="year", columns="month", values="return")


def _chart_monthly_heatmap(equity: pd.Series) -> go.Figure:
    monthly = _monthly_returns(equity)
    if monthly is None or monthly.empty:
        return go.Figure().update_layout(**_dark_layout())

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    years = monthly.index.tolist()
    z = (monthly.reindex(columns=range(1, 13)).values * 100.0)

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=months,
        y=years,
        colorscale=[[0.0, "#f85149"], [0.5, "#0d1117"], [1.0, "#3fb950"]],
        zmid=0,
        text=np.where(np.isnan(z), "", np.round(z, 1).astype(str)),
        texttemplate="%{text}%",
        textfont=dict(size=10, color="#c9d1d9"),
        colorbar=dict(title="%", tickfont=dict(color="#c9d1d9")),
        hovertemplate="%{y} %{x}<br>%{z:.2f}%<extra></extra>",
    ))
    fig.update_layout(**_dark_layout())
    fig.update_layout(
        height=max(200, 80 + 28 * len(years)),
        yaxis=dict(autorange="reversed", gridcolor="#30363d", linecolor="#30363d"),
    )
    fig.update_yaxes(tickmode="array", tickvals=years)
    return fig


def _chart_rolling_sharpe(equity: pd.Series, window: int = 252) -> go.Figure:
    rets = equity.pct_change()
    if len(rets) < window:
        return go.Figure().update_layout(**_dark_layout())
    rolling_mean = rets.rolling(window).mean()
    rolling_std = rets.rolling(window).std(ddof=1)
    rs = (rolling_mean / rolling_std) * np.sqrt(252)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=rs.index, y=rs.values,
        mode="lines",
        line=dict(color="#58a6ff", width=1.5),
        name="Rolling Sharpe",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#30363d")
    fig.update_layout(**_dark_layout())
    fig.update_layout(showlegend=False)
    fig.update_yaxes(title_text="Sharpe (annualized)")
    return fig


def _chart_trade_distribution(trades: Optional[pd.DataFrame]) -> go.Figure:
    fig = go.Figure()
    if trades is None or trades.empty or "pnl" not in trades.columns:
        return fig.update_layout(**_dark_layout())

    pnl = trades["pnl"].values
    fig.add_trace(go.Histogram(
        x=pnl,
        nbinsx=40,
        marker_color="#58a6ff",
        marker_line_color="#0d1117",
        marker_line_width=0.5,
        name="PnL",
        hovertemplate="PnL: %{x:.2f}<br>Count: %{y}<extra></extra>",
    ))
    fig.add_vline(x=0, line_dash="dash", line_color="#8b949e")
    fig.update_layout(**_dark_layout())
    fig.update_layout(showlegend=False)
    fig.update_xaxes(title_text="Trade PnL")
    fig.update_yaxes(title_text="Count")
    return fig


def _render_chart(fig: go.Figure) -> str:
    """Serialize a Plotly figure to an embeddable div (no plotly.js)."""
    if fig is None:
        return ""
    return fig.to_html(
        include_plotlyjs=False,
        full_html=False,
        config={"displayModeBar": False, "responsive": True},
    )