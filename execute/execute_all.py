# run_all.py
import json
from pathlib import Path
import pandas as pd
from engine.data import load_csv
from engine.core import BacktestEngine
from engine.loader import load_strategy, validate_signals
from analytics.metrics import compute_metrics, extract_trades

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

def run_one(df, path):
    try:
        fn = load_strategy(path)
        sig = validate_signals(fn(df), df)
        eng = BacktestEngine(initial_cash=100_000, commission_bps=1, slippage_bps=5)
        eq = eng.run(df, sig)
        trades = extract_trades(eng.pf.fills)
        m = compute_metrics(eq, rf_annual=0.04, trades=trades)
        return m
    except Exception as e:
        print(f"❌ {path}: {e}")
        return None

def main(data_path: str):
    df = load_csv(data_path)
    rows = []
    for path in STRATEGIES:
        m = run_one(df, path)
        if m is None:
            continue
        m["strategy"] = Path(path).stem
        rows.append(m)

    # Add buy-and-hold as a benchmark
    bh = run_one(df, "strategies/00_buy_hold.py")
    df_out = pd.DataFrame(rows).set_index("strategy")

    cols = ["CAGR", "volatility", "sharpe", "sortino", "calmar",
            "max_drawdown", "max_drawdown_duration_bars",
            "num_trades", "win_rate", "profit_factor", "expectancy"]
    
    display = df_out.copy()

    # Format percentages safely
    for c in ["CAGR", "volatility", "max_drawdown"]:
        if c in display.columns:
            display[c] = (display[c] * 100).round(2).astype(str) + "%"

    # Round floats safely
    for c in ["sharpe", "sortino", "calmar", "win_rate",
              "profit_factor", "expectancy"]:
        if c in display.columns:
            display[c] = display[c].round(3)

    # Optional: if a column is entirely missing, show it as "—"
    expected = ["CAGR", "volatility", "sharpe", "sortino", "calmar",
                "max_drawdown", "max_drawdown_duration_bars",
                "num_trades", "win_rate", "profit_factor", "expectancy"]
    for c in expected:
        if c not in display.columns:
            display[c] = "—"

    display = display[expected]

    print("\n" + "=" * 100)
    print(f"RESULTS ON: {data_path}  ({len(df)} bars, "
          f"{df.index[0].date()} → {df.index[-1].date()})")
    print("=" * 100)
    print(display.to_string())
    print("=" * 100)

if __name__ == "__main__":
    main("data/raw/xauusd_1D_comma.csv")   # ← change to your CSV