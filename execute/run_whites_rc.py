"""
White's Reality Check runner over the full strategy × asset universe.

Builds the (T, K) excess-return matrix and runs White's RC.

Usage:
    python -m execute.run_whites_rc
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from engine.data import load_csv
from engine.core import BacktestEngine
from engine.loader import load_strategy, validate_signals, call_strategy
from engine.multi_data import discover_symbols
from validation.whites_reality_check import whites_reality_check


# ---------------------------------------------------------------- config

STRATEGIES = [
    "strategies/01a_goldencross_sma_50_200.py",
    "strategies/01b_goldencross_ema_50_200.py",
    "strategies/01c_goldencross_ema_30_100.py",
    "strategies/01d_goldencross_ema_20_60.py",
    "strategies/01e_goldencross_ema_10_50.py",
]

DATA_DIR = "data/raw/daily"
PATTERN = "xauusd_1D_comma.csv"

COMMISSION_BPS = 1.0
SLIPPAGE_BPS = 5.0
INITIAL_CASH = 100_000.0
N_BOOTSTRAP = 5000
SEED = 42


# ---------------------------------------------------------------- helpers

def _latest_run_for_strategy(strategy_path: str) -> Path | None:
    """Find the most recent run dir whose manifest points at this strategy."""
    strat_stem = Path(strategy_path).stem
    candidates = []
    for r in Path("results/runs").glob("*/"):
        m = r / "manifest.json"
        if not m.exists():
            continue
        try:
            man = json.loads(m.read_text())
            sp = man.get("config", {}).get("strategy", {}).get("path", "")
            if Path(sp).stem == strat_stem:
                candidates.append((r.stat().st_mtime, r))
        except Exception:
            continue
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[0])[1]


def load_all_assets(paths: dict[str, str]) -> dict[str, pd.DataFrame]:
    """Load every asset once."""
    out = {}
    for name, path in paths.items():
        try:
            out[name] = load_csv(path)
        except Exception as e:
            print(f"  ⚠️ Could not load {name}: {e}")
    return out


def common_index(data: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    """Intersection of all assets' date ranges."""
    idx = None
    for df in data.values():
        idx = df.index if idx is None else idx.intersection(df.index)
    if idx is None or len(idx) < 10:
        raise ValueError("common index has too few bars")
    return idx.sort_values()


def compute_excess_returns(
    df: pd.DataFrame,
    strategy_fn,
    strategy_params: dict | None = None,
) -> tuple[pd.Series, dict]:
    """Return (excess_returns_series, info_dict) for one combo.

    excess_t = strategy_return_t - (avg_weight * asset_return_t)

    The benchmark is a passive investment with the strategy's average
    exposure, zero costs. Strategy returns already include costs.
    """
    params = strategy_params or {}
    raw_sig = call_strategy(strategy_fn, df, params=params)
    sig = validate_signals(raw_sig, df)

    engine = BacktestEngine(
        initial_cash=INITIAL_CASH,
        commission_bps=COMMISSION_BPS,
        slippage_bps=SLIPPAGE_BPS,
    )
    equity = engine.run(df, sig)

    strat_rets = equity.pct_change().fillna(0.0)
    asset_rets = df["close"].pct_change().fillna(0.0)
    avg_w = float(sig.mean())
    passive_rets = avg_w * asset_rets

    excess = strat_rets - passive_rets

    info = {
        "avg_weight": avg_w,
        "n_trades": len(engine.pf.fills),
        "strategy_sharpe": float(strat_rets.mean() / strat_rets.std(ddof=1) * np.sqrt(252))
                           if strat_rets.std(ddof=1) > 0 else 0.0,
        "passive_sharpe": float(passive_rets.mean() / passive_rets.std(ddof=1) * np.sqrt(252))
                          if passive_rets.std(ddof=1) > 0 else 0.0,
    }
    return excess, info


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n-bootstrap", type=int, default=N_BOOTSTRAP)
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--dry-run", action="store_true",
                   help="list combos without running the test")
    args = p.parse_args()

    print("=" * 78)
    print("WHITE'S REALITY CHECK — CROSS-ASSET MULTIPLE-TESTING CORRECTION")
    print("=" * 78)

    # --- Discover assets + strategies ---
    asset_paths = discover_symbols(DATA_DIR, pattern=PATTERN)
    print(f"\nAssets discovered: {len(asset_paths)}")
    print(f"Strategies:        {len(STRATEGIES)}")
    print(f"Total combos:      {len(asset_paths) * len(STRATEGIES)}")

    if args.dry_run:
        for name in asset_paths:
            print(f"  asset: {name}")
        for s in STRATEGIES:
            print(f"  strategy: {s}")
        return

    # --- Load all assets once ---
    print(f"\nLoading assets...")
    data_all = load_all_assets(asset_paths)
    print(f"  loaded {len(data_all)} assets")

    # --- Common index ---
    idx = common_index(data_all)
    print(f"\nCommon index: {len(idx)} bars")
    print(f"  {idx[0].date()} → {idx[-1].date()}")
    print(f"  (intersection of all asset date ranges)")

    # --- Build F matrix ---
    T = len(idx)
    K = len(data_all) * len(STRATEGIES)
    F = np.zeros((T, K))
    labels = []
    combo_info = []
    k = 0
    skipped = 0

    print(f"\nBuilding excess-return matrix ({T} bars × {K} combos)...")
    for strat_path in STRATEGIES:
        try:
            fn = load_strategy(strat_path)
        except Exception as e:
            print(f"  ⚠️ Could not load {strat_path}: {e}")
            skipped += len(data_all)
            continue

        strat_name = Path(strat_path).stem
        for asset_name, df_full in data_all.items():
            # Slice to common index
            df = df_full.reindex(idx).ffill()
            if len(df) < 50:
                skipped += 1
                continue
            try:
                excess, info = compute_excess_returns(df, fn)
                F[:, k] = excess.values
                labels.append(f"{strat_name} × {asset_name}")
                combo_info.append({"combo": labels[-1], **info})
                k += 1
            except Exception as e:
                print(f"  ⚠️ {strat_name} × {asset_name}: {e}")
                skipped += 1

    # Trim to actual
    F = F[:, :k]
    labels = labels[:k]

    print(f"  valid combos: {k}  (skipped: {skipped})")

    if k < 1:
        print("❌ No valid combos. Exiting.")
        return

    # --- Summary of raw excess returns ---
    obs_means = F.mean(axis=0) * 252  # annualized
    print(f"\nRaw annualized excess returns across {k} combos:")
    print(f"  mean:     {obs_means.mean()*100:+.2f}%")
    print(f"  median:   {np.median(obs_means)*100:+.2f}%")
    print(f"  min:      {obs_means.min()*100:+.2f}%")
    print(f"  max:      {obs_means.max()*100:+.2f}%")
    print(f"  positive: {(obs_means > 0).sum()}/{k}")

    # --- Run White's RC ---
    print(f"\nRunning White's Reality Check "
          f"(n_bootstrap={args.n_bootstrap}, seed={args.seed})...")
    result = whites_reality_check(
        F, n_bootstrap=args.n_bootstrap, seed=args.seed,
        combo_labels=labels,
    )

    # --- Report ---
    print(f"\n" + "=" * 78)
    print("RESULT")
    print("=" * 78)
    print(f"  T (bars):                      {result['T']}")
    print(f"  K (combos):                    {result['K']}")
    print(f"  Mean block length:             {result['mean_block']:.1f}")
    print()
    print(f"  Best combo:                    {result['best_combo']}")
    print(f"  Best annualized excess return: "
          f"{result['best_annualized_excess_return']*100:+.2f}%")
    print(f"  Observed V statistic:          {result['V_observed']:.4f}")
    print()
    print(f"  Bootstrap V mean:              {result['V_bootstrap_mean']:.4f}")
    print(f"  Bootstrap V std:               {result['V_bootstrap_std']:.4f}")
    print(f"  Bootstrap V 95th percentile:   {result['V_bootstrap_p95']:.4f}")
    print(f"  Bootstrap V 99th percentile:   {result['V_bootstrap_p99']:.4f}")
    print()
    print(f"  ** p-value:                    {result['p_value']:.4f}")
    print(f"  ** Verdict:                    {result['interpretation']}")
    print()
    print(f"  Combos with positive mean:     "
          f"{result['n_combos_with_positive_mean']}/{result['K']}")
    print(f"  Combos with negative mean:     "
          f"{result['n_combos_with_negative_mean']}/{result['K']}")

    print(f"\n  Top 5 combos by excess return:")
    for tc in result["top_5_combos"]:
        print(f"    {tc['label']:<45}  "
              f"{tc['annualized_excess_return']*100:+7.2f}%/yr")

    # --- Save artifacts ---
    run_dir = Path("results") / "whites_rc" / datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "whites_rc.json").write_text(json.dumps(result, indent=2, default=str))

    # Combo details
    combo_df = pd.DataFrame(combo_info)
    combo_df["mean_excess_per_bar"] = obs_means / 252
    combo_df.to_csv(run_dir / "combos.csv", index=False)

    # Attach the RC result to each participating strategy's latest run
    # so reporting.build can render the "White's RC significant" verdict.
    print("\nAttaching RC result to run directories...")
    for strat_path in STRATEGIES:
        attach_dir = _latest_run_for_strategy(strat_path)
        if attach_dir is None:
            print(f"  ⚠️  no run found for {strat_path}")
            continue
        (attach_dir / "whites_rc.json").write_text(
            json.dumps(result, indent=2, default=str)
        )
        print(f"  ✅ {Path(strat_path).stem} → {attach_dir.name}")

    print(f"\n✅ Saved to {run_dir}/")


if __name__ == "__main__":
    main()