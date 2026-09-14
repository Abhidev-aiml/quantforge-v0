"""
Bollinger + RSI Double Strategy Parameter Sweep

Tests the Bollinger + RSI double strategy across multiple parameter
combinations on 1D, 4H, and 1H data. Ranks top 10 candidates by OOS
excess Sharpe (walk-forward).

Usage:
    python -m execute.bollinger_rsi_sweep
    python -m execute.bollinger_rsi_sweep --quick        # fewer combos
    python -m execute.bollinger_rsi_sweep --tf 1D,4H     # subset of TFs

Outputs:
    results/bollinger_rsi_sweep_results.json
    results/bollinger_rsi_sweep_results.csv
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from engine.data import load_csv, cache
from engine.loader import load_strategy
from validation.walk_forward import walk_forward


STRATEGY_PATH = "strategies/25_bollinger_rsi_double.py"


# ---------------------------------------------------------------------------
# Walk-forward window sizes per timeframe
# ---------------------------------------------------------------------------
WF_WINDOWS = {
    "1D": {"train_bars": 756, "test_bars": 252, "step_bars": 126,  "warmup_bars": 252},
    "4H": {"train_bars": 4500, "test_bars": 1500, "step_bars": 750, "warmup_bars": 500},
    "1H": {"train_bars": 18000, "test_bars": 6000, "step_bars": 3000, "warmup_bars": 500},
}

# ---------------------------------------------------------------------------
# Datasets to test. Curated from prior backtests (equity indices + gold +
# a couple of FX for comparison). Extend as needed.
# ---------------------------------------------------------------------------
DATASETS = {
    "1D": [
        "data/raw/daily/USA30IDXUSD1440_comma.csv",
        "data/raw/daily/USA500IDXUSD1440_comma.csv",
        "data/raw/daily/USATECHIDXUSD1440_comma.csv",
        "data/raw/daily/GBRIDXGBP1440_comma.csv",
        "data/raw/daily/DEUIDXEUR1440_comma.csv",
        "data/raw/daily/xauusd_1D_comma.csv",
        "data/raw/daily/GBPUSD1440_comma.csv",
    ],
    "4H": [
        "data/raw/fourhours/USA30IDXUSD240_comma.csv",
        "data/raw/fourhours/USA500IDXUSD240_comma.csv",
        "data/raw/fourhours/USATECHIDXUSD240_comma.csv",
        "data/raw/fourhours/GBRIDXGBP240_comma.csv",
        "data/raw/fourhours/DEUIDXEUR240_comma.csv",
        "data/raw/fourhours/GBPUSD240_comma.csv",
    ],
    "1H": [
        "data/raw/onehours/USA30IDXUSD60_comma.csv",
        "data/raw/onehours/USA500IDXUSD60_comma.csv",
        "data/raw/onehours/USATECHIDXUSD60_comma.csv",
        "data/raw/onehours/GBRIDXGBP60_comma.csv",
        "data/raw/onehours/DEUIDXEUR60_comma.csv",
        "data/raw/onehours/GBPUSD60_comma.csv",
    ],
}


# ---------------------------------------------------------------------------
# Parameter grids
# ---------------------------------------------------------------------------
def parameter_grid(quick: bool = False) -> list[dict]:
    """Return list of parameter dicts to test."""
    if quick:
        rsi_lengths = [6, 14]
        bb_lengths = [50, 200]
        bb_mults = [2.0]
    else:
        rsi_lengths = [6, 14]
        bb_lengths = [20, 50, 100, 200]
        bb_mults = [1.5, 2.0, 2.5]

    grid = []
    for rsi_len in rsi_lengths:
        for bb_len in bb_lengths:
            for bb_mult in bb_mults:
                grid.append({
                    "rsi_length": rsi_len,
                    "rsi_oversold": 50,
                    "rsi_overbought": 50,
                    "bb_length": bb_len,
                    "bb_mult": bb_mult,
                })
    return grid


# ---------------------------------------------------------------------------
# Single walk-forward run
# ---------------------------------------------------------------------------
def run_single_sweep(data_path: str, timeframe: str, params: dict) -> dict:
    """Run one walk-forward for a parameter set."""
    try:
        df = load_csv(data_path)
        cache(df, data_path)
        fn = load_strategy(STRATEGY_PATH)

        wf = WF_WINDOWS[timeframe]

        engine_params = {
            "initial_cash": 100000.0,
            "commission_bps": 1.0,
            "slippage_bps": 5.0,
            "no_trade_band": 0.01,
            "warmup_bars": 0,
        }

        windows, agg = walk_forward(
            df, fn,
            strategy_params=params,
            train_bars=wf["train_bars"],
            test_bars=wf["test_bars"],
            step_bars=wf["step_bars"],
            warmup_bars=wf["warmup_bars"],
            compute_benchmark=True,
            min_trades_high_confidence=5,
            engine_params=engine_params,
        )

        return {
            "status": "success",
            "data_path": data_path,
            "timeframe": timeframe,
            "rsi_length": params["rsi_length"],
            "bb_length": params["bb_length"],
            "bb_mult": params["bb_mult"],
            "n_windows": agg.get("n_windows", 0),
            "mean_IS_sharpe": round(agg.get("mean_IS_sharpe", 0.0), 3),
            "mean_OOS_sharpe": round(agg.get("mean_OOS_sharpe", 0.0), 3),
            "degradation_ratio": round(agg.get("degradation_ratio", 0.0), 3),
            "robust": bool(agg.get("robust", False)),
            "chained_OOS_sharpe": round(agg.get("chained_OOS_sharpe", 0.0), 3),
            "chained_OOS_benchmark_sharpe": round(
                agg.get("chained_OOS_benchmark_sharpe", 0.0), 3
            ),
            "chained_OOS_excess_sharpe": round(
                agg.get("chained_OOS_excess_sharpe", 0.0), 3
            ),
            "chained_OOS_CAGR": round(agg.get("chained_OOS_CAGR", 0.0) * 100, 2),
            "chained_OOS_maxdd": round(agg.get("chained_OOS_maxdd", 0.0) * 100, 2),
            "n_low_confidence": agg.get("n_low_confidence_windows", 0),
            "has_edge": bool(agg.get("has_edge", False)),
        }
    except Exception as e:
        return {
            "status": "error",
            "data_path": data_path,
            "timeframe": timeframe,
            "rsi_length": params.get("rsi_length"),
            "bb_length": params.get("bb_length"),
            "bb_mult": params.get("bb_mult"),
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true",
                        help="Fewer parameter combos (faster)")
    parser.add_argument("--tf", type=str, default="1D,4H,1H",
                        help="Comma-separated timeframes: e.g. 1D,4H")
    args = parser.parse_args()

    selected_tfs = [t.strip() for t in args.tf.split(",") if t.strip()]
    for tf in selected_tfs:
        if tf not in WF_WINDOWS:
            raise ValueError(f"Unknown timeframe: {tf}")

    print("=" * 80)
    print("BOLLINGER + RSI DOUBLE STRATEGY SWEEP")
    print("=" * 80)
    print(f"Started:    {datetime.now().isoformat()}")
    print(f"Timeframes: {selected_tfs}")
    print(f"Quick mode: {args.quick}")

    grid = parameter_grid(quick=args.quick)
    print(f"Param combos: {len(grid)}")

    # Build (tf, data_path, params) work items
    work_items = []
    for tf in selected_tfs:
        for data_path in DATASETS.get(tf, []):
            if not Path(data_path).exists():
                print(f"  ✗ Missing: {data_path}")
                continue
            print(f"  ✓ Found:   {data_path}")
            for params in grid:
                work_items.append((tf, data_path, params))

    if not work_items:
        print("\n❌ No data files found!")
        return

    print(f"\nTotal walk-forward runs: {len(work_items)}")
    print("-" * 80)

    results = []
    for idx, (tf, data_path, params) in enumerate(work_items, 1):
        name = Path(data_path).stem
        pstr = (f"rsi={params['rsi_length']} "
                f"bb={params['bb_length']} "
                f"mult={params['bb_mult']}")
        print(f"\n[{idx}/{len(work_items)}] {tf} | {name} | {pstr}")

        result = run_single_sweep(data_path, tf, params)
        results.append(result)

        if result["status"] == "success":
            print(
                f"  OOS: {result['mean_OOS_sharpe']:+.3f} | "
                f"ChainOOS: {result['chained_OOS_sharpe']:+.3f} | "
                f"Excess: {result['chained_OOS_excess_sharpe']:+.3f} | "
                f"Deg: {result['degradation_ratio']:.3f} | "
                f"Robust: {'✓' if result['robust'] else '✗'} | "
                f"LC: {result['n_low_confidence']}/{result['n_windows']}"
            )
        else:
            print(f"  ERROR: {result['error']}")

    # -----------------------------------------------------------------
    # Rank & report
    # -----------------------------------------------------------------
    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "error"]

    print("\n" + "=" * 80)
    print(f"SWEEP COMPLETE: {len(successful)} succeeded, {len(failed)} failed")
    print("=" * 80)

    successful.sort(
        key=lambda x: x["chained_OOS_excess_sharpe"], reverse=True
    )

    # Top 10
    print("\n" + "=" * 80)
    print("TOP 10 CANDIDATES (by Chained OOS Excess Sharpe)")
    print("=" * 80)
    header = (
        f"{'#':>3} | {'TF':>3} | {'Asset':<18} | "
        f"{'rsi':>3} | {'bb':>4} | {'mult':>4} | "
        f"{'Excess':>7} | {'ChainOOS':>8} | {'Bench':>7} | "
        f"{'Deg':>5} | {'Robust':>6} | {'LC':>7}"
    )
    print(header)
    print("-" * len(header))

    for i, r in enumerate(successful[:10], 1):
        asset = Path(r["data_path"]).stem.replace("_comma", "")
        if len(asset) > 18:
            asset = asset[:17] + "…"
        print(
            f"{i:>3} | {r['timeframe']:>3} | {asset:<18} | "
            f"{r['rsi_length']:>3} | {r['bb_length']:>4} | {r['bb_mult']:>4.1f} | "
            f"{r['chained_OOS_excess_sharpe']:>+7.3f} | "
            f"{r['chained_OOS_sharpe']:>+8.3f} | "
            f"{r['chained_OOS_benchmark_sharpe']:>+7.3f} | "
            f"{r['degradation_ratio']:>5.3f} | "
            f"{'YES' if r['robust'] else 'NO':>6} | "
            f"{r['n_low_confidence']:>3}/{r['n_windows']:<3}"
        )

    # Positive absolute performance
    positive_oos = [r for r in successful if r["chained_OOS_sharpe"] > 0]
    print(f"\nConfigs with POSITIVE chained OOS Sharpe: {len(positive_oos)}")
    for r in positive_oos[:10]:
        asset = Path(r["data_path"]).stem.replace("_comma", "")
        print(
            f"  {r['timeframe']:>3} | {asset:<22} | "
            f"rsi={r['rsi_length']} bb={r['bb_length']} mult={r['bb_mult']} | "
            f"ChainOOS={r['chained_OOS_sharpe']:+.3f} | "
            f"Excess={r['chained_OOS_excess_sharpe']:+.3f} | "
            f"Robust={'YES' if r['robust'] else 'NO'}"
        )

    robust = [r for r in successful if r["robust"]]
    print(f"\nRobust configurations: {len(robust)}")
    for r in robust[:10]:
        asset = Path(r["data_path"]).stem.replace("_comma", "")
        print(
            f"  {r['timeframe']:>3} | {asset:<22} | "
            f"rsi={r['rsi_length']} bb={r['bb_length']} mult={r['bb_mult']} | "
            f"ChainOOS={r['chained_OOS_sharpe']:+.3f} | "
            f"Excess={r['chained_OOS_excess_sharpe']:+.3f}"
        )

    # Save
    output = {
        "sweep_date": datetime.now().isoformat(),
        "strategy": STRATEGY_PATH,
        "timeframes": selected_tfs,
        "quick_mode": args.quick,
        "n_combos": len(grid),
        "n_runs": len(results),
        "top_10": successful[:10],
        "all_results": successful,
        "failed": failed,
    }

    out_json = Path("results/bollinger_rsi_sweep_results.json")
    out_json.parent.mkdir(exist_ok=True)
    out_json.write_text(json.dumps(output, indent=2, default=str))
    print(f"\n✅ JSON saved to {out_json}")

    df_out = pd.DataFrame(successful)
    if not df_out.empty:
        out_csv = Path("results/bollinger_rsi_sweep_results.csv")
        df_out.to_csv(out_csv, index=False)
        print(f"✅ CSV saved to {out_csv}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    if successful:
        best = successful[0]
        asset = Path(best["data_path"]).stem.replace("_comma", "")
        print(f"Best: {best['timeframe']} | {asset} | "
              f"rsi={best['rsi_length']} bb={best['bb_length']} "
              f"mult={best['bb_mult']}")
        print(f"  Chained OOS Sharpe:    {best['chained_OOS_sharpe']:+.3f}")
        print(f"  Chained Benchmark:     {best['chained_OOS_benchmark_sharpe']:+.3f}")
        print(f"  Chained Excess Sharpe: {best['chained_OOS_excess_sharpe']:+.3f}")
        print(f"  Robust:                {'YES' if best['robust'] else 'NO'}")


if __name__ == "__main__":
    main()