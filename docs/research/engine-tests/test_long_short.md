Test: Long → Short (test_long_short.py)

Purpose

Verifies that the engine can transition directly from a long position to a short position without accidentally generating an intermediate flat target.

Scenario

Using data/raw/master_5min.csv:

First 5 bars: target +1.0

Bar 5 onward: target -1.0

Expected sequence:

BUY → LONG → SELL/reverse → SHORT

Code

from engine.data import load_csv
from engine.core import BacktestEngine
import pandas as pd

df = load_csv("data/raw/master_5min.csv")

signals = pd.Series(index=df.index, dtype=float)

signals.iloc[:5] = 1.0
signals.iloc[5:] = -1.0

engine = BacktestEngine(
    initial_cash=100_000,
    commission_bps=1,
    slippage_bps=5,
)

equity = engine.run(df, signals)

print(equity)

print("\nFills:")
for fill in engine.pf.fills:
    print(fill)

print(f"\nNumber of fills: {len(engine.pf.fills)}")
print(f"Final position: {engine.pf.positions}")
print(f"Final cash: {engine.pf.cash:.2f}")
print(f"Final equity: {equity.iloc[-1]:.2f}")

Why signal construction matters

This:

signals = pd.Series(0.0, index=df.index)
signals.iloc[0] = 1.0
signals.iloc[5] = -1.0

actually means:

+1 → 0 → 0 → 0 → 0 → -1 → 0 → ...

It therefore instructs the engine to flatten before going short and to flatten again afterward.

The correct persistent target construction is:

signals.iloc[:5] = 1.0
signals.iloc[5:] = -1.0

Expected behavior

The test should demonstrate:

Initial position: 0

After long entry: positive position

After reversal: negative position

Final position: negative

No repeated unnecessary fills while target remains -1.0

Baseline observation

The earlier test produced:

BUY  target=+1
SELL target=0
SELL target=-1
BUY  target=0

This was partly caused by the test signal construction and also exposed the residual-position issue in execution accounting.

Research question

Can the experimental execution engine correctly handle +1 → -1 with next-bar execution, slippage, commission, and no unintended flat state?

Status

Test design: ⚠️ Corrected
Accounting: ⚠️ Residual issue observed
Experimental implementation: ⏳ Pending