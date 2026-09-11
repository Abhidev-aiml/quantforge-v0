from __future__ import annotations
import numpy as np
import pandas as pd
from analytics.metrics import compute_metrics
from engine.core import BacktestEngine
def bootstrap_returns_iid(
    equity: pd.Series,
    n_sims: int = 5000,
    seed: int = 42,
) -> dict:
    """Resample daily returns with replacement; recompute Sharpe etc."""
    rng = np.random.default_rng(seed)
    rets = equity.pct_change().dropna().values
    n = len(rets)

    sharpes = np.empty(n_sims)
    cagrs   = np.empty(n_sims)
    maxdds  = np.empty(n_sims)

    for i in range(n_sims):
        sample = rng.choice(rets, size=n, replace=True)
        eq_sim = np.cumprod(1.0 + sample)
        s = pd.Series(eq_sim)
        m = compute_metrics(s)
        sharpes[i] = m["sharpe"]
        cagrs[i]   = m["CAGR"]
        maxdds[i]  = m["max_drawdown"]

    return _summarize(equity, sharpes, cagrs, maxdds, method="iid")


def _summarize(real_equity, sharpes, cagrs, maxdds, method: str) -> dict:
    real = compute_metrics(real_equity)
    return {
        "method": method,
        "n_sims": len(sharpes),
        "real_sharpe": real["sharpe"],
        "real_CAGR": real["CAGR"],
        "real_maxdd": real["max_drawdown"],
        # Distribution stats
        "sharpe_mean":  float(np.mean(sharpes)),
        "sharpe_std":   float(np.std(sharpes)),
        "sharpe_p05":   float(np.percentile(sharpes, 5)),
        "sharpe_p50":   float(np.percentile(sharpes, 50)),
        "sharpe_p95":   float(np.percentile(sharpes, 95)),
        # One-sided p-value: fraction of sims with Sharpe >= real
        "p_value_sharpe": float(np.mean(sharpes >= real["sharpe"])),
        "p_value_CAGR":   float(np.mean(cagrs   >= real["CAGR"])),
        # Probability of ruin (MaxDD worse than -50%)
        "prob_ruin":      float(np.mean(maxdds <= -0.50)),
    }

def bootstrap_returns_block(
    equity: pd.Series,
    n_sims: int = 5000,
    block_size: int = 20,
    seed: int = 42,
    ) -> dict:
    """Stationary block bootstrap; preserves short-range autocorrelation."""
    rng = np.random.default_rng(seed)
    rets = equity.pct_change().dropna().values
    n = len(rets)
    n_blocks = int(np.ceil(n / block_size))

    sharpes = np.empty(n_sims)
    cagrs   = np.empty(n_sims)
    maxdds  = np.empty(n_sims)

    for i in range(n_sims):
        starts = rng.integers(0, n - block_size, size=n_blocks)
        pieces = [rets[s:s + block_size] for s in starts]
        sample = np.concatenate(pieces)[:n]
        eq_sim = np.cumprod(1.0 + sample)
        m = compute_metrics(pd.Series(eq_sim))
        sharpes[i] = m["sharpe"]
        cagrs[i]   = m["CAGR"]
        maxdds[i]  = m["max_drawdown"]

    return _summarize(equity, sharpes, cagrs, maxdds,
                      method=f"block_{block_size}")

def bootstrap_trades(
    trades: pd.DataFrame,
    n_sims: int = 5000,
    seed: int = 42,
    ) -> dict:
    """Resample trades with replacement; rebuild an equity curve from returns."""
    if trades is None or len(trades) < 5:
        return {"method": "trade_bootstrap", "error": "need >= 5 trades"}

    rng = np.random.default_rng(seed)

    # Each trade's PnL as a fraction of the position's notional.
    notional = trades["qty"].values * trades["entry_price"].values
    pnl_pct  = trades["pnl"].values / notional

    n = len(pnl_pct)
    sharpes = np.empty(n_sims)
    cagrs   = np.empty(n_sims)
    maxdds  = np.empty(n_sims)
    finals  = np.empty(n_sims)

    # Assume trades are sequential; convert trade return to ~holding-period return
    # and reconstruct an equity curve of n trades.
    for i in range(n_sims):
        sample = rng.choice(pnl_pct, size=n, replace=True)
        eq_sim = np.cumprod(1.0 + sample)
        finals[i] = eq_sim[-1]
        # Annualize: strategy trades once per ~ (years * 252 / n) days on average
        years = 21.6   # from your data; in production, compute from trade timestamps
        trades_per_year = n / years
        ann_factor = trades_per_year ** 0.5     # rough Sharpe annualization
        rets = np.diff(np.concatenate([[1.0], eq_sim])) / np.concatenate([[1.0], eq_sim[:-1]])
        sharpes[i] = rets.mean() / rets.std() * ann_factor if rets.std() > 0 else 0
        cagrs[i]   = eq_sim[-1] ** (1 / years) - 1
        running_peak = np.maximum.accumulate(eq_sim)
        maxdds[i]  = (eq_sim / running_peak - 1).min()

    # Real trade PnL% for comparison
    real_eq = np.cumprod(1.0 + pnl_pct)
    real_final = real_eq[-1]
    real_sharpe = pnl_pct.mean() / pnl_pct.std() * (n / 21.6) ** 0.5 if pnl_pct.std() > 0 else 0
    real_cagr = real_final ** (1 / 21.6) - 1

    return {
        "method": "trade_bootstrap",
        "n_sims": n_sims,
        "n_trades": n,
        "real_sharpe": float(real_sharpe),
        "real_CAGR": float(real_cagr),
        "real_final_equity_mult": float(real_final),
        "sharpe_mean":  float(np.mean(sharpes)),
        "sharpe_p05":   float(np.percentile(sharpes, 5)),
        "sharpe_p50":   float(np.percentile(sharpes, 50)),
        "sharpe_p95":   float(np.percentile(sharpes, 95)),
        "p_value_sharpe": float(np.mean(sharpes >= real_sharpe)),
        "cagr_p05": float(np.percentile(cagrs, 5)),
        "cagr_p95": float(np.percentile(cagrs, 95)),
        "final_eq_p05": float(np.percentile(finals, 5)),
        "final_eq_p95": float(np.percentile(finals, 95)),
    }

def signal_permutation(
    df: pd.DataFrame,
    strategy_fn,
    n_sims: int = 200,       # expensive; fewer sims
    seed: int = 42,
    ) -> dict:
    """Shuffle log-returns to build synthetic price paths; rerun strategy."""
    rng = np.random.default_rng(seed)

    close = df["close"].values
    log_rets = np.diff(np.log(close))

    real_sig = strategy_fn(df)
    real_eng = BacktestEngine(initial_cash=100_000)
    real_eq = real_eng.run(df, real_sig)
    real_sharpe = compute_metrics(real_eq)["sharpe"]

    sharpes = np.empty(n_sims)
    for i in range(n_sims):
        shuffled = rng.permutation(log_rets)
        new_close = np.concatenate([[close[0]], close[0] * np.exp(np.cumsum(shuffled))])
        new_df = df.copy()
        # Rebuild OHLC roughly: keep intraday structure scale-consistent
        ratio = new_close / close
        new_df["close"] = new_close
        new_df["open"]  = df["open"].values  * ratio
        new_df["high"]  = df["high"].values  * ratio
        new_df["low"]   = df["low"].values   * ratio

        try:
            sig = strategy_fn(new_df)
            eng = BacktestEngine(initial_cash=100_000)
            eq = eng.run(new_df, sig)
            sharpes[i] = compute_metrics(eq)["sharpe"]
        except Exception:
            sharpes[i] = np.nan

    sharpes = sharpes[~np.isnan(sharpes)]
    return {
        "method": "signal_permutation",
        "n_sims": len(sharpes),
        "real_sharpe": float(real_sharpe),
        "perm_sharpe_mean": float(sharpes.mean()),
        "perm_sharpe_p05":  float(np.percentile(sharpes, 5)),
        "perm_sharpe_p50":  float(np.percentile(sharpes, 50)),
        "perm_sharpe_p95":  float(np.percentile(sharpes, 95)),
        "p_value":          float(np.mean(sharpes >= real_sharpe)),
    }
def bootstrap_returns_under_null(
    equity: pd.Series,
    n_sims: int = 5000,
    block_size: int = 20,
    seed: int = 42,
    ) -> dict:
    """
    Bootstrap under H0: true Sharpe = 0.

    We subtract the mean return so the null distribution has zero drift,
    preserving volatility, skew, and kurtosis. Then bootstrap blocks.
    p-value = P(null Sharpe >= observed Sharpe)
    """
    rng = np.random.default_rng(seed)
    rets = equity.pct_change().dropna().values
    n = len(rets)

    # Observed Sharpe (annualized, rf=0)
    mu_obs = rets.mean()
    sd_obs = rets.std(ddof=1)
    sharpe_obs = (mu_obs / sd_obs * np.sqrt(252)) if sd_obs > 0 else 0.0

    # Force zero mean, keep everything else
    rets_null = rets - mu_obs

    n_blocks = int(np.ceil(n / block_size))
    sharpes_null = np.empty(n_sims)

    for i in range(n_sims):
        starts = rng.integers(0, n - block_size, size=n_blocks)
        pieces = [rets_null[s:s + block_size] for s in starts]
        sample = np.concatenate(pieces)[:n]
        mu = sample.mean()
        sd = sample.std(ddof=1)
        sharpes_null[i] = (mu / sd * np.sqrt(252)) if sd > 0 else 0.0

    return {
        "method": f"null_block_{block_size}",
        "n_sims": n_sims,
        "observed_sharpe": float(sharpe_obs),
        "null_sharpe_mean": float(sharpes_null.mean()),
        "null_sharpe_std": float(sharpes_null.std()),
        "null_sharpe_p05": float(np.percentile(sharpes_null, 5)),
        "null_sharpe_p95": float(np.percentile(sharpes_null, 95)),
        "p_value_one_sided": float((sharpes_null >= sharpe_obs).mean()),
        "p_value_two_sided": float(
            (np.abs(sharpes_null) >= abs(sharpe_obs)).mean()
        ),
    }
def signal_block_shuffle(
    df: pd.DataFrame,
    strategy_fn,
    block_size: int = 60,
    n_sims: int = 500,
    commission_bps: float = 1.0,
    slippage_bps: float = 5.0,
    seed: int = 42,
    ) -> dict:
    """
    Shuffle the strategy's signals in blocks of size `block_size`.
    Preserves signal proportions and local serial structure.
    Destroys alignment between signal and price.

    p-value = P(shuffled Sharpe >= observed Sharpe)
    """
    rng = np.random.default_rng(seed)

    # Real run
    real_sig = strategy_fn(df)
    eng = BacktestEngine(initial_cash=100_000,
                         commission_bps=commission_bps,
                         slippage_bps=slippage_bps)
    eq = eng.run(df, real_sig)
    sharpe_obs = compute_metrics(eq)["sharpe"]

    sig_vals = real_sig.values
    n = len(sig_vals)
    n_full_blocks = n // block_size
    tail = sig_vals[n_full_blocks * block_size:]

    sharpes = np.empty(n_sims)
    for i in range(n_sims):
        order = rng.permutation(n_full_blocks)
        blocks = [sig_vals[j*block_size:(j+1)*block_size] for j in order]
        shuffled = np.concatenate(blocks + ([tail] if len(tail) else []))
        sig = pd.Series(shuffled, index=df.index)
        eng = BacktestEngine(initial_cash=100_000,
                             commission_bps=commission_bps,
                             slippage_bps=slippage_bps)
        eq = eng.run(df, sig)
        sharpes[i] = compute_metrics(eq)["sharpe"]

    return {
        "method": f"signal_shuffle_block_{block_size}",
        "n_sims": n_sims,
        "observed_sharpe": float(sharpe_obs),
        "null_sharpe_mean": float(sharpes.mean()),
        "null_sharpe_std": float(sharpes.std()),
        "null_sharpe_p05": float(np.percentile(sharpes, 5)),
        "null_sharpe_p95": float(np.percentile(sharpes, 95)),
        "p_value": float((sharpes >= sharpe_obs).mean()),
    }
def run_all_tests(
    df: pd.DataFrame,
    strategy_fn,
    equity: pd.Series,
    trades: pd.DataFrame,
    block_size: int,
    n_sims: int = 5000,
    n_perm: int = 500,
    seed: int = 42,
 ) -> dict:
    """Run corrected tests. block_size should match avg holding period."""
    return {
        "null_bootstrap": bootstrap_returns_under_null(
            equity, n_sims=n_sims, block_size=block_size, seed=seed
        ),
        "signal_shuffle": signal_block_shuffle(
            df, strategy_fn, block_size=block_size,
            n_sims=n_perm, seed=seed
        ),
        # Keep the CIs from the old tests — they're still useful
        "iid_ci": bootstrap_returns_iid(equity, n_sims=n_sims, seed=seed),
        "trade_ci": bootstrap_trades(trades, n_sims=n_sims, seed=seed),
    }