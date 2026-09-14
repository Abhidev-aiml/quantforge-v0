"""
Run Monte Carlo on an existing run's equity curve.

Writes monte_carlo.json into the same run directory so reporting.build
can pick it up.

Usage:
    python -m execute.run_mc_on_run results/runs/20260913_202522_1acdef
    python -m execute.run_mc_on_run --latest
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from validation.monte_carlo import (
    bootstrap_returns_under_null,
    bootstrap_returns_iid,
    bootstrap_returns_block,
    simulate_equity_paths,
)


# ---------------------------------------------------------------- helpers

def _latest_run(results_dir: str | Path = "results/runs") -> Path:
    runs = [p for p in Path(results_dir).glob("*") if p.is_dir()]
    if not runs:
        raise SystemExit(f"No runs found in {results_dir}")
    return max(runs, key=lambda p: p.stat().st_mtime)


def _load_equity(run_dir: Path) -> pd.Series:
    path = run_dir / "equity.csv"
    if not path.exists():
        raise SystemExit(f"Missing equity.csv in {run_dir}")
    df = pd.read_csv(path)
    ts_col = next((c for c in ("timestamp", "date", "index") if c in df.columns), None)
    if ts_col is None:
        raise SystemExit(f"No timestamp column in {path}")
    df[ts_col] = pd.to_datetime(df[ts_col])
    df = df.set_index(ts_col)
    num_cols = df.select_dtypes(include=[np.number]).columns
    if not len(num_cols):
        raise SystemExit(f"No numeric column in {path}")
    return df[num_cols[0]].astype(float).sort_index()


# ---------------------------------------------------------------- main

def run_mc(
    run_dir: Path,
    n_sims: int = 5000,
    n_perm: int = 500,
    seed: int = 42,
    block_sizes: tuple[int, ...] = (2, 5, 20, 40, 80, 160),
) -> dict:
    equity = _load_equity(run_dir)

    print("=" * 78)
    print("MONTE CARLO ON EXISTING RUN")
    print("=" * 78)
    print(f"  Run:    {run_dir}")
    print(f"  Equity: {len(equity)} bars "
          f"({equity.index[0].date()} → {equity.index[-1].date()})")
    print(f"  Sims:   {n_sims}")
    print(f"  Seed:   {seed}")
    print("=" * 78)

    report: dict = {}

    print("\n[1] Null bootstrap (H0: mean return = 0)")
    report["null_bootstrap"] = bootstrap_returns_under_null(
        equity, n_sims=n_sims, block_size=21, seed=seed,
    )
    nb = report["null_bootstrap"]
    print(f"    observed Sharpe:       {nb['observed_sharpe']:+.3f}")
    print(f"    null Sharpe mean:      {nb['null_sharpe_mean']:+.3f}")
    print(f"    null Sharpe std:       {nb['null_sharpe_std']:.3f}")
    print(f"    null 5–95 pct:         [{nb['null_sharpe_p05']:+.3f}, {nb['null_sharpe_p95']:+.3f}]")
    print(f"    p-value (one-sided):   {nb['p_value_one_sided']:.4f}")

    print("\n[2] IID bootstrap (informational CI)")
    report["iid_ci"] = bootstrap_returns_iid(
        equity, n_sims=n_sims, seed=seed,
    )
    ic = report["iid_ci"]
    print(f"    90% CI on Sharpe:      [{ic['sharpe_p05']:+.3f}, {ic['sharpe_p95']:+.3f}]")
    print(f"    prob of ruin (DD>50%): {ic['prob_ruin']:.2%}")

    print("\n[3] Block bootstrap (preserves autocorrelation)")
    report["block_ci"] = bootstrap_returns_block(
        equity, n_sims=n_sims, block_size=20, seed=seed,
    )
    bc = report["block_ci"]
    print(f"    90% CI on Sharpe:      [{bc['sharpe_p05']:+.3f}, {bc['sharpe_p95']:+.3f}]")

    print("\n[4] Equity path simulation (fan chart)")
    paths = simulate_equity_paths(
        equity,
        n_sims=min(n_sims, 5000),
        block_size=20,
        n_paths_saved=200,
        max_bars=400,
        seed=seed,
    )
    report["paths"] = paths
    print(f"    sims:                  {paths['n_sims']}")
    print(f"    paths saved:           {paths['n_paths_saved']}")
    print(f"    bars per path:         {paths['n_bars']}")
    print(f"    terminal wealth p05:   {np.percentile(paths['terminal_wealth'], 5):.3f}")
    print(f"    terminal wealth p50:   {np.percentile(paths['terminal_wealth'], 50):.3f}")
    print(f"    terminal wealth p95:   {np.percentile(paths['terminal_wealth'], 95):.3f}")
    print(f"    max DD p05:            {np.percentile(paths['max_drawdown'], 5):.2%}")
    print(f"    max DD p50:            {np.percentile(paths['max_drawdown'], 50):.2%}")

    out_path = run_dir / "monte_carlo.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n✅ Saved → {out_path}")

    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run_dir", nargs="?", help="path to a run directory")
    p.add_argument("--latest", action="store_true",
                   help="use the most recent run in results/runs/")
    p.add_argument("--n-sims", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    if args.latest:
        run_dir = _latest_run()
        print(f"Using latest run: {run_dir}")
    elif args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        raise SystemExit("Provide a run_dir or use --latest")

    if not run_dir.exists():
        raise SystemExit(f"Run dir does not exist: {run_dir}")

    run_mc(run_dir, n_sims=args.n_sims, seed=args.seed)


if __name__ == "__main__":
    main()