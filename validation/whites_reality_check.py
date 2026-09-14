"""
White's Reality Check (2000).

Tests whether the BEST strategy in a universe beats a benchmark after
correcting for multiple testing across K strategies.

Null hypothesis: E[f_k,t] <= 0 for all k
Alternative:     There exists k with E[f_k,t] > 0

where f_k,t = strategy_k return - benchmark_k return at time t.

Bootstrap: stationary block bootstrap with the SAME resampled time
indices across all K columns. This preserves both autocorrelation
within each series and cross-sectional dependence between strategies.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------- bootstrap

def _stationary_block_indices(T: int, mean_block: float, rng) -> np.ndarray:
    """Politis & Romano (1994) stationary bootstrap indices.

    Blocks have geometrically distributed lengths with mean = mean_block.
    Start points are drawn uniformly from [0, T).
    """
    p = 1.0 / mean_block
    indices = np.empty(T, dtype=np.int64)
    pos = 0
    while pos < T:
        start = int(rng.integers(0, T))
        length = int(rng.geometric(p))
        end = min(pos + length, T)
        n = end - pos
        indices[pos:end] = (start + np.arange(n)) % T
        pos = end
    return indices


# ---------------------------------------------------------------- main test

def whites_reality_check(
    excess_returns: np.ndarray,
    n_bootstrap: int = 5000,
    mean_block: float | None = None,
    seed: int = 42,
    combo_labels: list[str] | None = None,
) -> dict:
    """Run White's Reality Check.

    Args:
        excess_returns: (T, K) array. Column k is combo k's per-bar
                        excess return over its same-exposure benchmark.
        n_bootstrap:    bootstrap iterations
        mean_block:     average block length for stationary bootstrap.
                        Defaults to sqrt(T).
        seed:           RNG seed
        combo_labels:   optional list of K labels for reporting

    Returns:
        dict with p-value, observed statistic, top-performing combos,
        and bootstrap distribution summary.
    """
    F = np.asarray(excess_returns, dtype=float)

    if F.ndim != 2:
        raise ValueError(f"excess_returns must be 2D, got shape {F.shape}")

    T, K = F.shape

    if T < 10:
        raise ValueError(f"need at least 10 bars, got T={T}")
    if K < 1:
        raise ValueError(f"need at least 1 combo, got K={K}")
    if np.isnan(F).any():
        raise ValueError("excess_returns contains NaNs")

    if mean_block is None:
        mean_block = max(5.0, np.sqrt(T))
    p = 1.0 / mean_block

    rng = np.random.default_rng(seed)

    # Observed test statistic
    obs_means = F.mean(axis=0)                # (K,)
    V_obs = np.sqrt(T) * float(obs_means.max())
    best_k = int(obs_means.argmax())

    # Center each column by its observed mean (H0)
    centered = F - obs_means                  # broadcast (T, K)

    # Bootstrap
    V_boots = np.empty(n_bootstrap, dtype=float)
    for b in range(n_bootstrap):
        idx = _stationary_block_indices(T, mean_block, rng)
        F_boot = centered[idx, :]             # (T, K) resampled
        boot_means = F_boot.mean(axis=0)      # (K,)
        V_boots[b] = np.sqrt(T) * float(boot_means.max())

    p_value = float((V_boots >= V_obs).mean())

    # Top performers
    top_order = np.argsort(obs_means)[::-1][:5]
    top_combos = []
    for k in top_order:
        label = (combo_labels[k] if combo_labels and k < len(combo_labels)
                 else f"combo_{k}")
        top_combos.append({
            "label": label,
            "mean_excess_return_per_bar": float(obs_means[k]),
            "annualized_excess_return": float(obs_means[k] * 252),
            "mean_excess_return_rank": int(np.where(top_order == k)[0][0]) + 1,
        })

    return {
        "method": "white_reality_check",
        "n_bootstrap": n_bootstrap,
        "T": int(T),
        "K": int(K),
        "mean_block": float(mean_block),
        "V_observed": float(V_obs),
        "best_combo": (
            combo_labels[best_k] if combo_labels and best_k < len(combo_labels)
            else f"combo_{best_k}"
        ),
        "best_mean_excess_return_per_bar": float(obs_means[best_k]),
        "best_annualized_excess_return": float(obs_means[best_k] * 252),
        "top_5_combos": top_combos,
        "V_bootstrap_mean": float(V_boots.mean()),
        "V_bootstrap_std": float(V_boots.std(ddof=1)),
        "V_bootstrap_p50": float(np.percentile(V_boots, 50)),
        "V_bootstrap_p95": float(np.percentile(V_boots, 95)),
        "V_bootstrap_p99": float(np.percentile(V_boots, 99)),
        "V_bootstrap_max": float(V_boots.max()),
        "p_value": p_value,
        "interpretation": (
            f"REJECT H0: at least one combo has significant edge "
            f"(p={p_value:.4f} < 0.05)"
            if p_value < 0.05
            else f"FAIL TO REJECT H0: best combo consistent with luck "
                 f"(p={p_value:.4f} >= 0.05)"
        ),
        "n_combos_with_positive_mean": int((obs_means > 0).sum()),
        "n_combos_with_negative_mean": int((obs_means < 0).sum()),
    }