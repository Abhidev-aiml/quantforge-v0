"""
execute/screen_all_assets.py

Cheap cross-asset screen.
Runs all strategies on all datasets in data/raw/ and prints a comparison table.

No Monte Carlo here — that comes later, only for survivors.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

from engine.data import load_csv
from engine.core import BacktestEngine
from engine.loader import load_strategy, validate_signals
from analytics.metrics import compute_metrics, extract_trades


# ---------------------------------------------------------------- config

DATA_DIR = Path("data/raw/daily_mc")

# Every CSV in data/raw/ will be tested.
# Name your files descriptively: xauusd_1d.csv, xagusd_1d.csv, eurusd_1d.csv...

STRATEGIES = [
    "strategies/01_goldencross.py",
    "strategies/02_emacross.py",
    "strategies/03_rsi_meanrev.py",
    "strategies/04_bollinger_meanrev.py",
    "strategies/05_donchian_breakout.py",
    "strategies/06_macd_cross.py",
    "strategies/07_absolute_momentum.py",
    "strategies/08_atr_breakout.py",
    "strategies/09_zscore_meanrev.py",
    "strategies/10_roc_momentum.py",
]

COMMISSION_BPS = 1.0
SLIPPAGE_BPS   = 5.0
RF_ANNUAL      = 0.0     # set to 0 for cross-asset comparison fairness

OUT_CSV = "results/screen_all_assets.csv"


# ---------------------------------------------------------------- helpers

def same_exposure_sharpe(df, sig):
    """Sharpe of a static position at the signal's average weight."""
    w = float(sig.mean())
    w = max(-1.0, min(1.0, w))
    rets = df["close"].pct_change().fillna(0.0)
    bench_rets = w * rets
    bench_eq = 100_000 * (1 + bench_rets).cumprod()
    return compute_metrics(bench_eq)["sharpe"]


def run_one(df, path):
    try:
        fn = load_strategy(path)
        sig = validate_signals(fn(df), df)
        eng = BacktestEngine(initial_cash=100_000,
                             commission_bps=COMMISSION_BPS,
                             slippage_bps=SLIPPAGE_BPS)
        eq = eng.run(df, sig)
        trades = extract_trades(eng.pf.fills)
        m = compute_metrics(eq, rf_annual=RF_ANNUAL, trades=trades)

        bench_sharpe = same_exposure_sharpe(df, sig)

        return {
            "sharpe":           m["sharpe"],
            "excess_sharpe":    m["sharpe"] - bench_sharpe,
            "bench_sharpe":     bench_sharpe,
            "CAGR":             m["CAGR"],
            "max_drawdown":     m["max_drawdown"],
            "calmar":           m["calmar"],
            "avg_exposure":     float(sig.mean()),
            "num_trades":       m.get("num_trades", 0),
            "win_rate":         m.get("win_rate", float("nan")),
            "profit_factor":    m.get("profit_factor", float("nan")),
        }
    except Exception as e:
        print(f"  ❌ {Path(path).stem}: {e}")
        return None


# ---------------------------------------------------------------- main

def main():
    csv_files = sorted(DATA_DIR.glob("*.csv"))
    if not csv_files:
        print(f"No CSVs found in {DATA_DIR}")
        return

    print("=" * 78)
    print("CROSS-ASSET SCREEN")
    print("=" * 78)
    print(f"\nAssets:     {len(csv_files)} files")
    print(f"Strategies: {len(STRATEGIES)}")
    print(f"Total runs: {len(csv_files) * len(STRATEGIES)}\n")

    all_rows = []
    for csv_path in csv_files:
        asset = csv_path.stem
        print(f"\n[{asset}]")
        try:
            df = load_csv(csv_path)
        except Exception as e:
            print(f"  ❌ Could not load: {e}")
            continue
        print(f"  {len(df)} bars ({df.index[0].date()} → {df.index[-1].date()})")

        for s in STRATEGIES:
            r = run_one(df, s)
            if r is None:
                continue
            r["asset"]    = asset
            r["strategy"] = Path(s).stem
            all_rows.append(r)

    df_out = pd.DataFrame(all_rows)

    # ---- Console table: excess Sharpe by asset x strategy
    print("\n" + "=" * 78)
    print("EXCESS SHARPE vs SAME-EXPOSURE BENCHMARK")
    print("  positive = strategy beat a static position of equal weight")
    print("=" * 78)
    pivot = df_out.pivot(index="strategy", columns="asset",
                         values="excess_sharpe").round(3)
    print(pivot.to_string())

    print("\n" + "=" * 78)
    print("RAW SHARPE")
    print("=" * 78)
    pivot_raw = df_out.pivot(index="strategy", columns="asset",
                             values="sharpe").round(3)
    print(pivot_raw.to_string())

    print("\n" + "=" * 78)
    print("AVERAGE EXCESS SHARPE ACROSS ASSETS")
    print("=" * 78)
    avg = (df_out.groupby("strategy")["excess_sharpe"]
                 .agg(["mean", "std", "min", "max", "count"])
                 .round(3)
                 .sort_values("mean", ascending=False))
    print(avg.to_string())

    # ---- Save
    Path(OUT_CSV).parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(OUT_CSV, index=False)
    print(f"\n✅ Full results saved to {OUT_CSV}")

    # ---- Recommendations
    print("\n" + "=" * 78)
    print("RECOMMENDATIONS")
    print("=" * 78)
    survivors = avg[avg["mean"] > 0.10].index.tolist()
    if survivors:
        print(f"Strategies with positive average excess Sharpe:")
        for s in survivors:
            print(f"  ✓ {s}  (mean excess: {avg.loc[s,'mean']:+.3f}, "
                  f"assets tested: {int(avg.loc[s,'count'])})")
        print(f"\n→ Run full Monte Carlo on these: {survivors}")
    else:
        print("No strategy showed positive average excess Sharpe.")
        print("→ The trend hypothesis is not supported cross-asset.")


if __name__ == "__main__":
    main()