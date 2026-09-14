"""
Monte Carlo distribution charts.

Charts work from the summary statistics stored in monte_carlo.json.
Each function gracefully degrades when its input section is missing.

For distributions where we only have (mean, std, p05, p95), we draw a
horizontal band visual rather than a fake histogram. This is honest:
we show what the MC actually produced.
"""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go

from reporting.theme import apply_theme, empty_figure, COLORS


# ---- helpers --------------------------------------------------------

def _band_visualization(
    *,
    center: float,
    p05: float | None,
    p95: float | None,
    observed: float | None,
    title: str,
    x_label: str = "Value",
    annotation: str = "",
) -> go.Figure:
    """
    Draw a horizontal band showing (p05, center, p95) with an optional
    observed marker.
    """
    values = [v for v in (p05, center, observed) if v is not None]
    if not values:
        return empty_figure(f"{title}: no data")

    lo = min(values)
    hi = max(values)
    span = hi - lo if hi > lo else 1.0
    pad = 0.15 * span

    fig = go.Figure()

    # The 90% interval band
    if p05 is not None and p95 is not None:
        fig.add_trace(go.Scatter(
            x=[p05, p95, p95, p05, p05],
            y=[0.35, 0.35, 0.65, 0.65, 0.35],
            fill="toself",
            fillcolor="rgba(217,119,87,0.18)",
            line=dict(color=COLORS["accent"], width=1.5),
            name="90% interval",
            hovertemplate=f"[{p05:.3f}, {p95:.3f}]<extra>90% band</extra>",
        ))

    # Center marker
    fig.add_trace(go.Scatter(
        x=[center], y=[0.5],
        mode="markers",
        marker=dict(size=10, color=COLORS["text_muted"], symbol="diamond"),
        name="Mean",
        hovertemplate=f"{center:.3f}<extra>Mean</extra>",
    ))

    # Observed marker
    if observed is not None:
        fig.add_trace(go.Scatter(
            x=[observed], y=[0.5],
            mode="markers",
            marker=dict(size=16, color=COLORS["accent"], symbol="line-ns",
                        line=dict(width=3, color=COLORS["accent"])),
            name="Observed",
            hovertemplate=f"{observed:.3f}<extra>Observed</extra>",
        ))

    if annotation:
        fig.add_annotation(
            x=1, y=1.15, xref="paper", yref="paper",
            text=annotation, showarrow=False,
            font=dict(family="ui-monospace, monospace", size=11,
                      color=COLORS["text_muted"]),
            xanchor="right", yanchor="bottom",
        )

    apply_theme(fig, height=180)
    fig.update_xaxes(range=[lo - pad, hi + pad], title_text=x_label)
    fig.update_yaxes(visible=False, range=[0, 1])
    return fig


# ---- 20. null bootstrap Sharpe distribution ------------------------

def chart_mc_null_sharpe(mc: dict | None) -> go.Figure:
    if not mc or "null_bootstrap" not in mc:
        return empty_figure("Null bootstrap not available")

    nb = mc["null_bootstrap"]
    obs = nb.get("observed_sharpe")
    p = nb.get("p_value_one_sided")
    ann = f"p = {p:.4f}" if p is not None else ""

    return _band_visualization(
        center=nb["null_sharpe_mean"],
        p05=nb.get("null_sharpe_p05"),
        p95=nb.get("null_sharpe_p95"),
        observed=obs,
        title="Null Sharpe distribution",
        x_label="Sharpe",
        annotation=ann,
    )


# ---- 21. IID bootstrap CI -------------------------------------------

def chart_mc_iid_ci(mc: dict | None) -> go.Figure:
    if not mc or "iid_ci" not in mc:
        return empty_figure("IID CI not available")

    iid = mc["iid_ci"]
    return _band_visualization(
        center=iid.get("sharpe_p50", iid.get("sharpe_mean", 0.0)),
        p05=iid.get("sharpe_p05"),
        p95=iid.get("sharpe_p95"),
        observed=iid.get("real_sharpe"),
        title="IID bootstrap Sharpe CI",
        x_label="Sharpe",
        annotation="90% CI",
    )


# ---- 22. trade bootstrap CI ----------------------------------------

def chart_mc_trade_ci(mc: dict | None) -> go.Figure:
    if not mc or "trade_ci" not in mc:
        return empty_figure("Trade bootstrap not available (need >= 20 trades)")

    tb = mc["trade_ci"]
    return _band_visualization(
        center=tb.get("sharpe_p50", tb.get("sharpe_mean", 0.0)),
        p05=tb.get("sharpe_p05"),
        p95=tb.get("sharpe_p95"),
        observed=tb.get("real_sharpe"),
        title="Trade bootstrap Sharpe CI",
        x_label="Sharpe",
        annotation=f"{tb.get('n_trades', '?')} trades",
    )


# ---- 23. block-shuffle sweep ---------------------------------------

def chart_mc_block_sweep(mc: dict | None) -> go.Figure:
    if not mc or "signal_shuffle_sweep" not in mc:
        return empty_figure("Block shuffle sweep not available")

    sweep = mc["signal_shuffle_sweep"]
    if not sweep:
        return empty_figure()

    blocks = [r["block"] for r in sweep]
    pvals = [r["p_value"] for r in sweep]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=blocks, y=pvals,
        mode="lines+markers",
        line=dict(color=COLORS["accent"], width=2),
        marker=dict(size=10, color=COLORS["accent"],
                    line=dict(width=1.5, color=COLORS["bg"])),
        hovertemplate="block=%{x}<br>p=%{y:.4f}<extra></extra>",
    ))
    fig.add_hline(y=0.05, line_dash="dash", line_color=COLORS["negative"],
                  annotation_text="p = 0.05", annotation_position="right")
    fig.add_hline(y=0.10, line_dash="dot", line_color=COLORS["warning"],
                  annotation_text="p = 0.10", annotation_position="right")
    apply_theme(fig)
    fig.update_xaxes(title_text="Block size (bars)", type="log")
    fig.update_yaxes(title_text="p-value", range=[0, 1])
    return fig


# ---- 24. CAGR confidence interval ----------------------------------

def chart_mc_cagr_ci(mc: dict | None) -> go.Figure:
    if not mc:
        return empty_figure()

    iid = mc.get("iid_ci", {})
    tb = mc.get("trade_ci", {})
    real_cagr = iid.get("real_CAGR")
    iid_p05 = iid.get("cagr_p05")
    iid_p95 = iid.get("cagr_p95")
    tb_p05 = tb.get("cagr_p05")
    tb_p95 = tb.get("cagr_p95")

    if iid_p05 is None and tb_p05 is None:
        return empty_figure("No CAGR CI available")

    rows, lows, highs = [], [], []
    if iid_p05 is not None and iid_p95 is not None:
        rows.append("IID bootstrap")
        lows.append(iid_p05 * 100)
        highs.append(iid_p95 * 100)
    if tb_p05 is not None and tb_p95 is not None:
        rows.append("Trade bootstrap")
        lows.append(tb_p05 * 100)
        highs.append(tb_p95 * 100)

    fig = go.Figure()
    for i, label in enumerate(rows):
        fig.add_trace(go.Scatter(
            x=[lows[i], highs[i]], y=[label, label],
            mode="lines",
            line=dict(color=COLORS["accent"], width=6),
            showlegend=False,
            hovertemplate=f"{label}: [%{{x:.2f}}]%<extra></extra>",
        ))
    if real_cagr is not None:
        fig.add_vline(x=real_cagr * 100, line_dash="dash",
                      line_color=COLORS["text"],
                      annotation_text=f"observed {real_cagr*100:+.2f}%",
                      annotation_position="top")
    apply_theme(fig, height=200)
    fig.update_xaxes(title_text="CAGR (%)")
    return fig


# ---- 25. probability of ruin ---------------------------------------

def chart_mc_prob_ruin(mc: dict | None) -> go.Figure:
    if not mc:
        return empty_figure()

    iid = mc.get("iid_ci", {})
    prob = iid.get("prob_ruin")
    if prob is None:
        return empty_figure("Probability of ruin not available")

    fig = go.Figure(go.Bar(
        x=[prob * 100, (1 - prob) * 100],
        y=["", ""],
        orientation="h",
        marker_color=[COLORS["negative"],
                      COLORS.get("panel_alt", COLORS["panel"])],
        marker_line_color=COLORS["border"],
        marker_line_width=1,
        text=[f"Ruin: {prob*100:.2f}%", f"Survival: {(1-prob)*100:.2f}%"],
        textposition="inside",
        textfont=dict(size=12, color=COLORS["text"]),
        hovertemplate="%{text}<extra></extra>",
    ))
    apply_theme(fig, height=140)
    fig.update_layout(barmode="stack", showlegend=False)
    fig.update_xaxes(range=[0, 100], title_text="Probability (%)")
    fig.update_yaxes(visible=False)
    return fig

# ---- 26. Equity fan chart ------------------------------------------

def chart_mc_fan_paths(mc: dict | None) -> go.Figure:
    """
    Fan chart: many simulated equity paths in faint color,
    with shaded percentile bands and the observed path overlaid.
    """
    if not mc or "paths" not in mc:
        return empty_figure("Fan chart: paths not available")

    p = mc["paths"]
    bands = p["percentile_bands"]
    paths = p["paths_sample"]
    observed = p.get("observed_equity", [])
    n_bars = p["n_bars"]
    x = list(range(n_bars))

    fig = go.Figure()

    # Individual simulated paths — very faint gray lines
    for path in paths:
        fig.add_trace(go.Scatter(
            x=x, y=path,
            mode="lines",
            line=dict(color="rgba(120,120,120,0.08)", width=0.6),
            hoverinfo="skip",
            showlegend=False,
        ))

    # Shaded 5-95 band
    fig.add_trace(go.Scatter(
        x=x + x[::-1],
        y=bands["p95"] + bands["p05"][::-1],
        fill="toself",
        fillcolor="rgba(217,119,87,0.10)",
        line=dict(color="rgba(0,0,0,0)"),
        name="5th–95th pct",
        hoverinfo="skip",
        showlegend=True,
    ))

    # Shaded 25-75 band
    fig.add_trace(go.Scatter(
        x=x + x[::-1],
        y=bands["p75"] + bands["p25"][::-1],
        fill="toself",
        fillcolor="rgba(217,119,87,0.22)",
        line=dict(color="rgba(0,0,0,0)"),
        name="25th–75th pct",
        hoverinfo="skip",
        showlegend=True,
    ))

    # Median line
    fig.add_trace(go.Scatter(
        x=x, y=bands["p50"],
        mode="lines",
        line=dict(color=COLORS["accent"], width=2),
        name="Median",
        hovertemplate="Median: %{y:.3f}<extra></extra>",
    ))

    # Observed path
    if observed:
        fig.add_trace(go.Scatter(
            x=x, y=observed,
            mode="lines",
            line=dict(color=COLORS["text"], width=2.4),
            name="Observed",
            hovertemplate="Observed: %{y:.3f}<extra></extra>",
        ))

    apply_theme(fig, height=440)
    fig.update_xaxes(title_text="Bars (downsampled)")
    fig.update_yaxes(title_text="Equity (normalized)")
    return fig


# ---- 27. Terminal wealth histogram --------------------------------

def chart_mc_terminal_wealth(mc: dict | None) -> go.Figure:
    """Distribution of ending equity multiplier with percentile markers."""
    if not mc or "paths" not in mc:
        return empty_figure("Terminal wealth: paths not available")

    tw = np.asarray(mc["paths"]["terminal_wealth"], dtype=float)
    if len(tw) < 10:
        return empty_figure()

    pcts = [5, 25, 50, 75, 95]
    markers = {q: float(np.percentile(tw, q)) for q in pcts}

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=tw, nbinsx=60,
        marker_color=COLORS["accent"],
        marker_line_color=COLORS["bg"], marker_line_width=0.4,
        opacity=0.85,
        name="Terminal wealth",
        hovertemplate="mult: %{x:.3f}<br>count: %{y}<extra></extra>",
    ))

    # Percentile vertical lines
    marker_colors = {
        5:  COLORS["negative"],
        25: COLORS["warning"],
        50: COLORS["text"],
        75: COLORS["positive"],
        95: COLORS["positive"],
    }
    for q, value in markers.items():
        fig.add_vline(
            x=value,
            line=dict(color=marker_colors[q], width=1.5, dash="dash"),
            annotation_text=f"p{q}: {value:.2f}",
            annotation_position="top",
            annotation_font=dict(size=10, color=COLORS["text_muted"]),
        )

    apply_theme(fig, height=320)
    fig.update_xaxes(title_text="Terminal wealth multiplier (1.0 = break-even)")
    fig.update_yaxes(title_text="Simulations")
    return fig


# ---- 28. Max drawdown distribution --------------------------------

def chart_mc_drawdown_distribution(mc: dict | None) -> go.Figure:
    """Distribution of max drawdown across simulations."""
    if not mc or "paths" not in mc:
        return empty_figure("Drawdown distribution: paths not available")

    dd = np.asarray(mc["paths"]["max_drawdown"], dtype=float)
    if len(dd) < 10:
        return empty_figure()

    pcts = [5, 25, 50, 75, 95]
    markers = {q: float(np.percentile(dd, q)) for q in pcts}

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=dd * 100.0, nbinsx=60,
        marker_color=COLORS["negative"],
        marker_line_color=COLORS["bg"], marker_line_width=0.4,
        opacity=0.85,
        name="Max drawdown",
        hovertemplate="DD: %{x:.2f}%<br>count: %{y}<extra></extra>",
    ))

    marker_colors = {
        5:  COLORS["positive"],
        25: COLORS["text"],
        50: COLORS["warning"],
        75: COLORS["negative"],
        95: COLORS["negative"],
    }
    for q, value in markers.items():
        fig.add_vline(
            x=value * 100.0,
            line=dict(color=marker_colors[q], width=1.5, dash="dash"),
            annotation_text=f"p{q}: {value*100:.1f}%",
            annotation_position="top",
            annotation_font=dict(size=10, color=COLORS["text_muted"]),
        )

    apply_theme(fig, height=320)
    fig.update_xaxes(title_text="Max drawdown (%)")
    fig.update_yaxes(title_text="Simulations")
    return fig