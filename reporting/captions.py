"""
Chart captions and interpretive text for the Tier 2 report.

Each caption function takes the loaded artifacts and returns a dict
with a `text` string that explains what the chart shows, references
the observed values, and states what 'good' looks like.

This is what turns a chart dump into a research report.
"""
from __future__ import annotations

import numpy as np


def _fmt_pct(x, d=2):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x*100:+.{d}f}%"


def _fmt(x, d=3):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x:+.{d}f}"


# ---------------------------------------------------------------- performance

def equity_caption(metrics: dict, benchmark_metrics: dict | None = None) -> str:
    cagr = metrics.get("CAGR", 0)
    dd = metrics.get("max_drawdown", 0)
    bm_cagr = (benchmark_metrics or {}).get("CAGR")
    text = (
        f"The strategy compounded at {_fmt_pct(cagr)} per year with a "
        f"peak-to-trough drawdown of {_fmt_pct(dd)}. "
    )
    if bm_cagr is not None:
        delta = cagr - bm_cagr
        text += (
            f"The passive benchmark (buy & hold) compounded at "
            f"{_fmt_pct(bm_cagr)}, so the strategy's drift capture was "
            f"{_fmt_pct(delta)} per year. "
        )
    text += (
        "A healthy equity curve rises steadily, with drawdowns that are "
        "shallow and short. Deep drawdowns paired with long recovery "
        "periods mean the strategy is taking on more risk than the "
        "return justifies."
    )
    return text


def cumulative_return_caption(metrics: dict) -> str:
    total = metrics.get("total_return", 0)
    return (
        f"Total cumulative return over the full sample was "
        f"{_fmt_pct(total)}. The dashed line is the buy-and-hold path. "
        "Look for the strategy curve to be above or near the benchmark "
        "while trending upward. Long flat stretches mean the strategy "
        "spent time out of the market — acceptable if it avoided "
        "significant drawdowns, concerning if it missed rallies."
    )


def excess_return_caption(metrics: dict) -> str:
    return (
        "Cumulative return of the strategy minus the same-exposure "
        "benchmark. If this curve slopes upward over long windows, the "
        "strategy is adding value beyond passive exposure. If it slopes "
        "downward, the strategy is losing to a passive alternative — "
        "the classic signature of beta capture dressed up as alpha. "
        "The ideal is a smooth upward slope; the worst case is a "
        "monotonic decline."
    )


def rolling_cagr_caption() -> str:
    return (
        "Rolling annualized return computed on a 1-year and 3-year lookback. "
        "A robust strategy shows both lines positive most of the time. "
        "If the 1Y line swings violently but 3Y stays positive, the "
        "short-term signal is noisy but the longer-term edge is intact. "
        "If both lines go negative for extended periods, the strategy is "
        "regime-dependent."
    )


def annual_returns_caption() -> str:
    return (
        "Annual returns, green for positive years and red for negative. "
        "A trend-following or momentum strategy should have more green "
        "years than red, but the green bars should be visibly larger "
        "on average. Even distribution of small wins and small losses "
        "with no standout years suggests the edge is weak."
    )


def monthly_heatmap_caption() -> str:
    return (
        "Each cell is one month's return. Green is positive, red is "
        "negative. Strong strategies show clustering — consecutive "
        "positive months in bull regimes, sparse red months. Check for "
        "any single catastrophic month (deep red) that dominates the "
        "annual return; that's a tail-risk signature."
    )


def return_distribution_caption(metrics: dict) -> str:
    skew = metrics.get("skew", 0)
    kurt = metrics.get("kurtosis", 0)
    return (
        f"Daily return distribution (histogram) vs a fitted normal curve. "
        f"Skew = {_fmt(skew, 2)}, excess kurtosis = {_fmt(kurt, 2)}. "
        "Positive skew means the strategy has fat right tails (a few big "
        "wins) — common for trend-following. Negative skew means fat left "
        "tails (crash risk). Kurtosis above 0 means the tails are fatter "
        "than a normal distribution predicts, which is typical of all "
        "financial returns but matters for position sizing."
    )


# ---------------------------------------------------------------- risk

def rolling_vol_caption(metrics: dict) -> str:
    vol = metrics.get("volatility", 0)
    return (
        f"Rolling annualized volatility at 21, 63, and 252-day windows. "
        f"Full-sample volatility is {_fmt_pct(vol)}. The short windows "
        "swing wildly, the long window is smoother. Ideally the long-term "
        "line stays within a stable band. Large expansions in the 63-day "
        "line signal regime shifts — periods when position sizing should "
        "be reduced."
    )


def rolling_var_caption(metrics: dict) -> str:
    var = metrics.get("VaR_95", 0)
    cvar = metrics.get("CVaR_95", 0)
    return (
        f"Rolling 95% Value-at-Risk and Conditional VaR. Full-sample "
        f"VaR is {_fmt_pct(var, 2)} (5% of days are worse than this), and "
        f"CVaR is {_fmt_pct(cvar, 2)} (the average of those bad days). "
        "CVaR is always more negative than VaR — that's the point. Watch "
        "for CVaR bands that widen sharply; they precede drawdowns."
    )


def qq_plot_caption() -> str:
    return (
        "Q-Q plot of daily returns against a normal distribution. Points "
        "on the diagonal line mean the returns are normally distributed. "
        "Systematic departures at the tails (points above or below the "
        "line at the extremes) show fat tails — meaning the strategy has "
        "larger extreme moves than a normal distribution would predict. "
        "Almost every real return series shows this."
    )


def tail_ratio_caption() -> str:
    return (
        "Rolling tail ratio — the 95th percentile return divided by the "
        "absolute value of the 5th percentile. A value of 1.0 means the "
        "tails are symmetric. Above 1.0 means upside tails are bigger "
        "(positive asymmetry, generally good). Below 1.0 means downside "
        "tails are bigger (bad — the strategy has more crash risk than "
        "rally potential)."
    )


# ---------------------------------------------------------------- drawdowns

def drawdown_caption(metrics: dict) -> str:
    dd = metrics.get("max_drawdown", 0)
    days = metrics.get("max_drawdown_duration_days", 0)
    return (
        f"Underwater curve — percentage below the prior peak. The worst "
        f"drawdown was {_fmt_pct(dd)} lasting {int(days):,} calendar days. "
        "Drawdowns are unavoidable; what matters is their depth and how "
        "long they last. A strategy with -20% max drawdown that recovers "
        "in 6 months is tradeable. One with -50% that takes 5 years to "
        "recover is not."
    )


def top_drawdowns_caption() -> str:
    return (
        "The equity curve with the top 5 drawdown episodes highlighted. "
        "Look for patterns: are they clustered in a specific regime "
        "(2008, 2020), or spread evenly? Clustering means the strategy "
        "is regime-dependent. Also check recovery speed — the shaded "
        "regions should end within weeks to months, not years."
    )


# ---------------------------------------------------------------- trades

def trade_pnl_distribution_caption(metrics: dict) -> str:
    wr = metrics.get("win_rate", 0)
    pf = metrics.get("profit_factor", 0)
    return (
        f"Distribution of individual trade PnL. Win rate = {_fmt_pct(wr, 1)}, "
        f"profit factor = {_fmt(pf, 2)}. Trend-following strategies "
        "typically show a low win rate (< 40%) with a fat right tail — "
        "many small losses, a few large wins. Mean-reversion shows the "
        "opposite: high win rate with a fat left tail. Both patterns "
        "can be profitable; a distribution centered on zero with no "
        "tail is a red flag."
    )


def cumulative_trade_pnl_caption() -> str:
    return (
        "Running total of trade PnL, one point per closed trade. A "
        "healthy curve trends up with periodic pullbacks. A flat curve "
        "means the strategy is not generating edge. A curve that rises "
        "sharply then plateaus suggests the edge existed in an earlier "
        "regime but has decayed."
    )


def holding_period_caption() -> str:
    return (
        "Distribution of how long each trade was held. Trend-following "
        "has long holding periods (weeks to months); mean-reversion has "
        "short (days). If your strategy's holding period varies by an "
        "order of magnitude, it's mixing two different behaviors — "
        "likely a sign of an unstable hypothesis."
    )


def streaks_caption() -> str:
    return (
        "Distribution of consecutive winning and losing trades. Random "
        "sequences naturally produce runs. What matters is whether "
        "your streaks are longer than a random process would generate. "
        "Very long losing streaks (> 5) often reveal that the strategy "
        "has entered a regime where the edge no longer applies."
    )


def win_loss_caption() -> str:
    return (
        "Average and extreme winning vs losing trades. The ratio of "
        "avg win to avg loss is the payoff ratio. A trend strategy with "
        "payoff ratio 2.5 and win rate 35% is profitable; the same "
        "payoff with 20% win rate is not. Losses should be capped — a "
        "single catastrophic loss suggests missing risk controls."
    )


# ---------------------------------------------------------------- MC

def null_bootstrap_caption(mc: dict) -> str:
    nb = mc.get("null_bootstrap", {})
    obs = nb.get("observed_sharpe")
    p = nb.get("p_value_one_sided")
    return (
        f"Null bootstrap — resamples the return series with the mean "
        f"removed, so the null distribution has zero expected Sharpe. "
        f"Observed Sharpe {_fmt(obs)}, one-sided p-value {p:.4f}. "
        "Small p-value (< 0.05) means the observed Sharpe is unlikely "
        "under a no-edge null. Note: this test only says the strategy "
        "made money; it does NOT say the strategy has edge over beta. "
        "That's what the walk-forward and same-exposure tests are for."
    )


def fan_chart_caption(mc: dict) -> str:
    p = mc.get("paths", {})
    n = p.get("n_sims", 0)
    return (
        f"{n:,} simulated alternate equity paths, generated by block-"
        "bootstrapping the historical returns. The dark line is the "
        "observed path. Wide bands mean the strategy's outcome is highly "
        "path-dependent; narrow bands mean the outcome is stable. If the "
        "observed path sits near the median, performance was typical. If "
        "it sits near the top, the backtest was a lucky draw from the "
        "possible distribution — be careful assuming it repeats."
    )


def terminal_wealth_caption(mc: dict) -> str:
    return (
        "Distribution of ending equity multipliers across simulations. "
        "The p50 (median) is what you'd expect in a typical alternate "
        "history; the p5 is what you'd see in a bad draw. The spread "
        "between p5 and p95 is your uncertainty band. If p5 is below 1.0, "
        "meaningful probability exists of a losing outcome even if the "
        "median is profitable."
    )


def drawdown_distribution_caption(mc: dict) -> str:
    return (
        "Distribution of max drawdowns across simulations. Unlike a single "
        "backtest, this shows the range of drawdowns you might experience. "
        "If the 95th percentile is much worse than the observed max "
        "drawdown, the backtest was kind to you — plan for a bigger one."
    )


def block_sweep_caption(mc: dict) -> str:
    return (
        "Signal block shuffle sweep — p-value as a function of the block "
        "size used to shuffle signals. Small p-values at small block sizes "
        "just mean the strategy trades less than random; not a real "
        "timing test. What matters is whether p-values stay below 0.05 "
        "at block sizes comparable to your average holding period. If "
        "they don't, the specific alignment of signals to price action "
        "does not add value."
    )


# ---------------------------------------------------------------- WF

def wf_summary_caption(wf: dict) -> str:
    is_s = wf.get("mean_IS_sharpe")
    oos_s = wf.get("mean_OOS_sharpe")
    ch = wf.get("chained_OOS_sharpe")
    bm = wf.get("chained_OOS_benchmark_sharpe")
    ex = wf.get("chained_OOS_excess_sharpe")
    deg = wf.get("degradation_ratio")
    return (
        f"In-sample Sharpe {_fmt(is_s)}, out-of-sample Sharpe {_fmt(oos_s)}, "
        f"chained OOS Sharpe {_fmt(ch)}. The same-exposure benchmark's "
        f"chained Sharpe was {_fmt(bm)}, giving an excess Sharpe of "
        f"{_fmt(ex)}. Degradation ratio (OOS/IS) = {_fmt(deg, 2)}. "
        "A ratio near 1.0 means the strategy performs as well out of "
        "sample as in — no overfitting. A ratio near 0.5 means the "
        "in-sample performance was misleading. The excess Sharpe tells "
        "you whether the strategy actually beats a passive alternative; "
        "negative excess means it's still a beta play, regardless of "
        "walk-forward stability."
    )


def wf_scatter_caption() -> str:
    return (
        "In-sample Sharpe (x-axis) vs out-of-sample Sharpe (y-axis) for "
        "each walk-forward window. Points above the dashed diagonal are "
        "windows where OOS outperformed IS — good news. Points below "
        "mean IS was misleading — overfitting. A well-behaved strategy "
        "has points scattered evenly around the diagonal, not clustered "
        "deeply below."
    )


def wf_excess_caption() -> str:
    return (
        "Excess Sharpe vs same-exposure benchmark, per OOS window. "
        "Positive bars mean the strategy beat a passive alternative "
        "during that window; negative bars mean it lost. A truly robust "
        "edge shows a majority of positive bars. Clustering of negatives "
        "in specific years (2008, 2020) reveals regime dependence."
    )


def wf_trade_counts_caption() -> str:
    return (
        "Trades taken in each OOS window. Windows with fewer than 5 trades "
        "are statistically thin — their Sharpe estimates have wide "
        "confidence intervals. If most windows are flagged low-confidence, "
        "the aggregate metrics are the only meaningful signal, not the "
        "per-window chart."
    )


# ---------------------------------------------------------------- RC

def rc_caption(rc: dict) -> str:
    p = rc.get("p_value")
    best = rc.get("best_combo", "—")
    return (
        f"White's Reality Check — is the best combo significant after "
        f"correcting for the number of strategies tried? Best combo: "
        f"{best}. Observed V statistic: {_fmt(rc.get('V_observed'))}. "
        f"p-value: {p:.4f}. If p < 0.05, the best strategy is genuinely "
        "better than random after multiple-testing correction. If p is "
        "large, the best result is consistent with having tried enough "
        "variants to find a fluke."
    )


def rc_top_combos_caption() -> str:
    return (
        "Top 5 combos ranked by annualized excess return over the "
        "same-exposure benchmark. Even if the top combo has positive "
        "excess return, its neighbors should be similar for the result "
        "to be credible. A sharp drop from rank 1 to rank 5 means the "
        "winner is an outlier, not a robust region of parameter space."
    )


# ---------------------------------------------------------------- regime

def regime_overlay_caption() -> str:
    return (
        "Equity curve shaded by volatility regime (low, mid, high) "
        "classified from the strategy's own trailing 63-day volatility "
        "quartiles. Look for whether the strategy performs well in "
        "specific regimes. Trend strategies typically shine in high-"
        "volatility regimes (they can capture big moves) and struggle "
        "in low-vol regimes (chop)."
    )


def regime_performance_caption() -> str:
    return (
        "Annualized Sharpe within each volatility regime. A good strategy "
        "has positive Sharpe in at least two of three regimes, with "
        "monotonic increase or decrease as volatility changes. If Sharpe "
        "is positive only in one regime, the strategy is regime-dependent "
        "and will fail in others."
    )


def bull_bear_caption() -> str:
    return (
        "Performance on up days vs down days. Trend strategies often "
        "have higher returns on down days (short positions) or symmetric "
        "returns. Mean-reversion tends to perform well on up days and "
        "poorly on down days (it buys into weakness). The ratio tells "
        "you which market direction the strategy is actually betting on."
    )


def rolling_beta_caption() -> str:
    return (
        "Rolling 252-day beta to the benchmark. A beta near 1.0 means the "
        "strategy moves in lockstep with the market — you're paying fees "
        "for beta. A beta near 0 means genuine diversification. Fluctuating "
        "beta means the strategy's market exposure is unstable, which is "
        "usually a sign that position sizing needs refinement."
    )


# ---------------------------------------------------------------- registry

CAPTIONS = {
    "equity":                  equity_caption,
    "cumret":                  cumulative_return_caption,
    "excess":                  excess_return_caption,
    "rolling_cagr":            rolling_cagr_caption,
    "annual":                  annual_returns_caption,
    "monthly":                 monthly_heatmap_caption,
    "ret_dist":                return_distribution_caption,
    "vol":                     rolling_vol_caption,
    "var":                     rolling_var_caption,
    "qq":                      qq_plot_caption,
    "tail":                    tail_ratio_caption,
    "drawdown":                drawdown_caption,
    "top_dd":                  top_drawdowns_caption,
    "trade_pnl_dist":          trade_pnl_distribution_caption,
    "trade_cum_pnl":           cumulative_trade_pnl_caption,
    "trade_holding":           holding_period_caption,
    "trade_streaks":           streaks_caption,
    "trade_win_loss":          win_loss_caption,
    "mc_null":                 null_bootstrap_caption,
    "mc_fan":                  fan_chart_caption,
    "mc_terminal":             terminal_wealth_caption,
    "mc_drawdown":             drawdown_distribution_caption,
    "mc_sweep":                block_sweep_caption,
    "wf_summary":              wf_summary_caption,
    "wf_scatter":              wf_scatter_caption,
    "wf_excess":               wf_excess_caption,
    "wf_counts":               wf_trade_counts_caption,
    "rc":                      rc_caption,
    "rc_top_combos":           rc_top_combos_caption,
    "regime_overlay":          regime_overlay_caption,
    "regime_perf":             regime_performance_caption,
    "regime_bull_bear":        bull_bear_caption,
    "regime_beta":             rolling_beta_caption,
}


def build_captions(art) -> dict[str, str]:
    """Return {chart_key: caption_text} for the Tier 2 report."""
    from analytics.metrics import compute_metrics

    bm_metrics = None
    if art.benchmark is not None:
        try:
            bm_metrics = compute_metrics(art.benchmark)
        except Exception:
            bm_metrics = None

    mc = art.monte_carlo or {}
    wf = art.walk_forward or {}
    rc = art.whites_rc or {}

    out: dict[str, str] = {}
    for key, fn in CAPTIONS.items():
        try:
            if key.startswith("mc_"):
                out[key] = fn(mc)
            elif key.startswith("wf_"):
                out[key] = fn(wf)
            elif key.startswith("rc"):
                out[key] = fn(rc)
            elif key.startswith("trade_"):
                out[key] = fn(art.metrics)
            elif key in ("equity",):
                out[key] = fn(art.metrics, bm_metrics)
            elif key in ("excess", "cumret"):
                out[key] = fn(art.metrics)
            elif key in ("vol", "var", "ret_dist", "drawdown"):
                out[key] = fn(art.metrics)
            else:
                out[key] = fn()
        except Exception:
            out[key] = ""
    return out