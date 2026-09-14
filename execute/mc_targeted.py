"""
execute/mc_targeted.py

Focused Monte Carlo on selected (strategy, asset) pairs.
Run only on the combos that survived the cross-asset screen.
"""
from __future__ import annotations
import json
from pathlib import Path

from engine.data import load_csv
from engine.core import BacktestEngine
from engine.loader import load_strategy, validate_signals
from analytics.metrics import compute_metrics, extract_trades
from validation.monte_carlo import (
    bootstrap_returns_under_null,
    bootstrap_returns_iid,
    bootstrap_trades,
    signal_block_shuffle,
)


# ---------------------------------------------------------------- config

# Format: (asset_csv, strategy_py, block_sizes_list)
# block_sizes should bracket the average holding period of each strategy.
#
# Rule of thumb for block sizes:
#   - mean-reversion:   [2, 3, 5, 8, 13, 21]
#   - medium trend:     [5, 13, 21, 40, 80]
#   - slow trend:       [21, 40, 80, 160, 250]

TARGETS = [
    # ---- EDIT THIS LIST after the screen ----
    # Example entries; replace with your actual survivors:
    ("data/raw/xagusd_1d.csv", "strategies/07_absolute_momentum.py",
     [5, 13, 21, 40, 80]),
    ("data/raw/xagusd_1d.csv", "strategies/01_goldencross.py",
     [21, 40, 80, 160, 250]),
    ("data/raw/eurusd_1d.csv", "strategies/07_absolute_momentum.py",
     [5, 13, 21, 40, 80]),
    ("data/raw/eurusd_1d.csv", "strategies/01_goldencross.py",
     [21, 40, 80, 160, 250]),
    # ... add the pairs that survived the screen
]

N_SIMS_SWEEP = 300
N_SIMS_NULL  = 5000
N_SIMS_CI    = 5000
SEED = 42


# ---------------------------------------------------------------- helpers

def run_strategy(df, path, commission_bps=1.0, slippage_bps=5.0):
    fn = load_strategy(path)
    sig = validate_signals(fn(df), df)
    eng = BacktestEngine(initial_cash=100_000,
                         commission_bps=commission_bps,
                         slippage_bps=slippage_bps)
    eq = eng.run(df, sig)
    trades = extract_trades(eng.pf.fills)
    return fn, sig, eq, trades


def same_exposure_benchmark(df, sig):
    w = float(sig.mean())
    w = max(-1.0, min(1.0, w))
    rets = df["close"].pct_change().fillna(0.0)
    bench_eq = 100_000 * (1 + w * rets).cumprod()
    return bench_eq, w


def report_one(asset_csv, strategy_path, block_sizes):
    asset = Path(asset_csv).stem
    strat = Path(strategy_path).stem
    print("\n" + "=" * 78)
    print(f"{asset}  ×  {strat}")
    print("=" * 78)

    df = load_csv(asset_csv)
    fn, sig, eq, trades = run_strategy(df, strategy_path)
    n_trades = len(trades) if trades is not None else 0
    obs = compute_metrics(eq)["sharpe"]

    # --- Same-exposure benchmark ---
    bench_eq, w = same_exposure_benchmark(df, sig)
    bench_s = compute_metrics(bench_eq)["sharpe"]
    excess  = obs - bench_s

    print(f"\n[0] Same-exposure benchmark")
    print(f"    avg weight:      {w:+.3f}")
    print(f"    strategy Sharpe: {obs:+.3f}")
    print(f"    benchmark:       {bench_s:+.3f}")
    print(f"    excess Sharpe:   {excess:+.3f}   "
          f"{'ALPHA' if excess > 0.20 else 'modest' if excess > 0 else 'BETA'}")
    print(f"    trades:          {n_trades}")

    # --- Null bootstrap ---
    null = bootstrap_returns_under_null(eq, n_sims=N_SIMS_NULL,
                                        block_size=21, seed=SEED)
    print(f"\n[1] Null bootstrap  p={null['p_value_one_sided']:.4f}")

    # --- Block sweep ---
    print(f"\n[2] Timing-skill block sweep")
    print(f"    {'block':>6}  {'null_mean':>10}  {'p':>7}  verdict")
    sweep = []
    for bs in block_sizes:
        r = signal_block_shuffle(df, fn, block_size=bs,
                                 n_sims=N_SIMS_SWEEP, seed=SEED)
        sweep.append({"block": bs, **r})
        v = ("strong" if r["p_value"] < 0.01
             else "sig" if r["p_value"] < 0.05
             else "marginal" if r["p_value"] < 0.10
             else "no")
        print(f"    {bs:>6}  {r['null_sharpe_mean']:>10.3f}  "
              f"{r['p_value']:>7.3f}  {v}")

    best = min(sweep, key=lambda x: x["p_value"])
    print(f"    best: block={best['block']}  p={best['p_value']:.3f}")

    # --- CIs ---
    iid = bootstrap_returns_iid(eq, n_sims=N_SIMS_CI, seed=SEED)
    print(f"\n[3] IID Sharpe 90% CI: "
          f"[{iid['sharpe_p05']:.3f}, {iid['sharpe_p95']:.3f}]")

    payload = {
        "asset": asset, "strategy": strategy_path,
        "observed_sharpe": obs, "benchmark_sharpe": bench_s,
        "excess_sharpe": excess, "avg_weight": w, "n_trades": n_trades,
        "null_bootstrap": null, "block_sweep": sweep, "iid_ci": iid,
    }
    if n_trades >= 20:
        tb = bootstrap_trades(trades, n_sims=N_SIMS_CI, seed=SEED)
        payload["trade_ci"] = tb
        print(f"    trade Sharpe 90% CI: "
              f"[{tb['sharpe_p05']:.3f}, {tb['sharpe_p95']:.3f}]")

    out = Path("results") / "mc_targeted"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{asset}__{strat}.json").write_text(
        json.dumps(payload, indent=2, default=str)
    )
    return payload


# ---------------------------------------------------------------- main

def main():
    print("TARGETED MONTE CARLO")
    print(f"Running {len(TARGETS)} (asset, strategy) pairs")
    results = []
    for asset_csv, strat, blocks in TARGETS:
        try:
            results.append(report_one(asset_csv, strat, blocks))
        except Exception as e:
            print(f"❌ {asset_csv} × {strat}: {e}")

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"{'asset':>12}  {'strategy':>28}  "
          f"{'excess':>8}  {'best_block':>10}  {'best_p':>8}")
    print("-" * 78)
    for r in results:
        best = min(r["block_sweep"], key=lambda x: x["p_value"])
        print(f"{r['asset']:>12}  {Path(r['strategy']).stem:>28}  "
              f"{r['excess_sharpe']:>+8.3f}  "
              f"{best['block']:>10}  {best['p_value']:>8.3f}")


if __name__ == "__main__":
    main()