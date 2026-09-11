Test: Long → Flat (test_flat.py)

Purpose

Verifies that the engine can enter a long position and then correctly exit to a flat position.

Scenario

Using data/raw/master_5min.csv:

First 5 bars: target weight +1.0

Bar 5 onward: target weight 0.0

Execution occurs on the next bar's open.

Expected:

2 fills: BUY, then SELL

Final position should be 0 (apart from negligible floating-point noise)

Code

from engine.data import load_csv
from engine.core import BacktestEngine
import pandas as pd

df = load_csv("data/raw/master_5min.csv")

signals = pd.Series(index=df.index, dtype=float)
signals.iloc[:5] = 1.0
signals.iloc[5:] = 0.0

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

Expected checks

Number of fills = 2
Final position = 0

A meaningful residual such as -0.006 indicates an accounting issue.

Baseline observation

The baseline engine produced BUY and SELL fills but ended with approximately:

{'ASSET': -0.006023626161805851}

This indicates a target-weight accounting issue when slippage is applied.

Research question

Can an experimental execution implementation eliminate the residual while preserving next-bar execution, slippage, commission, and target weights?

Status

Baseline: ❌ Accounting issue observed
Experimental fix: ⏳ Pending