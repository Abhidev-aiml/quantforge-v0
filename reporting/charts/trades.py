"""
Trade-level charts.

All functions accept a trades DataFrame (from extract_trades) with columns:
    entry_ts, exit_ts, direction, entry_price, exit_price, qty,
    gross_pnl, commission, pnl, scale_ins
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from reporting.theme import apply_theme, empty_figure, COLORS


def _prepare(trades: pd.DataFrame | None) -> pd.DataFrame | None:
    if trades is None or trades.empty:
        return None
    t = trades.copy()
    for col in ("entry_ts", "exit_ts"):
        if col in t.columns and not pd.api.types.is_datetime64_any_dtype(t[col]):
            t[col] = pd.to_datetime(t[col], errors="coerce")
    if "pnl" not in t.columns:
        return None
    return t


# ---- 14. trade pnl distribution -------------------------------------

def chart_trade_pnl_distribution(trades: pd.DataFrame | None) -> go.Figure:
    t = _prepare(trades)
    if t is None:
        return empty_figure("No trades recorded")

    pnl = t["pnl"].dropna().values
    if len(pnl) < 5:
        return empty_figure("Fewer than 5 trades")

    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]

    fig = go.Figure()
    if len(losses):
        fig.add_trace(go.Histogram(
            x=losses, nbinsx=30, name="Loss",
            marker_color=COLORS["negative"],
            marker_line_color=COLORS["bg"], marker_line_width=0.4,
            opacity=0.85,
        ))
    if len(wins):
        fig.add_trace(go.Histogram(
            x=wins, nbinsx=30, name="Win",
            marker_color=COLORS["positive"],
            marker_line_color=COLORS["bg"], marker_line_width=0.4,
            opacity=0.85,
        ))
    fig.add_vline(x=0, line_dash="dash", line_color=COLORS["text_subtle"])
    apply_theme(fig)
    fig.update_layout(barmode="overlay")
    fig.update_xaxes(title_text="Trade PnL")
    fig.update_yaxes(title_text="Count")
    return fig


# ---- 15. cumulative trade pnl ---------------------------------------

def chart_cumulative_trade_pnl(trades: pd.DataFrame | None) -> go.Figure:
    t = _prepare(trades)
    if t is None:
        return empty_figure("No trades recorded")
    t = t.dropna(subset=["pnl", "exit_ts"]).sort_values("exit_ts")
    if len(t) < 2:
        return empty_figure()

    cum = t["pnl"].cumsum().values
    x = t["exit_ts"].values

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=cum,
        mode="lines",
        line=dict(color=COLORS["accent"], width=1.8),
        fill="tozeroy",
        fillcolor="rgba(217,119,87,0.10)",
        hovertemplate="%{y:,.0f}<extra>Cumulative PnL</extra>",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color=COLORS["text_subtle"])
    apply_theme(fig)
    fig.update_yaxes(title_text="Cumulative PnL")
    return fig


# ---- 16. holding period distribution --------------------------------

def chart_holding_period_distribution(trades: pd.DataFrame | None) -> go.Figure:
    t = _prepare(trades)
    if t is None:
        return empty_figure("No trades recorded")
    t = t.dropna(subset=["entry_ts", "exit_ts"])
    if len(t) < 5:
        return empty_figure()

    days = (t["exit_ts"] - t["entry_ts"]).dt.total_seconds() / 86400.0
    days = days[days >= 0]
    if days.empty:
        return empty_figure()

    fig = go.Figure(go.Histogram(
        x=days.values, nbinsx=40,
        marker_color=COLORS["accent"],
        marker_line_color=COLORS["bg"], marker_line_width=0.4,
        opacity=0.85,
        hovertemplate="%{x:.1f} days<br>%{y} trades<extra></extra>",
    ))
    apply_theme(fig)
    fig.update_xaxes(title_text="Holding period (days)")
    fig.update_yaxes(title_text="Trades")
    return fig


# ---- 17. consecutive streaks ---------------------------------------

def chart_consecutive_streaks(trades: pd.DataFrame | None) -> go.Figure:
    t = _prepare(trades)
    if t is None:
        return empty_figure("No trades recorded")
    pnl = t["pnl"].dropna().values
    if len(pnl) < 5:
        return empty_figure()

    signs = np.sign(pnl)
    streaks = []
    current_sign = signs[0]
    length = 1
    for s in signs[1:]:
        if s == current_sign and s != 0:
            length += 1
        else:
            if current_sign != 0:
                streaks.append((current_sign, length))
            current_sign = s
            length = 1
    if current_sign != 0:
        streaks.append((current_sign, length))

    wins = [l for s, l in streaks if s > 0]
    losses = [l for s, l in streaks if s < 0]

    fig = go.Figure()
    if wins:
        fig.add_trace(go.Histogram(
            x=wins, name="Win streak",
            marker_color=COLORS["positive"],
            marker_line_color=COLORS["bg"], marker_line_width=0.5,
            opacity=0.85,
        ))
    if losses:
        fig.add_trace(go.Histogram(
            x=losses, name="Loss streak",
            marker_color=COLORS["negative"],
            marker_line_color=COLORS["bg"], marker_line_width=0.5,
            opacity=0.85,
        ))
    apply_theme(fig)
    fig.update_layout(barmode="overlay")
    fig.update_xaxes(title_text="Streak length")
    fig.update_yaxes(title_text="Occurrences")
    return fig


# ---- 18. win vs loss breakdown --------------------------------------

def chart_win_loss_breakdown(trades: pd.DataFrame | None) -> go.Figure:
    t = _prepare(trades)
    if t is None:
        return empty_figure("No trades recorded")
    pnl = t["pnl"].dropna()
    if len(pnl) < 5:
        return empty_figure()

    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]

    labels, values, colors = [], [], []
    if len(wins):
        labels.append(f"Avg win ({len(wins)})")
        values.append(wins.mean())
        colors.append(COLORS["positive"])
        labels.append(f"Best win ({len(wins)})")
        values.append(wins.max())
        colors.append(COLORS["positive_soft"] if "positive_soft" in COLORS else COLORS["positive"])
    if len(losses):
        labels.append(f"Avg loss ({len(losses)})")
        values.append(losses.mean())
        colors.append(COLORS["negative"])
        labels.append(f"Worst loss ({len(losses)})")
        values.append(losses.min())
        colors.append(COLORS["negative"])

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=colors,
        marker_line_color=COLORS["bg"], marker_line_width=0.5,
        text=[f"{v:+,.0f}" for v in values],
        textposition="outside",
        textfont=dict(size=11, color=COLORS["text"]),
        hovertemplate="%{y}: %{x:,.0f}<extra></extra>",
    ))
    fig.add_vline(x=0, line_dash="dash", line_color=COLORS["text_subtle"])
    apply_theme(fig, height=max(260, 60 + 40 * len(labels)))
    fig.update_xaxes(title_text="PnL")
    return fig


# ---- 19. trade PnL timeline ----------------------------------------

def chart_trade_timeline(trades: pd.DataFrame | None) -> go.Figure:
    t = _prepare(trades)
    if t is None:
        return empty_figure("No trades recorded")
    t = t.dropna(subset=["pnl", "exit_ts"]).sort_values("exit_ts")
    if len(t) < 5:
        return empty_figure()

    colors = [COLORS["positive"] if p > 0 else COLORS["negative"]
              for p in t["pnl"].values]

    fig = go.Figure(go.Bar(
        x=t["exit_ts"].values, y=t["pnl"].values,
        marker_color=colors,
        marker_line_color=COLORS["bg"], marker_line_width=0.2,
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:+,.0f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color=COLORS["text_subtle"])
    apply_theme(fig)
    fig.update_yaxes(title_text="PnL per trade")
    return fig