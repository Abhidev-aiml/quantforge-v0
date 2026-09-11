"""
execute/execute_montecarlo.py

Monte Carlo diagnostics v2.

Key addition: [0] Same-Exposure Benchmark.
    Compares the strategy against a passive position with the SAME average
    exposure. This is the only honest test for "alpha vs beta."

Also fixed: block=1 was removed from the significance sweep because it
    measures turnover differences, not timing skill.
"""

from __future__ import annotations
import json
from pathlib import Path

import numpy as np
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

DATA_PATH = "data/raw/xauusd_1D_comma.csv"

STRATEGIES = [
    ("strategies/07_absolute_momentum.py", "Absolute Momentum (long/short, 12m)"),
    ("strategies/01_goldencross.py",       "Golden Cross (50/200 SMA, long-only)"),
    ("strategies/03_rsi_meanrev.py",       "RSI(2) Mean Reversion + 200 SMA filter"),
]

# Finer-grained sweep starting at 2 (block=1 is a turnover test, not a
# significance test — see docstring).
BLOCK_SIZES = [2, 3, 5, 8, 13, 21, 40, 80, 160]

N_SIMS_SWEEP = 300
N_SIMS_NULL  = 5000
N_SIMS_CI    = 5000
N_SIMS_TRADE = 5000

SEED = 42


# -------------------------------------------------------------- helpers

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
    """Static position at the signal's average weight."""
    avg_weight = float(sig.mean())
    avg_weight = max(-1.0, min(1.0, avg_weight))
    rets = df["close"].pct_change().fillna(0.0)
    bench_rets = avg_weight * rets
    bench_eq = 100_000 * (1 + bench_rets).cumprod()
    return bench_eq, avg_weight


def analyze_excess(eq, bench_eq):
    s = compute_metrics(eq)
    b = compute_metrics(bench_eq)
    return {
        "strategy_sharpe":  s["sharpe"],
        "benchmark_sharpe": b["sharpe"],
        "excess_sharpe":    s["sharpe"] - b["sharpe"],
        "strategy_CAGR":    s["CAGR"],
        "benchmark_CAGR":   b["CAGR"],
        "excess_CAGR":      s["CAGR"] - b["CAGR"],
        "strategy_maxdd":   s["max_drawdown"],
        "benchmark_maxdd":  b["max_drawdown"],
    }


# -------------------------------------------------------------- main

def main():
    print("=" * 78)
    print("QUANTFORGE — MONTE CARLO DIAGNOSTICS (v2)")
    print("=" * 78)

    df = load_csv(DATA_PATH)
    print(f"\nData: {DATA_PATH}")
    print(f"      {len(df)} bars  "
          f"({df.index[0].date()} → {df.index[-1].date()})")

    for path, description in STRATEGIES:
        print("\n" + "=" * 78)
        print(f"STRATEGY: {description}")
        print(f"FILE:     {path}")
        print("=" * 78)

        try:
            fn, sig, eq, trades = run_strategy(df, path)
        except Exception as e:
            print(f"❌ Failed: {e}")
            continue

        observed_sharpe = compute_metrics(eq)["sharpe"]
        n_trades = len(trades) if trades is not None else 0

        print(f"\nObserved Sharpe (rf=0): {observed_sharpe:.3f}")
        print(f"Round-trip trades:       {n_trades}")

        # ---------- [0] Same-exposure benchmark ----------
        print(f"\n[0] Same-Exposure Benchmark (beta-only)")
        print(f"    Compares strategy vs a static position of equal average weight.")
        print(f"    This is the fairest alpha-vs-beta test.")
        bench_eq, avg_w = same_exposure_benchmark(df, sig)
        ex = analyze_excess(eq, bench_eq)
        print(f"    Average exposure:        {avg_w:+.3f}")
        print(f"    Strategy  Sharpe/CAGR:   "
              f"{ex['strategy_sharpe']:+.3f}  /  {ex['strategy_CAGR']*100:+.2f}%")
        print(f"    Benchmark Sharpe/CAGR:   "
              f"{ex['benchmark_sharpe']:+.3f}  /  {ex['benchmark_CAGR']*100:+.2f}%")
        print(f"    EXCESS Sharpe/CAGR:      "
              f"{ex['excess_sharpe']:+.3f}  /  {ex['excess_CAGR']*100:+.2f}%")
        print(f"    Strategy  MaxDD:         {ex['strategy_maxdd']*100:+.2f}%")
        print(f"    Benchmark MaxDD:         {ex['benchmark_maxdd']*100:+.2f}%")
        if ex["excess_sharpe"] > 0.30:
            print("    → Substantial alpha over beta.")
        elif ex["excess_sharpe"] > 0.10:
            print("    → Modest alpha over beta.")
        elif ex["excess_sharpe"] > 0:
            print("    → Marginal alpha over beta.")
        else:
            print("    → No alpha; returns are consistent with beta capture.")

        # ---------- [1] Null bootstrap ----------
        print(f"\n[1] Null Bootstrap (H0: mean return = 0)")
        print(f"    NOTE: passes trivially for any long-biased strategy on a")
        print(f"    trending asset. Confirms 'made money,' not 'has skill.'")
        null = bootstrap_returns_under_null(
            eq, n_sims=N_SIMS_NULL, block_size=21, seed=SEED
        )
        print(f"    observed Sharpe:        {null['observed_sharpe']:.3f}")
        print(f"    null Sharpe mean:       {null['null_sharpe_mean']:.3f}")
        print(f"    null Sharpe std:        {null['null_sharpe_std']:.3f}")
        print(f"    null 5th–95th pct:      "
              f"[{null['null_sharpe_p05']:.3f}, {null['null_sharpe_p95']:.3f}]")
        print(f"    p-value (one-sided):    {null['p_value_one_sided']:.4f}")

        # ---------- [2] Signal block shuffle sweep ----------
        print(f"\n[2] Signal Block Shuffle Sweep (timing-skill test)")
        print(f"    Small p at some B → real timing skill at that horizon.")
        print(f"    Flat high p at all B → returns are beta capture.\n")
        print(f"    {'block':>6}  {'obs':>8}  {'null_mean':>10}  "
              f"{'null_p05':>9}  {'null_p95':>9}  {'p':>7}  verdict")
        print(f"    {'-'*6}  {'-'*8}  {'-'*10}  {'-'*9}  {'-'*9}  {'-'*7}  {'-'*10}")

        sweep_results = []
        for bs in BLOCK_SIZES:
            r = signal_block_shuffle(
                df, fn, block_size=bs, n_sims=N_SIMS_SWEEP, seed=SEED
            )
            sweep_results.append({"block": bs, **r})
            verdict = ("strong" if r["p_value"] < 0.01
                       else "sig" if r["p_value"] < 0.05
                       else "marginal" if r["p_value"] < 0.10
                       else "no")
            print(f"    {bs:>6}  {r['observed_sharpe']:>8.3f}  "
                  f"{r['null_sharpe_mean']:>10.3f}  "
                  f"{r['null_sharpe_p05']:>9.3f}  "
                  f"{r['null_sharpe_p95']:>9.3f}  "
                  f"{r['p_value']:>7.3f}  {verdict}")

        best = min(sweep_results, key=lambda x: x["p_value"])
        print(f"\n    Best block size: {best['block']} (p = {best['p_value']:.3f})")
        if best["p_value"] < 0.05:
            print(f"    → Timing skill at ~{best['block']}-bar horizon.")
        elif best["p_value"] < 0.10:
            print(f"    → Marginal timing skill at ~{best['block']}-bar horizon.")
        else:
            print(f"    → No timing skill at any horizon tested.")

        # ---------- [3] CIs ----------
        print(f"\n[3] Informational Confidence Intervals")
        iid = bootstrap_returns_iid(eq, n_sims=N_SIMS_CI, seed=SEED)
        print(f"    IID 90% CI on Sharpe:   "
              f"[{iid['sharpe_p05']:.3f}, {iid['sharpe_p95']:.3f}]")
        print(f"    Prob of ruin:           {iid['prob_ruin']:.2%}")

        tb = None
        if n_trades >= 20:
            tb = bootstrap_trades(trades, n_sims=N_SIMS_TRADE, seed=SEED)
            print(f"    Trade 90% CI on Sharpe: "
                  f"[{tb['sharpe_p05']:.3f}, {tb['sharpe_p95']:.3f}]")
            print(f"    Trade CAGR 5th–95th:    "
                  f"[{tb['cagr_p05']*100:+.2f}%, {tb['cagr_p95']*100:+.2f}%]")
        else:
            print(f"    Trade bootstrap: SKIPPED "
                  f"(only {n_trades} trades; need ≥ 20)")

        # ---------- Save ----------
        out_dir = Path("results") / "monte_carlo"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{Path(path).stem}.json"
        payload = {
            "strategy": path,
            "description": description,
            "observed_sharpe": observed_sharpe,
            "n_trades": n_trades,
            "same_exposure": {"avg_weight": avg_w, **ex},
            "null_bootstrap": null,
            "signal_shuffle_sweep": sweep_results,
            "iid_ci": iid,
        }
        if tb is not None:
            payload["trade_ci"] = tb
        out_file.write_text(json.dumps(payload, indent=2, default=str))
        print(f"\n    → Saved: {out_file}")

    print("\n" + "=" * 78)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 78)
    print("\nReading guide:")
    print("  [0] Excess Sharpe > 0.30 vs benchmark → real alpha")
    print("  [2] Small p at some block B          → timing skill at that horizon")
    print("  [2] Flat high p across all B         → beta capture, no timing")
    print("  [3] Trade CI straddling zero         → sample too thin for inference")


if __name__ == "__main__":
    main()