import pandas as pd
from engine.data import load_csv
from engine.core import BacktestEngine
from engine.loader import load_strategy, validate_signals
from analytics.metrics import compute_metrics, extract_trades
import json
import numpy as np
df = load_csv("data/raw/xauusd_1h_comma.csv")   # or a real CSV, ideally 5+ years

# def run(strategy_path):
#     fn = load_strategy(strategy_path)
#     sig = validate_signals(fn(df), df)
#     eng = BacktestEngine(initial_cash=100_000, commission_bps=1, slippage_bps=5)
#     eq = eng.run(df, sig)
#     trades = extract_trades(eng.pf.fills)
#     return eq, trades


# # --- Experiment 1: buy-and-hold metrics ---
# eq, trades = run("strategies/buy_hold.py")
# m = compute_metrics(eq, rf_annual=0.04, trades=trades)
# print("Exp 1 ✅ buy_hold:")
# print(json.dumps(m, indent=2, default=str))

# # --- Experiment 2: SMA strategy metrics ---
# eq, trades = run("strategies/sma_cross.py")
# m = compute_metrics(eq, rf_annual=0.04, trades=trades)
# print("Exp 2 ✅ sma_cross:")
# print(json.dumps(m, indent=2, default=str))

# # --- Experiment 3: cheat lookahead strategy metrics ---
# eq, trades = run("strategies/cheat_lookahead.py")
# m = compute_metrics(eq, rf_annual=0.04, trades=trades)
# print("Exp 3 ✅ cheat_lookahead:")
# print(f"Sharpe: {m['sharpe']:.2f}  CAGR: {m['CAGR']:.2%}  MaxDD: {m['max_drawdown']:.2%}")

 # Randomly generate signals and run backtest
# rng = np.random.default_rng(42)
# for seed in [1, 2, 3, 4, 5]:
#     rng = np.random.default_rng(seed)
#     sig = pd.Series(rng.choice([-1.0, 0.0, 1.0], size=len(df)), index=df.index)
#     eng = BacktestEngine(initial_cash=100_000, commission_bps=1, slippage_bps=5)
#     eq = eng.run(df, sig)
#     m = compute_metrics(eq)
#     print(f"seed {seed}: Sharpe={m['sharpe']:+.2f}  "
#           f"CAGR={m['CAGR']:+.2%}  MaxDD={m['max_drawdown']:.2%}")

fn = load_strategy("strategies/buy_hold.py")
sig = validate_signals(fn(df), df)
for slip in [0, 2, 5, 10, 20, 50]:
    eng = BacktestEngine(initial_cash=100_000, commission_bps=1, slippage_bps=slip)
    eq = eng.run(df, sig)
    m = compute_metrics(eq, rf_annual=0.04)
    print(f"slippage={slip:>3} bps → Sharpe={m['sharpe']:+.2f}  "
          f"CAGR={m['CAGR']:+.2%}  MaxDD={m['max_drawdown']:.2%}")