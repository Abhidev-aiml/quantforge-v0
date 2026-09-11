# researcher_workflow.py
from engine.data import load_csv
from engine.core import BacktestEngine
from engine.loader import load_strategy, validate_signals
from analytics.metrics import compute_metrics, extract_trades

df = load_csv("data/raw/xauusd_1h_comma.csv")
fn = load_strategy("strategies/03_rsi_meanrev.py")
sig = validate_signals(fn(df), df)

eng = BacktestEngine(initial_cash=100_000, commission_bps=1, slippage_bps=5)
equity = eng.run(df, sig)
trades = extract_trades(eng.pf.fills)
metrics = compute_metrics(equity, rf_annual=0.04, trades=trades)

for k, v in metrics.items():
    print(f"{k:>28}: {v}")