"""
White's Reality Check charts.
"""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go

from reporting.theme import apply_theme, empty_figure, COLORS


# ---- 31. V-statistic distribution ----------------------------------

def chart_rc_v_distribution(rc: dict | None) -> go.Figure:
    if not rc:
        return empty_figure("White's RC results not available")

    obs = rc.get("V_observed")
    mean = rc.get("V_bootstrap_mean")
    p95 = rc.get("V_bootstrap_p95")
    p99 = rc.get("V_bootstrap_p99")
    p = rc.get("p_value")

    if obs is None or mean is None:
        return empty_figure()

    lo = min(v for v in (obs, mean, p95, p99) if v is not None)
    hi = max(v for v in (obs, mean, p95, p99) if v is not None)
    span = max(hi - lo, 1e-6)
    pad = 0.15 * span

    fig = go.Figure()

    # Bootstrap distribution band
    if p95 is not None and p99 is not None:
        fig.add_trace(go.Scatter(
            x=[mean, p95, p95, mean, mean],
            y=[0.35, 0.35, 0.65, 0.65, 0.35],
            fill="toself",
            fillcolor="rgba(217,119,87,0.15)",
            line=dict(color=COLORS["accent"], width=1),
            name="Bootstrap (to p95)",
            hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=[p95, p99, p99, p95, p95],
            y=[0.35, 0.35, 0.65, 0.65, 0.35],
            fill="toself",
            fillcolor="rgba(217,119,87,0.30)",
            line=dict(color=COLORS["accent"], width=1),
            name="Tail (p95 to p99)",
            hoverinfo="skip",
        ))

    # Mean marker
    fig.add_trace(go.Scatter(
        x=[mean], y=[0.5],
        mode="markers",
        marker=dict(size=10, color=COLORS["text_muted"], symbol="diamond"),
        name="Bootstrap mean",
        hovertemplate=f"{mean:.4f}<extra>Mean</extra>",
    ))

    # Observed marker
    fig.add_trace(go.Scatter(
        x=[obs], y=[0.5],
        mode="markers",
        marker=dict(size=18, color=COLORS["accent"], symbol="line-ns",
                    line=dict(width=3, color=COLORS["accent"])),
        name="Observed V",
        hovertemplate=f"{obs:.4f}<extra>Observed</extra>",
    ))

    ann = f"p = {p:.4f}" if p is not None else ""
    if ann:
        fig.add_annotation(
            x=1, y=1.15, xref="paper", yref="paper",
            text=ann, showarrow=False,
            font=dict(family="ui-monospace, monospace", size=11,
                      color=COLORS["text_muted"]),
            xanchor="right", yanchor="bottom",
        )

    apply_theme(fig, height=180)
    fig.update_xaxes(range=[lo - pad, hi + pad], title_text="V statistic")
    fig.update_yaxes(visible=False, range=[0, 1])
    return fig


# ---- 32. top combos bar chart ---------------------------------------

def chart_rc_top_combos(rc: dict | None) -> go.Figure:
    if not rc or "top_5_combos" not in rc:
        return empty_figure()

    combos = rc["top_5_combos"]
    if not combos:
        return empty_figure()

    labels = [c["label"] for c in combos][::-1]
    values = [c["annualized_excess_return"] * 100 for c in combos][::-1]
    colors = [COLORS["positive"] if v > 0 else COLORS["negative"] for v in values]

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=colors,
        marker_line_color=COLORS["bg"], marker_line_width=0.5,
        text=[f"{v:+.2f}%" for v in values],
        textposition="outside",
        textfont=dict(size=10, color=COLORS["text"]),
        hovertemplate="%{y}<br>%{x:+.2f}% annualized<extra></extra>",
    ))
    fig.add_vline(x=0, line_dash="dash", line_color=COLORS["text_subtle"])
    apply_theme(fig, height=max(240, 60 + 42 * len(labels)))
    fig.update_xaxes(title_text="Annualized excess return (%)")
    return fig


# ---- 33. positive vs negative combos -------------------------------

def chart_rc_combo_distribution(rc: dict | None) -> go.Figure:
    if not rc:
        return empty_figure()

    n_pos = rc.get("n_combos_with_positive_mean")
    n_neg = rc.get("n_combos_with_negative_mean")
    if n_pos is None or n_neg is None:
        return empty_figure()

    fig = go.Figure(go.Bar(
        x=[n_pos, n_neg],
        y=["Positive", "Negative"],
        orientation="h",
        marker_color=[COLORS["positive"], COLORS["negative"]],
        marker_line_color=COLORS["bg"], marker_line_width=0.5,
        text=[str(n_pos), str(n_neg)],
        textposition="outside",
        textfont=dict(size=12, color=COLORS["text"]),
        hovertemplate="%{y}: %{x} combos<extra></extra>",
    ))
    apply_theme(fig, height=180)
    fig.update_xaxes(title_text="Number of combos")
    return fig