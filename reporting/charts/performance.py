"""
Performance charts.

All functions accept pandas Series/DataFrames and return go.Figure.
They never raise on empty/short input — they return an empty themed
figure instead.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from reporting.theme import apply_theme, empty_figure, COLORS


# ---- 1. equity curve ------------------------------------------------

def chart_equity_curve(
    equity: pd.Series,
    benchmark: pd.Series | None = None,
    log_scale: bool = False,
) -> go.Figure:
    if len(equity) < 2:
        return empty_figure("Equity curve: not enough data")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity.index, y=equity.values,
        name="Strategy", mode="lines",
        line=dict(color=COLORS["accent"], width=2),
        hovertemplate="%{y:,.0f}<extra>Strategy</extra>",
    ))
    if benchmark is not None:
        bm = benchmark.reindex(equity.index).ffill()
        fig.add_trace(go.Scatter(
            x=bm.index, y=bm.values,
            name="Buy & Hold", mode="lines",
            line=dict(color=COLORS["bench"], width=1.5, dash="dot"),
            hovertemplate="%{y:,.0f}<extra>Benchmark</extra>",
        ))
    apply_theme(fig)
    fig.update_yaxes(title_text="Equity", type="log" if log_scale else "linear")
    return fig


# ---- 2. cumulative return -------------------------------------------

def chart_cumulative_return(
    equity: pd.Series,
    benchmark: pd.Series | None = None,
) -> go.Figure:
    if len(equity) < 2:
        return empty_figure()

    strat = equity / equity.iloc[0] - 1.0
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=strat.index, y=strat.values * 100.0,
        name="Strategy", mode="lines",
        line=dict(color=COLORS["accent"], width=2),
        hovertemplate="%{y:.2f}%<extra>Strategy</extra>",
    ))
    if benchmark is not None:
        bm = benchmark.reindex(equity.index).ffill()
        bm = bm / bm.iloc[0] - 1.0
        fig.add_trace(go.Scatter(
            x=bm.index, y=bm.values * 100.0,
            name="Buy & Hold", mode="lines",
            line=dict(color=COLORS["bench"], width=1.5, dash="dot"),
            hovertemplate="%{y:.2f}%<extra>Benchmark</extra>",
        ))
    fig.add_hline(y=0, line_dash="dash", line_color=COLORS["neutral"])
    apply_theme(fig)
    fig.update_yaxes(title_text="Cumulative return (%)")
    return fig


# ---- 3. excess return over benchmark --------------------------------

def chart_excess_return(
    equity: pd.Series,
    benchmark: pd.Series,
) -> go.Figure:
    if len(equity) < 2 or benchmark is None:
        return empty_figure("Excess return: benchmark not available")

    sr = equity.pct_change().fillna(0.0)
    br = benchmark.reindex(equity.index).ffill().pct_change().fillna(0.0)
    excess = sr - br
    cum = (1 + excess).cumprod() - 1.0

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=cum.index, y=cum.values * 100.0,
        mode="lines",
        line=dict(color=COLORS["positive"], width=2),
        fill="tozeroy",
        fillcolor="rgba(63,185,80,0.12)",
        hovertemplate="%{y:.2f}%<extra>Excess</extra>",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color=COLORS["neutral"])
    apply_theme(fig)
    fig.update_yaxes(title_text="Cumulative excess return (%)")
    return fig


# ---- 4. rolling CAGR -------------------------------------------------

def chart_rolling_cagr(
    equity: pd.Series,
    windows: tuple[int, ...] = (252, 756),
    periods_per_year: float = 252.0,
) -> go.Figure:
    if len(equity) < min(windows) + 2:
        return empty_figure("Rolling CAGR: not enough data")

    fig = go.Figure()
    colors = [COLORS["accent"], COLORS["warning"], COLORS["positive"]]
    for i, w in enumerate(windows):
        if len(equity) < w + 1:
            continue
        ratio = equity / equity.shift(w)
        cagr = ratio ** (periods_per_year / w) - 1.0
        fig.add_trace(go.Scatter(
            x=cagr.index, y=cagr.values * 100.0,
            name=f"{w // 252}Y",
            mode="lines",
            line=dict(color=colors[i % len(colors)], width=1.8),
            hovertemplate="%{y:.2f}%<extra>" + f"{w // 252}Y CAGR</extra>",
        ))
    fig.add_hline(y=0, line_dash="dash", line_color=COLORS["neutral"])
    apply_theme(fig)
    fig.update_yaxes(title_text="Rolling CAGR (%)")
    return fig


# ---- 5. annual returns -----------------------------------------------

def chart_annual_returns(equity: pd.Series) -> go.Figure:
    if len(equity) < 2:
        return empty_figure()

    yearly = equity.resample("YE").last()
    rets = yearly.pct_change().dropna()
    if rets.empty:
        return empty_figure()

    years = [d.year for d in rets.index]
    values = rets.values * 100.0
    colors = [COLORS["positive"] if v >= 0 else COLORS["negative"] for v in values]

    fig = go.Figure(go.Bar(
        x=years, y=values,
        marker_color=colors,
        marker_line_color=COLORS["bg"],
        marker_line_width=0.5,
        text=[f"{v:+.1f}%" for v in values],
        textposition="outside",
        textfont=dict(size=10, color=COLORS["text"]),
        hovertemplate="%{x}: %{y:.2f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_color=COLORS["neutral"], line_width=0.5)
    apply_theme(fig)
    fig.update_yaxes(title_text="Annual return (%)")
    return fig


# ---- 6. monthly heatmap ---------------------------------------------

_MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def chart_monthly_heatmap(equity: pd.Series) -> go.Figure:
    if len(equity) < 30:
        return empty_figure("Monthly heatmap: not enough data")

    monthly = equity.resample("ME").last()
    rets = monthly.pct_change().dropna()
    if rets.empty:
        return empty_figure()

    df = pd.DataFrame({
        "year":  rets.index.year,
        "month": rets.index.month,
        "ret":   rets.values,
    })
    pivot = df.pivot(index="year", columns="month", values="ret")
    pivot = pivot.reindex(columns=range(1, 13))

    z = pivot.values * 100.0
    text = np.where(np.isnan(z), "", np.round(z, 1).astype(str))
    years = pivot.index.tolist()

    fig = go.Figure(go.Heatmap(
        z=z,
        x=_MONTH_LABELS,
        y=years,
        colorscale=[[0.0, COLORS["negative"]],
                    [0.5, COLORS["bg"]],
                    [1.0, COLORS["positive"]]],
        zmid=0,
        text=text,
        texttemplate="%{text}%",
        textfont=dict(size=10, color=COLORS["text"]),
        colorbar=dict(title="%", tickfont=dict(color=COLORS["text"]),
                      len=0.8),
        hovertemplate="%{y} %{x}<br>%{z:.2f}%<extra></extra>",
    ))
    apply_theme(fig, height=max(220, 60 + 26 * len(years)))
    fig.update_layout(
        yaxis=dict(autorange="reversed", gridcolor=COLORS["border"],
                   linecolor=COLORS["border"]),
    )
    fig.update_yaxes(tickmode="array", tickvals=years)
    return fig


# ---- 7. return distribution -----------------------------------------

def chart_return_distribution(
    returns: pd.Series,
    bins: int = 80,
) -> go.Figure:
    if len(returns) < 10:
        return empty_figure()

    r = returns.dropna().values
    mu, sd = float(np.mean(r)), float(np.std(r, ddof=1))

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=r * 100.0,
        nbinsx=bins,
        name="Observed",
        marker_color=COLORS["accent"],
        marker_line_color=COLORS["bg"],
        marker_line_width=0.4,
        opacity=0.85,
        histnorm="probability density",
        hovertemplate="%{x:.3f}%<br>density: %{y:.2f}<extra></extra>",
    ))
    # normal overlay
    xs = np.linspace(r.min(), r.max(), 400) * 100.0
    pdf = (1.0 / (sd * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((xs/100.0 - mu) / sd) ** 2) / 100.0
    fig.add_trace(go.Scatter(
        x=xs, y=pdf * 100.0,
        name="Normal fit",
        mode="lines",
        line=dict(color=COLORS["warning"], width=1.5, dash="dash"),
        hovertemplate="%{x:.2f}%<extra>Normal</extra>",
    ))
    fig.add_vline(x=0, line_dash="dot", line_color=COLORS["neutral"])
    apply_theme(fig)
    fig.update_xaxes(title_text="Daily return (%)")
    fig.update_yaxes(title_text="Density")
    return fig