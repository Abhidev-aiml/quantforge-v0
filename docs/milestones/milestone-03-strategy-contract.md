Milestone 3 — Strategy Contract

Project: QuantForge v0
Milestone: 03
Status: ✅ Completed

1. Milestone Objective

Milestone 3 established a strict Strategy Contract that separates strategy logic from the backtesting engine.

Every strategy follows the same interface:

def generate_signals(df: pd.DataFrame) -> pd.Series:

The engine does not need to know how a strategy works internally. It only consumes validated target-weight signals.

2. Strategy Contract

A valid strategy:

Accepts a pandas DataFrame.

Returns a pandas Series.

Returns the same number of signals as market-data rows.

Uses exactly the same index as the input data.

Produces numeric target weights.

Keeps target weights within [-1.0, +1.0].

Signal interpretation:

+1.0 → 100% long
 0.0 → flat
-1.0 → 100% short

3. Strategy Loader

engine/loader.py was implemented to dynamically load strategy files.

The loader:

Checks that the strategy file exists.

Requires a .py file.

Imports the strategy using importlib.util.

Checks that generate_signals exists.

Checks that it is callable.

Returns the strategy function for execution.

4. StrategyError

A dedicated StrategyError exception was implemented.

This provides clear and controlled errors when a strategy violates the contract instead of allowing confusing downstream engine failures.

5. Signal Validation

validate_signals() was implemented to enforce the strategy contract.

The validation layer checks:

Return type: must be pd.Series.

Length: must exactly match the market-data DataFrame.

Index: must exactly match the DataFrame index.

Numeric values: signals must be numeric.

Signal range: values must remain within [-1.0, +1.0].

Validated signals are converted to floating-point values, and remaining NaN values are converted to 0.0, representing a flat position during warm-up.

6. Reference Strategies

Two valid reference strategies were implemented.

Buy & Hold

Produces a continuous +1.0 target.

SMA Crossover

Uses:

20-period SMA

100-period SMA

Signal logic:

Fast SMA > Slow SMA → +1.0
Fast SMA < Slow SMA → -1.0
Otherwise → 0.0

Both demonstrate that different strategy logic can plug into the same engine without modifying the engine itself.

7. Negative / Broken Strategy Tests

Deliberately invalid strategies were created to verify that the contract fails correctly.

Test Case

Expected Behavior

Result

Wrong return type

Reject list instead of Series

✅ PASS

Missing generate_signals

Reject invalid function name

✅ PASS

Out-of-range leverage

Reject values such as 3.0

✅ PASS

Lookahead example

Document future-information bias

✅ PASS

The lookahead example is educational only and is not a legitimate trading strategy.

8. Loader Test Suite

Five loader experiments were completed:

Experiment

Test

Result

1

Buy & Hold happy path

✅ PASS

2

SMA crossover

✅ PASS

3

Wrong return type

✅ Caught correctly

4

Missing generate_signals

✅ Caught correctly

5

Out-of-range signal

✅ Caught correctly

Valid strategies load and validate successfully, while invalid strategies fail with clear StrategyError messages.

9. Architecture After Milestone 3

┌─────────────────────┐
│     Market Data     │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│  Strategy Loader    │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ generate_signals()  │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ Signal Validation   │
│                     │
│ • Type              │
│ • Length            │
│ • Index             │
│ • Numeric           │
│ • Range             │
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│  Backtest Engine    │
└─────────────────────┘

QuantForge now cleanly separates:

Data
Strategy
Validation
Execution

10. Quant Engineering Significance

The strategy contract is an important architectural milestone because strategy development is now decoupled from execution.

A new strategy can follow:

Create strategy file
        ↓
Implement generate_signals(df)
        ↓
Validate signals
        ↓
Run through engine

The core engine does not need to be rewritten for each strategy.

This makes future strategy research easier to develop, test, reproduce, and compare.

11. Data Contract Note

The original Milestone 3 specification describes market data containing:

open
high
low
close
volume

The current NIFTY 5-minute dataset contains OHLC data without volume.

This difference has been documented as a design consideration rather than silently changing the original Milestone 3 contract.

12. Completion Checklist

Strategy contract defined

generate_signals(df) interface established

StrategyError implemented

load_strategy() implemented

Dynamic strategy loading implemented

Return type validation implemented

Signal length validation implemented

Signal index validation implemented

Numeric validation implemented

[-1, +1] range validation implemented

Signal normalization implemented

Buy & Hold strategy validated

SMA crossover strategy validated

Broken strategy cases tested

Lookahead example documented

Five loader experiments completed

Strategy/engine separation established

Milestone 3 Result

✅ COMPLETED

QuantForge v0 now has a validated, reusable strategy interface.

The core contract is:

def generate_signals(df: pd.DataFrame) -> pd.Series:

Strategies can now be created, loaded, validated, and passed to the backtesting engine without coupling strategy implementation to engine logic.

Milestone 3 successfully establishes the Strategy Layer of QuantForge v0.