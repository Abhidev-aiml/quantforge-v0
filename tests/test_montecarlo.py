# test_mc.py
from engine.data import load_csv
from engine.core import BacktestEngine
from engine.loader import load_strategy, validate_signals
from validation.monte_carlo import bootstrap_returns_iid
from validation.monte_carlo import bootstrap_trades
import json
from analytics.metrics import extract_trades

df = load_csv("data/raw/xauusd_1D_comma.csv")

def get_equity(path):
    fn = load_strategy(path)
    sig = validate_signals(fn(df), df)
    eng = BacktestEngine(initial_cash=100_000, commission_bps=1, slippage_bps=5)
    return eng.run(df, sig)

eq = get_equity("strategies/07_absolute_momentum.py")
mc = bootstrap_returns_iid(eq, n_sims=5000)
print(json.dumps(mc, indent=2))



fn = load_strategy("strategies/07_absolute_momentum.py")
sig = validate_signals(fn(df), df)
eng = BacktestEngine(initial_cash=100_000, commission_bps=1, slippage_bps=5)
eq = eng.run(df, sig)
trades = extract_trades(eng.pf.fills)

mc = bootstrap_trades(trades, n_sims=5000)
print(json.dumps(mc, indent=2))