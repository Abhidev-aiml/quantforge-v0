"""
Risk charts: rolling volatility, rolling VaR, Q-Q plot, tail ratio,
drawdown, top drawdowns.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats

from reporting.theme import apply_theme, empty_figure, COLORS


# ---- 8. rolling volatility ------------------------------------------

def chart_rolling_volatility(
    equity: pd.Series,
    windows: tuple[int, ...] = (21, 63, 252),
    periods_per_year: float = 252.0,
) -> go.Figure:
    rets = equity.pct_change().dropna()
    if len(rets) < max(windows) + 2:
        return empty_figure("Rolling volatility: not enough data")

    fig = go.Figure()
    colors = [COLORS["warning"], COLORS["accent"], COLORS["positive"]]
    for i, w in enumerate(windows):
        vol = rets.rolling(w).std(ddof=1) * np.sqrt(periods_per_year)
        fig.add_trace(go.Scatter(
            x=vol.index, y=vol.values * 100.0,
            name=f"{w}d",
            mode="lines",
            line=dict(color=colors[i % len(colors)], width=1.5),
            hovertemplate="%{y:.2f}%<extra>" + f"{w}d vol</extra>",
        ))
    apply_theme(fig)
    fig.update_yaxes(title_text="Annualized volatility (%)")
    return fig


# ---- 9. rolling VaR / CVaR ------------------------------------------

def chart_rolling_var(
    equity: pd.Series,
    window: int = 252,
    confidence: float = 0.95,
) -> go.Figure:
    rets = equity.pct_change().dropna()
    if len(rets) < window + 10:
        return empty_figure("Rolling VaR: not enough data")

    q = 1.0 - confidence
    var = rets.rolling(window).quantile(q)
    # CVaR: mean of returns below VaR within window
    cvar = rets.rolling(window).apply(
        lambda x: x[x <= np.quantile(x, q)].mean() if len(x) else np.nan,
        raw=True,
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=var.index, y=var.values * 100.0,
        name=f"VaR {int(confidence*100)}%",
        mode="lines",
        line=dict(color=COLORS["warning"], width=1.6),
        hovertemplate="%{y:.2f}%<extra>VaR</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=cvar.index, y=cvar.values * 100.0,
        name=f"CVaR {int(confidence*100)}%",
        mode="lines",
        line=dict(color=COLORS["negative"], width=1.6),
        hovertemplate="%{y:.2f}%<extra>CVaR</extra>",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=COLORS["neutral"])
    apply_theme(fig)
    fig.update_yaxes(title_text="Return (%)")
    return fig


# ---- 10. Q-Q plot ---------------------------------------------------

def chart_qq_plot(returns: pd.Series) -> go.Figure:
    r = returns.dropna().values
    if len(r) < 20:
        return empty_figure()

    mu, sd = float(np.mean(r)), float(np.std(r, ddof=1))
    if sd <= 0:
        return empty_figure("Q-Q: zero variance")

    standardized = (r - mu) / sd
    qq = stats.probplot(standardized, dist="norm", fit=False)
    theoretical, sample = qq[0], qq[1]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=theoretical, y=sample,
        mode="markers",
        marker=dict(size=4, color=COLORS["accent"], opacity=0.7),
        name="Observed",
        hovertemplate="theory: %{x:.2f}<br>sample: %{y:.2f}<extra></extra>",
    ))
    # 45° reference
    lo, hi = min(theoretical.min(), sample.min()), max(theoretical.max(), sample.max())
    fig.add_trace(go.Scatter(
        x=[lo, hi], y=[lo, hi],
        mode="lines",
        line=dict(color=COLORS["warning"], width=1.5, dash="dash"),
        name="Normal reference",
        hoverinfo="skip",
    ))
    apply_theme(fig)
    fig.update_xaxes(title_text="Theoretical quantile (normal)")
    fig.update_yaxes(title_text="Sample quantile")
    return fig


# ---- 11. rolling tail ratio -----------------------------------------

def chart_rolling_tail_ratio(
    equity: pd.Series, window: int = 252,
) -> go.Figure:
    rets = equity.pct_change().dropna()
    if len(rets) < window + 10:
        return empty_figure()

    def tail_ratio(x):
        if len(x) < 20:
            return np.nan
        p95 = np.percentile(x, 95)
        p05 = np.percentile(x, 5)
        if p05 == 0:
            return np.nan
        return p95 / abs(p05)

    tr = rets.rolling(window).apply(tail_ratio, raw=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=tr.index, y=tr.values,
        mode="lines",
        line=dict(color=COLORS["accent"], width=1.6),
        hovertemplate="%{y:.3f}<extra>Tail ratio</extra>",
    ))
    fig.add_hline(y=1.0, line_dash="dash", line_color=COLORS["neutral"],
                  annotation_text="Symmetric")
    apply_theme(fig)
    fig.update_yaxes(title_text="Tail ratio (95th / |5th|)")
    return fig


# ---- 12. drawdown underwater ----------------------------------------

def chart_drawdown(equity: pd.Series) -> go.Figure:
    if len(equity) < 2:
        return empty_figure()
    dd = (equity / equity.cummax() - 1.0) * 100.0

    fig = go.Figure(go.Scatter(
        x=dd.index, y=dd.values,
        mode="lines",
        line=dict(color=COLORS["negative"], width=1.0),
        fill="tozeroy",
        fillcolor="rgba(248,81,73,0.22)",
        hovertemplate="%{y:.2f}%<extra>Drawdown</extra>",
    ))
    apply_theme(fig)
    fig.update_yaxes(title_text="Drawdown (%)")
    return fig


# ---- 13. top drawdowns annotated ------------------------------------

def _extract_drawdowns(equity: pd.Series) -> pd.DataFrame:
    """Return per-drawdown episodes with peak/trough/recovery timestamps."""
    peak = equity.iloc[0]
    peak_ts = equity.index[0]
    current_peak_ts = peak_ts
    episodes = []
    in_dd = False
    dd_start = None

    for ts, v in equity.items():
        if v >= peak:
            # recovery or new high
            if in_dd:
                episodes[-1]["recovery_ts"] = ts
                episodes[-1]["duration_days"] = (
                    (ts - episodes[-1]["trough_ts"]).days
                )
                episodes[-1]["total_days"] = (
                    (ts - episodes[-1]["start_ts"]).days
                )
            peak = v
            current_peak_ts = ts
            in_dd = False
            dd_start = None
        else:
            dd = v / peak - 1.0
            if not in_dd:
                in_dd = True
                dd_start = current_peak_ts
                episodes.append({
                    "start_ts": current_peak_ts,
                    "trough_ts": ts,
                    "trough_value": v,
                    "depth": dd,
                    "recovery_ts": None,
                    "duration_days": None,
                    "total_days": None,
                })
            else:
                if dd < episodes[-1]["depth"]:
                    episodes[-1]["trough_ts"] = ts
                    episodes[-1]["trough_value"] = v
                    episodes[-1]["depth"] = dd
    return pd.DataFrame(episodes)


def chart_top_drawdowns(
    equity: pd.Series, top_n: int = 5,
) -> go.Figure:
    if len(equity) < 20:
        return empty_figure()

    episodes = _extract_drawdowns(equity)
    if episodes.empty:
        return empty_figure("No drawdowns found")

    episodes = episodes.sort_values("depth").head(top_n)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity.index, y=equity.values,
        mode="lines",
        line=dict(color=COLORS["muted"], width=1.0),
        name="Equity",
        hovertemplate="%{y:,.0f}<extra>Equity</extra>",
    ))

    for i, (_, row) in enumerate(episodes.iterrows()):
        # shade the drawdown period
        x0 = row["start_ts"]
        x1 = row["recovery_ts"] if row["recovery_ts"] is not None else equity.index[-1]
        fig.add_vrect(
            x0=x0, x1=x1,
            fillcolor="rgba(248,81,73,0.08)",
            line_width=0,
            layer="below",
        )
        # annotate depth
        fig.add_annotation(
            x=row["trough_ts"], y=row["trough_value"],
            text=f"#{i+1}  {row['depth']*100:.1f}%",
            showarrow=True, arrowhead=2,
            arrowcolor=COLORS["negative"],
            font=dict(color=COLORS["negative"], size=10),
            bgcolor=COLORS["panel"],
            bordercolor=COLORS["border"],
        )
    apply_theme(fig, height=400)
    fig.update_yaxes(title_text="Equity")
    return fig


# ---- utility --------------------------------------------------------

def top_drawdowns_table(equity: pd.Series, top_n: int = 10) -> pd.DataFrame:
    """Return a sorted DataFrame of top-N drawdowns for tabular display."""
    episodes = _extract_drawdowns(equity)
    if episodes.empty:
        return pd.DataFrame()
    episodes = episodes.sort_values("depth").head(top_n).copy()
    episodes["depth_pct"] = (episodes["depth"] * 100).round(2)
    episodes = episodes[[
        "start_ts", "trough_ts", "recovery_ts",
        "depth_pct", "duration_days", "total_days",
    ]]
    return episodes.reset_index(drop=True)