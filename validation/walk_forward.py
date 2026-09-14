"""
Walk-forward validation with per-window benchmark comparison.

Splits data into rolling (train, test) windows:
    [---- train ----][-- test --]
        [---- train ----][-- test --]
            [---- train ----][-- test --]

Per window, computes:
  - IS Sharpe (in-sample)
  - OOS Sharpe (out-of-sample)
  - Benchmark OOS Sharpe (same-exposure passive, cost-charged)
  - Excess OOS Sharpe = strategy - benchmark

Also builds a CHAINED OOS equity curve — the concatenated OOS returns
from all windows, which recovers the full statistical power of the
out-of-sample period.

Key verdicts:
  robust (WF)  — degradation_ratio >= 0.5 and mean OOS Sharpe > 0
  has_edge     — chained OOS excess Sharpe > 0.2
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from analytics.metrics import compute_metrics
from engine.core import BacktestEngine
from engine.loader import call_strategy
from validation.monte_carlo import same_exposure_benchmark_cost_adjusted


# ---------------------------------------------------------------- helpers

def _resolve_ppy(index: pd.Index, fallback: float = 252.0) -> float:
    """Infer periods-per-year from a DatetimeIndex via bars / span-years."""
    if not isinstance(index, pd.DatetimeIndex) or len(index) < 3:
        return fallback
    span_days = (index[-1] - index[0]).days
    if span_days <= 0:
        return fallback
    return float(len(index) / (span_days / 365.25))


# ---------------------------------------------------------------- dataclass

@dataclass
class WalkForwardWindow:
    """One IS/OOS window's metrics."""
    window: int
    is_start: pd.Timestamp
    is_end: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp
    is_bars: int
    oos_bars: int
    is_metrics: dict = field(default_factory=dict)
    oos_metrics: dict = field(default_factory=dict)
    oos_benchmark_metrics: dict = field(default_factory=dict)
    oos_excess_sharpe: float = float("nan")
    oos_excess_CAGR: float = float("nan")
    low_confidence: bool = False
    # These are held in memory but not exported to CSV
    oos_equity: pd.Series | None = None
    oos_benchmark_equity: pd.Series | None = None


# ---------------------------------------------------------------- main

def walk_forward(
    df: pd.DataFrame,
    strategy_fn,
    strategy_params: dict | None = None,
    train_bars: int = 756,
    test_bars: int = 252,
    step_bars: int | None = None,
    warmup_bars: int = 0,
    engine_params: dict | None = None,
    periods_per_year: float | None = None,
    commission_bps: float = 1.0,
    slippage_bps: float = 5.0,
    compute_benchmark: bool = True,
    min_trades_high_confidence: int = 5,
) -> tuple[list[WalkForwardWindow], dict]:
    """Run walk-forward with per-window benchmark and chained OOS equity."""
    engine_params = engine_params or {}
    step_bars = step_bars or test_bars
    n = len(df)

    if train_bars + test_bars > n:
        raise ValueError(
            f"train+test ({train_bars}+{test_bars}) exceeds data length ({n})"
        )

    ppy = periods_per_year if periods_per_year is not None else _resolve_ppy(df.index)

    full_signals = call_strategy(strategy_fn, df, params=strategy_params)

    windows: list[WalkForwardWindow] = []
    start = 0
    win_idx = 0

    while start + train_bars + test_bars <= n:
        win_idx += 1
        is_start_i = start
        is_end_i = start + train_bars
        oos_start_i = is_end_i
        oos_end_i = oos_start_i + test_bars

        # --- IS window ---
        is_df = df.iloc[is_start_i:is_end_i]
        is_sig = full_signals.iloc[is_start_i:is_end_i]

        eng_is = BacktestEngine(**engine_params)
        is_eq = eng_is.run(is_df, is_sig)
        is_m = compute_metrics(is_eq, periods_per_year=ppy)

        # --- OOS window (with burn-in) ---
        burn_in = max(warmup_bars, 0)
        oos_ext_start_i = max(0, oos_start_i - burn_in)
        oos_df_ext = df.iloc[oos_ext_start_i:oos_end_i]
        oos_sig_ext = full_signals.iloc[oos_ext_start_i:oos_end_i]

        eng_oos = BacktestEngine(**engine_params)
        oos_eq_ext = eng_oos.run(oos_df_ext, oos_sig_ext)
        oos_eq = oos_eq_ext.iloc[oos_start_i - oos_ext_start_i:]
        oos_m = compute_metrics(oos_eq, periods_per_year=ppy)

        # --- Benchmark OOS window ---
        bm_metrics: dict = {}
        bm_eq = None
        excess_sharpe = float("nan")
        excess_cagr = float("nan")

        if compute_benchmark:
            # Benchmark on the pure OOS slice (no burn-in), same costs
            oos_df_slice = df.iloc[oos_start_i:oos_end_i]
            oos_sig_slice = full_signals.iloc[oos_start_i:oos_end_i]

            # Skip benchmark if strategy is entirely flat in this window
            if float(oos_sig_slice.abs().mean()) > 1e-9:
                bm_eq, _ = same_exposure_benchmark_cost_adjusted(
                    oos_df_slice, oos_sig_slice,
                    commission_bps=commission_bps,
                    slippage_bps=slippage_bps,
                )
                bm_metrics = compute_metrics(bm_eq, periods_per_year=ppy)
                excess_sharpe = oos_m.get("sharpe", np.nan) - bm_metrics.get("sharpe", np.nan)
                excess_cagr = oos_m.get("CAGR", np.nan) - bm_metrics.get("CAGR", np.nan)

        # --- Low confidence flag ---
        n_trades = oos_m.get("num_trades", 0)
        low_conf = n_trades < min_trades_high_confidence

        windows.append(WalkForwardWindow(
            window=win_idx,
            is_start=df.index[is_start_i],
            is_end=df.index[is_end_i - 1],
            oos_start=df.index[oos_start_i],
            oos_end=df.index[oos_end_i - 1],
            is_bars=len(is_df),
            oos_bars=len(oos_eq),
            is_metrics=is_m,
            oos_metrics=oos_m,
            oos_benchmark_metrics=bm_metrics,
            oos_excess_sharpe=float(excess_sharpe) if not np.isnan(excess_sharpe) else float("nan"),
            oos_excess_CAGR=float(excess_cagr) if not np.isnan(excess_cagr) else float("nan"),
            low_confidence=low_conf,
            oos_equity=oos_eq,
            oos_benchmark_equity=bm_eq,
        ))

        start += step_bars

    aggregate = _aggregate(windows, step_bars, ppy, compute_benchmark)
    return windows, aggregate


# ---------------------------------------------------------------- aggregation

def _aggregate(
    windows: list[WalkForwardWindow],
    step_bars: int,
    ppy: float,
    compute_benchmark: bool,
) -> dict:
    if not windows:
        return {"n_windows": 0, "error": "no windows produced"}

    is_sharpes = np.array([w.is_metrics.get("sharpe", np.nan) for w in windows], dtype=float)
    oos_sharpes = np.array([w.oos_metrics.get("sharpe", np.nan) for w in windows], dtype=float)
    excess_sharpes = np.array([w.oos_excess_sharpe for w in windows], dtype=float)

    is_clean = is_sharpes[~np.isnan(is_sharpes)]
    oos_clean = oos_sharpes[~np.isnan(oos_sharpes)]
    excess_clean = excess_sharpes[~np.isnan(excess_sharpes)]

    # Compute low confidence count before early return
    n_low_conf = sum(1 for w in windows if w.low_confidence)

    if len(oos_clean) == 0:
        return {
            "n_windows": len(windows),
            "n_low_confidence_windows": n_low_conf,
            "error": "all OOS windows NaN",
        }

    mean_is = float(is_clean.mean()) if len(is_clean) else float("nan")
    mean_oos = float(oos_clean.mean())
    degradation = (float(mean_oos / mean_is)
                   if mean_is and abs(mean_is) > 1e-9 else float("nan"))
    pct_positive = float((oos_clean > 0).mean())

    agg: dict = {
        "periods_per_year": float(ppy),
        "step_bars": int(step_bars),
        "n_windows": len(windows),
        "n_oos_clean": len(oos_clean),
        "n_low_confidence_windows": n_low_conf,
        "mean_IS_sharpe": mean_is,
        "mean_OOS_sharpe": mean_oos,
        "median_OOS_sharpe": float(np.median(oos_clean)),
        "std_OOS_sharpe": float(oos_clean.std(ddof=1)) if len(oos_clean) > 1 else 0.0,
        "min_OOS_sharpe": float(oos_clean.min()),
        "max_OOS_sharpe": float(oos_clean.max()),
        "pct_positive_OOS": pct_positive,
        "degradation_ratio": degradation,
        "robust": bool(
            not np.isnan(degradation)
            and degradation >= 0.5
            and mean_oos > 0
            and pct_positive >= 0.5
        ),
    }

    # --- Per-window excess Sharpe summary ---
    if compute_benchmark and len(excess_clean) > 0:
        agg["mean_OOS_excess_sharpe"] = float(excess_clean.mean())
        agg["median_OOS_excess_sharpe"] = float(np.median(excess_clean))
        agg["std_OOS_excess_sharpe"] = (
            float(excess_clean.std(ddof=1)) if len(excess_clean) > 1 else 0.0
        )
        agg["pct_positive_excess_OOS"] = float((excess_clean > 0).mean())
    else:
        agg["mean_OOS_excess_sharpe"] = float("nan")
        agg["median_OOS_excess_sharpe"] = float("nan")
        agg["std_OOS_excess_sharpe"] = float("nan")
        agg["pct_positive_excess_OOS"] = float("nan")

    # --- Chained OOS equity ---
    chained = _chain_oos(windows, step_bars, ppy, "oos_equity")
    if chained is not None and len(chained) > 2:
        agg["chained_OOS_sharpe"] = chained["sharpe"]
        agg["chained_OOS_CAGR"] = chained["CAGR"]
        agg["chained_OOS_maxdd"] = chained["max_drawdown"]
        agg["chained_OOS_bars"] = chained["n_bars"]

        # Chain the benchmark equity the same way
        bm_chain = _chain_oos(windows, step_bars, ppy, "oos_benchmark_equity")
        if bm_chain is not None and len(bm_chain) > 2:
            agg["chained_OOS_benchmark_sharpe"] = bm_chain["sharpe"]
            agg["chained_OOS_excess_sharpe"] = (
                agg["chained_OOS_sharpe"] - bm_chain["sharpe"]
            )
            agg["chained_OOS_excess_CAGR"] = (
                agg["chained_OOS_CAGR"] - bm_chain["CAGR"]
            )
        else:
            agg["chained_OOS_benchmark_sharpe"] = float("nan")
            agg["chained_OOS_excess_sharpe"] = float("nan")
            agg["chained_OOS_excess_CAGR"] = float("nan")
    else:
        agg["chained_OOS_sharpe"] = float("nan")
        agg["chained_OOS_CAGR"] = float("nan")
        agg["chained_OOS_maxdd"] = float("nan")
        agg["chained_OOS_bars"] = 0
        agg["chained_OOS_benchmark_sharpe"] = float("nan")
        agg["chained_OOS_excess_sharpe"] = float("nan")
        agg["chained_OOS_excess_CAGR"] = float("nan")

    # --- Edge verdict ---
    chained_excess = agg.get("chained_OOS_excess_sharpe", float("nan"))
    agg["has_edge"] = bool(
        not np.isnan(chained_excess) and chained_excess > 0.20
    )

    return agg


def _chain_oos(
    windows: list[WalkForwardWindow],
    step_bars: int,
    ppy: float,
    attr_name: str,
) -> dict | None:
    """Concatenate each window's first `step_bars` of OOS returns.

    Produces a non-overlapping chain spanning the full OOS period.
    Returns a metrics dict or None.
    """
    parts: list[pd.Series] = []
    for w in windows:
        eq = getattr(w, attr_name, None)
        if eq is None or len(eq) < 2:
            continue
        rets = eq.pct_change().dropna()
        if len(rets) == 0:
            continue
        # For overlapping windows, only take the FIRST step_bars so
        # no bar is counted twice.
        rets = rets.iloc[:step_bars] if len(rets) > step_bars else rets
        parts.append(rets)

    if not parts:
        return None

    chained = pd.concat(parts).sort_index()
    # Deduplicate overlapping indices (shouldn't happen with step slicing,
    # but be defensive)
    chained = chained[~chained.index.duplicated(keep="first")]

    if len(chained) < 3:
        return None

    eq = 100_000.0 * (1.0 + chained).cumprod()
    m = compute_metrics(eq, periods_per_year=ppy)
    m["n_bars"] = int(len(chained))
    return m


# ---------------------------------------------------------------- export

def windows_to_dataframe(windows: list[WalkForwardWindow]) -> pd.DataFrame:
    """Flatten window metrics to a DataFrame for CSV export.

    Excludes in-memory equity Series (only metrics + flags).
    """
    rows = []
    for w in windows:
        rows.append({
            "window": w.window,
            "is_start": w.is_start,
            "is_end": w.is_end,
            "oos_start": w.oos_start,
            "oos_end": w.oos_end,
            "is_bars": w.is_bars,
            "oos_bars": w.oos_bars,
            "is_sharpe": w.is_metrics.get("sharpe", np.nan),
            "is_CAGR": w.is_metrics.get("CAGR", np.nan),
            "is_maxdd": w.is_metrics.get("max_drawdown", np.nan),
            "oos_sharpe": w.oos_metrics.get("sharpe", np.nan),
            "oos_CAGR": w.oos_metrics.get("CAGR", np.nan),
            "oos_maxdd": w.oos_metrics.get("max_drawdown", np.nan),
            "oos_n_trades": w.oos_metrics.get("num_trades", 0),
            "oos_win_rate": w.oos_metrics.get("win_rate", np.nan),
            "oos_benchmark_sharpe": w.oos_benchmark_metrics.get("sharpe", np.nan),
            "oos_excess_sharpe": w.oos_excess_sharpe,
            "oos_excess_CAGR": w.oos_excess_CAGR,
            "low_confidence": w.low_confidence,
        })
    return pd.DataFrame(rows)