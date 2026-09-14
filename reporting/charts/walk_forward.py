"""
Walk-forward validation charts.

Input: walk_forward_windows.csv (per-window metrics) and
walk_forward_aggregate.json (aggregate statistics).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from reporting.theme import apply_theme, empty_figure, COLORS


def _prepare(windows: pd.DataFrame | None) -> pd.DataFrame | None:
    if windows is None or windows.empty:
        return None
    w = windows.copy()
    for col in ("is_start", "is_end", "oos_start", "oos_end"):
        if col in w.columns:
            w[col] = pd.to_datetime(w[col], errors="coerce")
    return w


# ---- 26. IS vs OOS Sharpe scatter ----------------------------------

def chart_wf_is_vs_oos_scatter(windows: pd.DataFrame | None) -> go.Figure:
    w = _prepare(windows)
    if w is None or len(w) < 2:
        return empty_figure("Walk-forward windows not available")

    is_s = w["is_sharpe"].values
    oos_s = w["oos_sharpe"].values

    valid = ~(np.isnan(is_s) | np.isnan(oos_s))
    is_s, oos_s = is_s[valid], oos_s[valid]
    if len(is_s) < 2:
        return empty_figure()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=is_s, y=oos_s,
        mode="markers",
        marker=dict(
            size=10,
            color=COLORS["accent"],
            line=dict(width=1.5, color=COLORS["bg"]),
            opacity=0.85,
        ),
        hovertemplate="IS: %{x:.3f}<br>OOS: %{y:.3f}<extra></extra>",
    ))

    lo = float(min(is_s.min(), oos_s.min()))
    hi = float(max(is_s.max(), oos_s.max()))
    fig.add_trace(go.Scatter(
        x=[lo, hi], y=[lo, hi],
        mode="lines",
        line=dict(color=COLORS["text_subtle"], width=1, dash="dash"),
        name="y = x",
        hoverinfo="skip",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=COLORS["border_strong"])
    fig.add_vline(x=0, line_dash="dot", line_color=COLORS["border_strong"])
    apply_theme(fig)
    fig.update_xaxes(title_text="In-sample Sharpe")
    fig.update_yaxes(title_text="Out-of-sample Sharpe")
    return fig


# ---- 27. OOS Sharpe per window -------------------------------------

def chart_wf_oos_sharpe_series(windows: pd.DataFrame | None) -> go.Figure:
    w = _prepare(windows)
    if w is None or len(w) < 2:
        return empty_figure()

    oos = w["oos_sharpe"].values
    colors = [COLORS["positive"] if v > 0 else COLORS["negative"] for v in oos]
    labels = [d.strftime("%Y") if pd.notna(d) else "" for d in w["oos_start"]]

    fig = go.Figure(go.Bar(
        x=labels, y=oos,
        marker_color=colors,
        marker_line_color=COLORS["bg"], marker_line_width=0.4,
        hovertemplate="%{x}<br>OOS Sharpe: %{y:.3f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_color=COLORS["text_subtle"], line_width=0.5)
    apply_theme(fig)
    fig.update_yaxes(title_text="OOS Sharpe")
    return fig


# ---- 28. excess Sharpe vs benchmark per window ---------------------

def chart_wf_excess_sharpe(windows: pd.DataFrame | None) -> go.Figure:
    w = _prepare(windows)
    if w is None or "oos_excess_sharpe" not in w.columns or len(w) < 2:
        return empty_figure()

    ex = w["oos_excess_sharpe"].values
    colors = [COLORS["positive"] if v > 0 else COLORS["negative"] for v in ex]
    labels = [d.strftime("%Y") if pd.notna(d) else "" for d in w["oos_start"]]

    fig = go.Figure(go.Bar(
        x=labels, y=ex,
        marker_color=colors,
        marker_line_color=COLORS["bg"], marker_line_width=0.4,
        hovertemplate="%{x}<br>Excess Sharpe: %{y:.3f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_color=COLORS["text_subtle"], line_width=0.5)
    apply_theme(fig)
    fig.update_yaxes(title_text="OOS excess Sharpe")
    return fig


# ---- 29. trade count per window ------------------------------------

def chart_wf_trade_counts(windows: pd.DataFrame | None) -> go.Figure:
    w = _prepare(windows)
    if w is None or "oos_n_trades" not in w.columns or len(w) < 2:
        return empty_figure()

    counts = w["oos_n_trades"].values
    labels = [d.strftime("%Y") if pd.notna(d) else "" for d in w["oos_start"]]
    colors = [COLORS["positive"] if c >= 5 else COLORS["warning"] for c in counts]

    fig = go.Figure(go.Bar(
        x=labels, y=counts,
        marker_color=colors,
        marker_line_color=COLORS["bg"], marker_line_width=0.4,
        hovertemplate="%{x}<br>%{y} trades<extra></extra>",
    ))
    fig.add_hline(y=5, line_dash="dash", line_color=COLORS["warning"],
                  annotation_text="low confidence",
                  annotation_position="right")
    apply_theme(fig)
    fig.update_yaxes(title_text="Trades in OOS window")
    return fig


# ---- 30. aggregate summary bars ------------------------------------

def chart_wf_summary_bars(wf_aggregate: dict | None) -> go.Figure:
    if not wf_aggregate:
        return empty_figure("Walk-forward aggregate not available")

    labels, values, colors = [], [], []

    def add(label, value, color=None):
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return
        labels.append(label)
        values.append(value)
        colors.append(color or COLORS["accent"])

    add("Mean IS",       wf_aggregate.get("mean_IS_sharpe"))
    add("Mean OOS",      wf_aggregate.get("mean_OOS_sharpe"))
    add("Chained OOS",   wf_aggregate.get("chained_OOS_sharpe"))
    add("Chained bench", wf_aggregate.get("chained_OOS_benchmark_sharpe"),
        COLORS["text_muted"])
    add("Chained excess", wf_aggregate.get("chained_OOS_excess_sharpe"),
        COLORS["positive"])

    if not labels:
        return empty_figure()

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=colors,
        marker_line_color=COLORS["bg"], marker_line_width=0.5,
        text=[f"{v:+.3f}" for v in values],
        textposition="outside",
        textfont=dict(size=11, color=COLORS["text"]),
        hovertemplate="%{y}: %{x:+.3f}<extra></extra>",
    ))
    fig.add_vline(x=0, line_dash="dash", line_color=COLORS["text_subtle"])
    apply_theme(fig, height=max(220, 60 + 40 * len(labels)))
    fig.update_xaxes(title_text="Sharpe")
    return fig