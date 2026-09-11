from engine.data import load_csv
from engine.core import BacktestEngine
import pandas as pd

df = load_csv("data/raw/toy.csv")

# Buy and hold: weight = 1.0 always
signals = pd.Series(1.0, index=df.index)
signals[df["close"].shift(-1) > df["close"]] = 2.0  # cheat: 200% leverage on up days
engine = BacktestEngine(initial_cash=100_000, commission_bps=1, slippage_bps=5)
equity = engine.run(df, signals)

print(equity.head())
print(equity.tail())
print(f"Total return: {equity.iloc[-1] / equity.iloc[0] - 1:.2%}")
print(f"Fills: {len(engine.pf.fills)}")
print(engine.pf.fills[:3])