"""
Monte Carlo validation primitives.

All functions accept `periods_per_year` for annualization and, where
they construct engines, cost parameters that must match the experiment.

Timeframe-agnostic: works for daily (252), 4H (~1512), 1H (~6048), etc.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analytics.metrics import compute_metrics
from engine.core import BacktestEngine


# ---------------------------------------------------------------- helpers

def _annualize_sharpe(returns: np.ndarray, ppy: float) -> float:
    """Compute annualized Sharpe from a return series."""
    if len(returns) < 2:
        return 0.0
    sd = returns.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(returns.mean() / sd * np.sqrt(ppy))


def _infer_periods_per_year(index: pd.DatetimeIndex,
                            default: float = 252.0) -> float:
    """Infer bars-per-year from a DatetimeIndex.

    Uses total bars / span-in-years. This is timeframe-agnostic and
    naturally returns ~252 for business-day data, ~365 for calendar-day,
    ~8760 for hourly, and so on.
    """
    if not isinstance(index, pd.DatetimeIndex) or len(index) < 3:
        return default
    span_days = (index[-1] - index[0]).days
    if span_days <= 0:
        return default
    years = span_days / 365.25
    return len(index) / years


# ---------------------------------------------------------------- return bootstraps

def bootstrap_returns_iid(
    equity: pd.Series,
    n_sims: int = 5000,
    periods_per_year: float | None = None,
    seed: int = 42,
) -> dict:
    """IID resample of returns. Informational CI (not a p-value)."""
    rng = np.random.default_rng(seed)
    rets = equity.pct_change().dropna().values
    n = len(rets)
    ppy = periods_per_year or _infer_periods_per_year(equity.index)

    sharpes = np.empty(n_sims)
    cagrs = np.empty(n_sims)
    maxdds = np.empty(n_sims)

    for i in range(n_sims):
        sample = rng.choice(rets, size=n, replace=True)
        eq_sim = np.cumprod(1.0 + sample)
        s = pd.Series(eq_sim)
        m = compute_metrics(s, periods_per_year=ppy)
        sharpes[i] = m["sharpe"]
        cagrs[i] = m["CAGR"]
        maxdds[i] = m["max_drawdown"]

    real = compute_metrics(equity, periods_per_year=ppy)
    return {
        "method": "iid",
        "n_sims": n_sims,
        "periods_per_year": float(ppy),
        "real_sharpe": real["sharpe"],
        "real_CAGR": real["CAGR"],
        "real_maxdd": real["max_drawdown"],
        "sharpe_mean": float(np.mean(sharpes)),
        "sharpe_std": float(np.std(sharpes)),
        "sharpe_p05": float(np.percentile(sharpes, 5)),
        "sharpe_p50": float(np.percentile(sharpes, 50)),
        "sharpe_p95": float(np.percentile(sharpes, 95)),
        "p_value_sharpe": float(np.mean(sharpes >= real["sharpe"])),
        "p_value_CAGR": float(np.mean(cagrs >= real["CAGR"])),
        "prob_ruin": float(np.mean(maxdds <= -0.50)),
    }


def bootstrap_returns_block(
    equity: pd.Series,
    n_sims: int = 5000,
    block_size: int = 20,
    periods_per_year: float | None = None,
    seed: int = 42,
) -> dict:
    """Stationary block bootstrap. Preserves short-range autocorrelation."""
    rng = np.random.default_rng(seed)
    rets = equity.pct_change().dropna().values
    n = len(rets)
    ppy = periods_per_year or _infer_periods_per_year(equity.index)
    n_blocks = int(np.ceil(n / block_size))

    sharpes = np.empty(n_sims)
    cagrs = np.empty(n_sims)
    maxdds = np.empty(n_sims)

    for i in range(n_sims):
        starts = rng.integers(0, n - block_size, size=n_blocks)
        sample = np.concatenate([rets[s:s + block_size] for s in starts])[:n]
        eq_sim = np.cumprod(1.0 + sample)
        m = compute_metrics(pd.Series(eq_sim), periods_per_year=ppy)
        sharpes[i] = m["sharpe"]
        cagrs[i] = m["CAGR"]
        maxdds[i] = m["max_drawdown"]

    real = compute_metrics(equity, periods_per_year=ppy)
    return {
        "method": f"block_{block_size}",
        "n_sims": n_sims,
        "periods_per_year": float(ppy),
        "real_sharpe": real["sharpe"],
        "real_CAGR": real["CAGR"],
        "real_maxdd": real["max_drawdown"],
        "sharpe_mean": float(np.mean(sharpes)),
        "sharpe_std": float(np.std(sharpes)),
        "sharpe_p05": float(np.percentile(sharpes, 5)),
        "sharpe_p50": float(np.percentile(sharpes, 50)),
        "sharpe_p95": float(np.percentile(sharpes, 95)),
        "p_value_sharpe": float(np.mean(sharpes >= real["sharpe"])),
        "p_value_CAGR": float(np.mean(cagrs >= real["CAGR"])),
        "prob_ruin": float(np.mean(maxdds <= -0.50)),
    }


def bootstrap_returns_under_null(
    equity: pd.Series,
    n_sims: int = 5000,
    block_size: int = 20,
    periods_per_year: float | None = None,
    seed: int = 42,
) -> dict:
    """Null bootstrap with zero-mean return series.

    p-value = P(zero-mean world produces Sharpe ≥ observed).
    """
    rng = np.random.default_rng(seed)
    rets = equity.pct_change().dropna().values
    n = len(rets)
    ppy = periods_per_year or _infer_periods_per_year(equity.index)

    mu_obs = rets.mean()
    sd_obs = rets.std(ddof=1)
    sharpe_obs = (mu_obs / sd_obs * np.sqrt(ppy)) if sd_obs > 0 else 0.0

    rets_null = rets - mu_obs  # enforce zero mean
    n_blocks = int(np.ceil(n / block_size))

    sharpes_null = np.empty(n_sims)
    for i in range(n_sims):
        starts = rng.integers(0, n - block_size, size=n_blocks)
        sample = np.concatenate([rets_null[s:s + block_size]
                                 for s in starts])[:n]
        sharpes_null[i] = _annualize_sharpe(sample, ppy)

    return {
        "method": f"null_block_{block_size}",
        "n_sims": n_sims,
        "periods_per_year": float(ppy),
        "observed_sharpe": float(sharpe_obs),
        "null_sharpe_mean": float(sharpes_null.mean()),
        "null_sharpe_std": float(sharpes_null.std()),
        "null_sharpe_p05": float(np.percentile(sharpes_null, 5)),
        "null_sharpe_p95": float(np.percentile(sharpes_null, 95)),
        "p_value_one_sided": float((sharpes_null >= sharpe_obs).mean()),
        "p_value_two_sided": float((np.abs(sharpes_null) >= abs(sharpe_obs)).mean()),
    }


# ---------------------------------------------------------------- trade bootstraps

def _infer_trade_years(trades: pd.DataFrame) -> float:
    """Infer elapsed years from trade timestamps, or fall back to len heuristic."""
    if "entry_ts" in trades.columns and "exit_ts" in trades.columns:
        try:
            entry = pd.to_datetime(trades["entry_ts"])
            exit_ = pd.to_datetime(trades["exit_ts"])
            span_days = (exit_.max() - entry.min()).days
            if span_days > 0:
                return span_days / 365.25
        except Exception:
            pass
    # Fallback: assume one trade every 5 business days
    return len(trades) * 5 / 252.0


def bootstrap_trades(
    trades: pd.DataFrame,
    n_sims: int = 5000,
    periods_per_year: float | None = None,
    elapsed_years: float | None = None,
    seed: int = 42,
) -> dict:
    """IID resample of trade percentage returns. Approximate."""
    if trades is None or len(trades) < 5:
        return {"method": "trade_bootstrap", "error": "need >= 5 trades"}

    rng = np.random.default_rng(seed)
    notional = trades["qty"].values * trades["entry_price"].values
    pnl_pct = trades["pnl"].values / notional
    n = len(pnl_pct)

    years = elapsed_years or _infer_trade_years(trades)
    ppy = periods_per_year or (n / years if years > 0 else 252.0)

    sharpes = np.empty(n_sims)
    finals = np.empty(n_sims)

    for i in range(n_sims):
        sample = rng.choice(pnl_pct, size=n, replace=True)
        eq_sim = np.cumprod(1.0 + sample)
        finals[i] = eq_sim[-1]
        rets = np.diff(eq_sim, prepend=1.0) / eq_sim
        sharpes[i] = _annualize_sharpe(rets, ppy)

    real_eq = np.cumprod(1.0 + pnl_pct)
    real_sharpe = _annualize_sharpe(pnl_pct, ppy)
    if years > 0 and real_eq[-1] > 0:
        real_cagr = real_eq[-1] ** (1.0 / years) - 1.0
    else:
        real_cagr = np.nan

    return {
        "method": "trade_bootstrap",
        "n_sims": n_sims,
        "n_trades": n,
        "elapsed_years": float(years),
        "periods_per_year": float(ppy),
        "real_sharpe": float(real_sharpe),
        "real_CAGR": float(real_cagr),
        "real_final_equity_mult": float(real_eq[-1]),
        "sharpe_mean": float(np.mean(sharpes)),
        "sharpe_p05": float(np.percentile(sharpes, 5)),
        "sharpe_p50": float(np.percentile(sharpes, 50)),
        "sharpe_p95": float(np.percentile(sharpes, 95)),
        "p_value_sharpe": float(np.mean(sharpes >= real_sharpe)),
        "final_eq_p05": float(np.percentile(finals, 5)),
        "final_eq_p95": float(np.percentile(finals, 95)),
    }


def bootstrap_trades_block(
    trades: pd.DataFrame,
    n_sims: int = 5000,
    block_size: int = 5,
    periods_per_year: float | None = None,
    elapsed_years: float | None = None,
    seed: int = 42,
) -> dict:
    """Block bootstrap over trades. Preserves short runs of wins/losses."""
    if trades is None or len(trades) < 5:
        return {"method": "trade_block_bootstrap", "error": "need >= 5 trades"}

    rng = np.random.default_rng(seed)
    notional = trades["qty"].values * trades["entry_price"].values
    pnl_pct = trades["pnl"].values / notional
    n = len(pnl_pct)

    if n < block_size:
        return {"method": "trade_block_bootstrap",
                "error": f"need >= {block_size} trades"}

    years = elapsed_years or _infer_trade_years(trades)
    ppy = periods_per_year or (n / years if years > 0 else 252.0)

    n_blocks = int(np.ceil(n / block_size))
    sharpes = np.empty(n_sims)
    cagrs = np.empty(n_sims)

    for i in range(n_sims):
        starts = rng.integers(0, n - block_size, size=n_blocks)
        sample = np.concatenate([pnl_pct[s:s + block_size]
                                 for s in starts])[:n]
        eq_sim = np.cumprod(1.0 + sample)
        rets = np.diff(eq_sim, prepend=1.0) / eq_sim
        sharpes[i] = _annualize_sharpe(rets, ppy)
        if years > 0 and eq_sim[-1] > 0:
            cagrs[i] = eq_sim[-1] ** (1.0 / years) - 1.0
        else:
            cagrs[i] = np.nan

    real_eq = np.cumprod(1.0 + pnl_pct)
    real_sharpe = _annualize_sharpe(pnl_pct, ppy)
    real_cagr = real_eq[-1] ** (1.0 / years) - 1.0 if years > 0 else np.nan

    return {
        "method": f"trade_block_bootstrap_{block_size}",
        "n_sims": n_sims,
        "n_trades": n,
        "elapsed_years": float(years),
        "periods_per_year": float(ppy),
        "real_sharpe": float(real_sharpe),
        "real_CAGR": float(real_cagr),
        "sharpe_p05": float(np.percentile(sharpes, 5)),
        "sharpe_p50": float(np.percentile(sharpes, 50)),
        "sharpe_p95": float(np.percentile(sharpes, 95)),
        "p_value_sharpe": float(np.mean(sharpes >= real_sharpe)),
        "cagr_p05": float(np.percentile(cagrs, 5)),
        "cagr_p95": float(np.percentile(cagrs, 95)),
    }


# ---------------------------------------------------------------- signal shuffle

def signal_block_shuffle(
    df: pd.DataFrame,
    strategy_fn,
    block_size: int = 60,
    n_sims: int = 500,
    commission_bps: float = 1.0,
    slippage_bps: float = 5.0,
    initial_cash: float = 100_000.0,
    no_trade_band: float = 0.01,
    warmup_bars: int = 0,
    periods_per_year: float | None = None,
    seed: int = 42,
) -> dict:
    """Shuffle the strategy's signals in blocks. Tests timing skill.

    Uses the SAME execution parameters as the observed run so the
    comparison is apples-to-apples.
    """
    rng = np.random.default_rng(seed)
    ppy = periods_per_year or _infer_periods_per_year(df.index)

    # --- observed run ---
    real_sig = strategy_fn(df)
    eng = BacktestEngine(
        initial_cash=initial_cash,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        no_trade_band=no_trade_band,
        warmup_bars=warmup_bars,
    )
    real_eq = eng.run(df, real_sig)
    real_sharpe = compute_metrics(real_eq, periods_per_year=ppy)["sharpe"]

    # --- shuffle sweep ---
    sig_vals = real_sig.values
    n = len(sig_vals)
    n_full_blocks = n // block_size
    tail = sig_vals[n_full_blocks * block_size:]

    sharpes = np.empty(n_sims)
    for i in range(n_sims):
        order = rng.permutation(n_full_blocks)
        blocks = [sig_vals[j * block_size:(j + 1) * block_size]
                  for j in order]
        shuffled = np.concatenate(blocks + ([tail] if len(tail) else []))
        sig = pd.Series(shuffled, index=df.index)

        eng = BacktestEngine(
            initial_cash=initial_cash,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            no_trade_band=no_trade_band,
            warmup_bars=warmup_bars,
        )
        eq = eng.run(df, sig)
        sharpes[i] = compute_metrics(eq, periods_per_year=ppy)["sharpe"]

    return {
        "method": f"signal_shuffle_block_{block_size}",
        "n_sims": n_sims,
        "periods_per_year": float(ppy),
        "observed_sharpe": float(real_sharpe),
        "null_sharpe_mean": float(sharpes.mean()),
        "null_sharpe_std": float(sharpes.std()),
        "null_sharpe_p05": float(np.percentile(sharpes, 5)),
        "null_sharpe_p95": float(np.percentile(sharpes, 95)),
        "p_value": float((sharpes >= real_sharpe).mean()),
    }


# ---------------------------------------------------------------- benchmark

def same_exposure_benchmark_cost_adjusted(
    df: pd.DataFrame,
    signals: pd.Series,
    commission_bps: float = 1.0,
    slippage_bps: float = 5.0,
) -> tuple[pd.Series, float]:
    """Passive benchmark at strategy's average weight, charged the
    strategy's cost drag. Returns (benchmark_equity, avg_weight).
    """
    w = float(signals.mean())
    w = max(-1.0, min(1.0, w))

    rets = df["close"].pct_change().fillna(0.0)
    turnover_per_bar = signals.diff().abs().mean()
    cost_per_bar = turnover_per_bar * (commission_bps + slippage_bps) / 1e4

    bench_rets = w * rets - cost_per_bar
    bench_eq = 100_000 * (1 + bench_rets).cumprod()
    return bench_eq, w

def simulate_equity_paths(
    equity: pd.Series,
    n_sims: int = 5000,
    block_size: int = 20,
    n_paths_saved: int = 200,
    max_bars: int = 400,
    periods_per_year: float | None = None,
    seed: int = 42,
) -> dict:
    """
    Run block-bootstrap Monte Carlo on a return series and return:
      - percentile bands over time (p05, p25, p50, p75, p95)
      - a sample of n_paths_saved simulated equity paths (downsampled)
      - terminal wealth array (all n_sims)
      - max drawdown array (all n_sims)
      - observed equity curve downsampled for overlay

    All arrays are downsampled to at most `max_bars` points so the
    output JSON stays small.

    Uses block bootstrap to preserve autocorrelation, which matters for
    trend strategies whose returns have persistence.
    """
    rets = equity.pct_change().dropna().values
    n = len(rets)
    if n < block_size * 3:
        raise ValueError(f"Series too short: {n} returns, need > {block_size * 3}")

    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_size))

    # Downsample indices for the bands and paths — we keep every k-th bar
    step = max(1, n // max_bars)
    kept = np.arange(0, n, step)[:max_bars]
    n_kept = len(kept)

    # Storage for percentile bands at every kept bar
    sim_curves = np.empty((n_sims, n_kept), dtype=np.float64)
    terminal = np.empty(n_sims, dtype=np.float64)
    max_dd_arr = np.empty(n_sims, dtype=np.float64)

    # Sampled paths to keep whole
    paths_sample = np.empty((n_paths_saved, n_kept), dtype=np.float64)
    sampled_idx = rng.choice(n_sims, size=min(n_paths_saved, n_sims), replace=False)
    sampled_idx = set(int(i) for i in sampled_idx)

    for i in range(n_sims):
        starts = rng.integers(0, n - block_size, size=n_blocks)
        sample = np.concatenate([rets[s:s + block_size] for s in starts])[:n]
        eq = np.cumprod(1.0 + sample)

        sim_curves[i] = eq[kept]
        terminal[i] = eq[-1]
        running_peak = np.maximum.accumulate(eq)
        max_dd_arr[i] = float((eq / running_peak - 1.0).min())

        if i in sampled_idx:
            paths_sample[len([k for k in sampled_idx if k <= i]) - 1] = eq[kept]

    # Percentile bands across simulations at each kept bar
    bands = {
        "p05": np.percentile(sim_curves, 5, axis=0).tolist(),
        "p25": np.percentile(sim_curves, 25, axis=0).tolist(),
        "p50": np.percentile(sim_curves, 50, axis=0).tolist(),
        "p75": np.percentile(sim_curves, 75, axis=0).tolist(),
        "p95": np.percentile(sim_curves, 95, axis=0).tolist(),
    }

    # Observed equity downsampled to the same grid (post first return)
    obs = equity.iloc[1:].values
    obs = obs / obs[0]  # normalize to 1.0
    obs_kept = obs[kept].tolist()

    # Only keep real sampled paths (in case n_sims < n_paths_saved)
    paths_sample = paths_sample[: len(sampled_idx)]

    return {
        "n_sims": int(n_sims),
        "n_paths_saved": int(len(paths_sample)),
        "n_bars": int(n_kept),
        "downsample_step": int(step),
        "percentile_bands": bands,
        "paths_sample": paths_sample.tolist(),
        "terminal_wealth": terminal.tolist(),
        "max_drawdown": max_dd_arr.tolist(),
        "observed_equity": obs_kept,
    }