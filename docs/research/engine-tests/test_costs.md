Test: Transaction Costs (test_costs.py)

Purpose

Verifies that transaction costs reduce portfolio performance and are actually reflected in equity.

The engine models:

Commission

Slippage

This is a mechanical accounting test, not a profitability test.

Scenario

Run the same persistent long strategy twice:

Without costs

Commission = 0 bps
Slippage = 0 bps

With costs

Commission = 1 bps
Slippage = 5 bps

Everything else remains identical.

Code

from engine.data import load_csv
from engine.core import BacktestEngine
import pandas as pd

df = load_csv("data/raw/master_5min.csv")

signals = pd.Series(1.0, index=df.index)

# WITHOUT COSTS
engine_no_cost = BacktestEngine(
    initial_cash=100_000,
    commission_bps=0,
    slippage_bps=0,
)

equity_no_cost = engine_no_cost.run(df, signals)

# WITH COSTS
engine_cost = BacktestEngine(
    initial_cash=100_000,
    commission_bps=1,
    slippage_bps=5,
)

equity_cost = engine_cost.run(df, signals)

# Compare results
final_no_cost = equity_no_cost.iloc[-1]
final_cost = equity_cost.iloc[-1]

return_no_cost = (final_no_cost / 100_000 - 1) * 100
return_cost = (final_cost / 100_000 - 1) * 100

print("WITHOUT COSTS")
print(f"Final equity: {final_no_cost:.2f}")
print(f"Return:       {return_no_cost:.2f}%")
print(f"Fills:        {len(engine_no_cost.pf.fills)}")

print("\nWITH COSTS")
print(f"Final equity: {final_cost:.2f}")
print(f"Return:       {return_cost:.2f}%")
print(f"Fills:        {len(engine_cost.pf.fills)}")

print("\nCOST IMPACT")
print(f"Difference:   {final_no_cost - final_cost:.2f}")

Expected relationship

The key expectation is:

Final equity WITHOUT costs
>
Final equity WITH costs

Therefore:

Cost impact > 0

Observed result

The NIFTY 5-minute test produced:

WITHOUT COSTS
Final equity: 289033.39
Return:       189.03%
Fills:        1

WITH COSTS
Final equity: 288878.94
Return:       188.88%
Fills:        1

COST IMPACT
Difference:   154.44

Therefore:

Cost impact = 154.44

What this proves

Commission is being charged.

Slippage affects execution.

Trading costs affect portfolio equity.

Costs reduce reported return.

The same strategy can be compared under different cost assumptions.

What this does NOT prove

It does not prove:

the strategy has an edge

the backtest is profitable

the dataset is clean

execution is fully realistic

ORB works

the cost model is realistic enough for live trading

Those require separate experiments.

Future extensions

Test sensitivity to:

0, 1, 5, 10 bps commission/slippage assumptions

trade frequency

position size

different market regimes

Status

Transaction-cost accounting: ✅ Passed
Cost-sensitivity research: ⏳ Future