"""
Regime analysis charts.

Uses trailing volatility quantiles as the regime classifier:
    low  → below 33rd percentile
    mid  → 33rd to 67th percentile
    high → above 67th percentile
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from reporting.theme import apply_theme, empty_figure, COLORS

REGIMES = ("low", "mid", "high")
REGIME_COLORS = {
    "low":  "rgba(74,124,89,0.10)",
    "mid":  "rgba(198,138,46,0.10)",
    "high": "rgba(178,58,46,0.10)",
}


# ---- regime classifier ---------------------------------------------

def classify_regimes(
    equity: pd.Series, window: int = 63,
) -> pd.Series:
    """
    Return a Series of regime labels ('low', 'mid', 'high') per bar,
    classified by the strategy's own trailing volatility quantiles.
    """
    rets = equity.pct_change()
    vol = rets.rolling(window, min_periods=max(20, window // 3)).std(ddof=1)
    vol = vol.dropna()
    if len(vol) < 30:
        return pd.Series(dtype=object)

    q33 = vol.quantile(1 / 3)
    q67 = vol.quantile(2 / 3)

    labels = pd.Series("mid", index=vol.index, dtype=object)
    labels[vol <= q33] = "low"
    labels[vol >= q67] = "high"
    return labels


# ---- 34. regime overlay on equity ----------------------------------

def chart_regime_overlay(equity: pd.Series, window: int = 63) -> go.Figure:
    if len(equity) < window + 30:
        return empty_figure("Not enough data for regime analysis")

    labels = classify_regimes(equity, window)
    if labels.empty:
        return empty_figure()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity.index, y=equity.values,
        mode="lines",
        line=dict(color=COLORS["text"], width=1.5),
        name="Equity",
        hovertemplate="%{y:,.0f}<extra>Equity</extra>",
    ))

    # Draw contiguous regions of each regime as background
    prev_regime = labels.iloc[0]
    start = labels.index[0]
    for ts, regime in labels.iloc[1:].items():
        if regime != prev_regime:
            fig.add_vrect(
                x0=start, x1=ts,
                fillcolor=REGIME_COLORS.get(prev_regime, "rgba(0,0,0,0)"),
                line_width=0, layer="below",
            )
            start = ts
            prev_regime = regime
    fig.add_vrect(
        x0=start, x1=labels.index[-1],
        fillcolor=REGIME_COLORS.get(prev_regime, "rgba(0,0,0,0)"),
        line_width=0, layer="below",
    )

    apply_theme(fig, height=380)
    fig.update_yaxes(title_text="Equity")
    return fig


# ---- 35. performance by regime -------------------------------------

def chart_regime_performance(equity: pd.Series, window: int = 63) -> go.Figure:
    if len(equity) < window + 30:
        return empty_figure()

    labels = classify_regimes(equity, window)
    if labels.empty:
        return empty_figure()

    rets = equity.pct_change().reindex(labels.index)

    rows = []
    for r in REGIMES:
        mask = labels == r
        if not mask.any():
            continue
        r_sub = rets[mask].dropna()
        if len(r_sub) < 5:
            continue
        mu = r_sub.mean()
        sd = r_sub.std(ddof=1)
        sharpe = (mu / sd * np.sqrt(252)) if sd > 0 else 0.0
        hit = (r_sub > 0).mean()
        rows.append({
            "regime": r,
            "sharpe": sharpe,
            "hit_rate": hit,
            "ann_vol": sd * np.sqrt(252),
            "n_bars": len(r_sub),
        })

    if not rows:
        return empty_figure()

    df = pd.DataFrame(rows)
    colors = [
        COLORS["positive"] if s > 0 else COLORS["negative"]
        for s in df["sharpe"]
    ]

    fig = go.Figure(go.Bar(
        x=df["regime"].str.capitalize(),
        y=df["sharpe"],
        marker_color=colors,
        marker_line_color=COLORS["bg"], marker_line_width=0.5,
        text=[f"{s:+.2f}" for s in df["sharpe"]],
        textposition="outside",
        textfont=dict(size=11, color=COLORS["text"]),
        customdata=np.stack([df["n_bars"], df["hit_rate"] * 100], axis=-1),
        hovertemplate=(
            "%{x}<br>Sharpe: %{y:.3f}<br>"
            "Bars: %{customdata[0]}<br>"
            "Hit rate: %{customdata[1]:.1f}%<extra></extra>"
        ),
    ))
    fig.add_hline(y=0, line_color=COLORS["text_subtle"], line_width=0.5)
    apply_theme(fig)
    fig.update_yaxes(title_text="Sharpe (annualized)")
    return fig


# ---- 36. bull/bear attribution vs benchmark -------------------------

def chart_bull_bear_performance(
    equity: pd.Series, benchmark: pd.Series | None = None,
) -> go.Figure:
    if len(equity) < 30:
        return empty_figure()

    rets = equity.pct_change().dropna()
    if benchmark is not None:
        br = benchmark.reindex(equity.index).ffill().pct_change().dropna()
        aligned = pd.concat([rets, br], axis=1, join="inner").dropna()
        aligned.columns = ["strat", "bench"]
        bull = aligned[aligned["bench"] > 0]
        bear = aligned[aligned["bench"] <= 0]
        if len(bull) < 5 or len(bear) < 5:
            return empty_figure("Insufficient bull/bear bars")
        rows = []
        for name, sub in (("Bull", bull), ("Bear", bear)):
            rows.append({
                "period": name,
                "strat": sub["strat"].mean() * 252,
                "bench": sub["bench"].mean() * 252,
                "n_bars": len(sub),
            })
        df = pd.DataFrame(rows)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df["period"], y=df["strat"] * 100,
            name="Strategy",
            marker_color=COLORS["accent"],
            marker_line_color=COLORS["bg"], marker_line_width=0.5,
            text=[f"{v*100:+.1f}%" for v in df["strat"]],
            textposition="outside",
            textfont=dict(size=10, color=COLORS["text"]),
            hovertemplate="%{x} · Strategy: %{y:.2f}% annualized<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=df["period"], y=df["bench"] * 100,
            name="Benchmark",
            marker_color=COLORS["text_muted"],
            marker_line_color=COLORS["bg"], marker_line_width=0.5,
            text=[f"{v*100:+.1f}%" for v in df["bench"]],
            textposition="outside",
            textfont=dict(size=10, color=COLORS["text"]),
            hovertemplate="%{x} · Benchmark: %{y:.2f}% annualized<extra></extra>",
        ))
        fig.update_layout(barmode="group")
    else:
        # No benchmark: split on strategy's own returns
        bull = rets[rets > 0]
        bear = rets[rets <= 0]
        fig = go.Figure(go.Bar(
            x=["Up days", "Down days"],
            y=[bull.mean() * 252 * 100, bear.mean() * 252 * 100],
            marker_color=[COLORS["positive"], COLORS["negative"]],
            marker_line_color=COLORS["bg"], marker_line_width=0.5,
            text=[f"{bull.mean()*252*100:+.1f}%", f"{bear.mean()*252*100:+.1f}%"],
            textposition="outside",
            textfont=dict(size=10, color=COLORS["text"]),
        ))

    fig.add_hline(y=0, line_color=COLORS["text_subtle"], line_width=0.5)
    apply_theme(fig)
    fig.update_yaxes(title_text="Annualized return (%)")
    return fig


# ---- 37. rolling beta -----------------------------------------------

def chart_rolling_beta(
    equity: pd.Series,
    benchmark: pd.Series | None,
    window: int = 252,
) -> go.Figure:
    if benchmark is None:
        return empty_figure("Benchmark not available")

    rets = equity.pct_change()
    br = benchmark.reindex(equity.index).ffill().pct_change()
    df = pd.concat([rets, br], axis=1, join="inner").dropna()
    if len(df) < window + 20:
        return empty_figure()
    df.columns = ["s", "b"]

    cov = df["s"].rolling(window).cov(df["b"])
    var = df["b"].rolling(window).var()
    beta = cov / var

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=beta.index, y=beta.values,
        mode="lines",
        line=dict(color=COLORS["accent"], width=1.8),
        hovertemplate="β = %{y:.3f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color=COLORS["text_subtle"])
    fig.add_hline(y=1, line_dash="dot", line_color=COLORS["warning"],
                  annotation_text="β=1", annotation_position="right")
    apply_theme(fig)
    fig.update_yaxes(title_text="Rolling beta to benchmark")
    return fig