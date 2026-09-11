Milestone 2 — The Backtesting Engine

Project: QuantForge v0
Milestone: 02
Component: Core Backtesting Engine
Status: Baseline implemented; transition-accounting research pending

1. Objective

Milestone 2 introduces the core portfolio and execution engine.

The purpose is to move from a clean market-data pipeline to a backtester that can:

Maintain portfolio cash and positions

Calculate portfolio equity

Convert strategy signals into target portfolio weights

Execute orders on the next bar

Model slippage

Model commissions

Record fills

Produce an equity curve

Support long, flat, and short target weights

The engine is designed to be bar-based and timeframe-agnostic. It does not assume that the input is daily, 5-minute, hourly, or any other specific timeframe.

2. Baseline Engine

The canonical Milestone 2 implementation is:

engine/core.py

The baseline should be treated as the reference implementation.

Research experiments should not silently overwrite this file.

3. Core Architecture

The engine consists primarily of two components.

Portfolio

The Portfolio dataclass maintains:

cash
positions
equity_curve
fills

Cash

Available uninvested capital.

Example:

cash = 100_000

Positions

Dictionary containing the quantity held for each symbol.

Example:

{
    "ASSET": 100
}

Negative quantities represent short positions.

Equity Curve

Stores portfolio equity snapshots over time.

Example:

{
    "timestamp": timestamp,
    "equity": equity
}

Fills

Stores executed trades.

Example:

{
    "timestamp": timestamp,
    "side": "BUY",
    "qty": 100,
    "price": 100.05,
    "commission": 10,
    "target_weight": 1.0
}

4. Portfolio Equity

Portfolio equity is calculated as:

Equity = Cash + Position Market Value

For a single asset:

equity = cash + quantity * current_price

This is marked to market using the current bar's close when an equity snapshot is taken.

5. Signal Model

The engine uses target portfolio weights.

The basic interpretation is:

+1.0  → 100% long
 0.0  → flat
-1.0  → 100% short

Examples:

+1.0

means fully invested long.

0.0

means no position.

-1.0

means fully invested short.

6. Execution Model

The engine follows:

Signal on bar t close
        ↓
Pending target
        ↓
Execute on bar t+1 open

This prevents the backtest from using information from the current closing bar to trade at that same close.

This is an important protection against look-ahead bias.

Example

Suppose:

09:15 bar closes

and the strategy generates:

LONG

The engine does not execute at the 09:15 close.

Instead:

09:15 close
     ↓
signal generated
     ↓
09:20 open
     ↓
trade executed

7. Slippage

The baseline engine models slippage in basis points.

For:

slippage_bps = 5

the execution price is adjusted by:

5 / 10,000

or:

0.05%

Buy

A buy pays a higher execution price:

execution_price = open_price + slippage

Sell

A sell receives a lower execution price:

execution_price = open_price - slippage

This represents adverse price movement during execution.

8. Commission

Commission is charged on traded notional.

For:

commission_bps = 1

the commission rate is:

1 / 10,000

or:

0.01%

For a ₹100,000 trade:

commission = ₹100,000 × 0.0001
           = ₹10

9. No-Trade Band

The baseline engine includes:

no_trade_band = 0.01

This prevents very small portfolio adjustments.

Conceptually:

If required adjustment < 1% of equity:
    do nothing

This reduces unnecessary trading and avoids excessive micro-adjustments.

10. Baseline Configuration

The default engine configuration is:

BacktestEngine(
    symbol="ASSET",
    initial_cash=100_000.0,
    commission_bps=1.0,
    slippage_bps=5.0,
    no_trade_band=0.01,
)

11. Milestone 2 Tests

The following tests were used to validate the engine.

engine/test_engine.py
engine/test_flat.py
engine/test_long_short.py
engine/test_costs.py

12. Test — Buy and Hold

Objective

Verify that the engine can:

Receive a persistent +1.0 signal.

Enter on the next bar.

Apply slippage.

Apply commission.

Maintain the long position.

Mark the portfolio to market.

Signal

signals = pd.Series(1.0, index=df.index)

This represents a persistent 100% long target.

Observed Result

The NIFTY 5-minute dataset produced:

Fills: 1

BUY
timestamp: 2015-01-09 09:20
target_weight: 1.0

The trade occurred one bar after the initial 09:15 signal.

Result

PASS

13. Test — Next-Bar Execution

The engine was specifically checked to ensure that:

Signal → bar t close
Execution → bar t+1 open

For the NIFTY 5-minute data:

09:15 signal
     ↓
09:20 execution

This confirms the intended execution timing.

Result

PASS

14. Test — Slippage

The baseline engine uses:

slippage_bps=5

For the observed first trade:

Market open:     8300.65
Slippage:        5 bps
Execution price: 8304.800325

The execution price is worse for the buyer than the raw market open.

Result

PASS

15. Test — Commission

The baseline engine uses:

commission_bps=1

For the initial approximately ₹100,000 notional trade:

Commission ≈ ₹10

The fill record correctly records the commission.

Result

PASS

16. Test — Transaction Cost Impact

The same buy-and-hold strategy was run with and without costs.

Without costs

Final equity: 289033.39
Return:       189.03%
Fills:        1

With costs

Final equity: 288878.94
Return:       188.88%
Fills:        1

Cost impact

Difference: 154.44

The presence of costs therefore reduced final portfolio equity.

Result

PASS

17. Test — Long → Flat

Objective

Test:

+1.0 → 0.0

Expected behavior:

BUY
 ↓
LONG
 ↓
SELL
 ↓
FLAT

The baseline produced two fills:

BUY
SELL

However, it ended with a small residual position:

{'ASSET': -0.006023626161805851}

A target of zero should result in zero position apart from negligible floating-point noise.

Diagnosis

The baseline implementation calculates current position value using the market price while calculating trade quantity using the slippage-adjusted execution price.

This can create a small residual position.

Result

FAIL — accounting issue identified

The baseline file remains unchanged. The issue is documented for research.

18. Test — Long → Short

Objective

Test:

+1.0 → -1.0

Expected behavior:

BUY
 ↓
LONG
 ↓
SELL / reverse
 ↓
SHORT

An earlier test incorrectly constructed the signal series using zeros between the two targets.

For example:

signals = pd.Series(0.0, index=df.index)

signals.iloc[0] = 1.0
signals.iloc[5] = -1.0

actually represents:

+1 → 0 → 0 → 0 → 0 → -1 → 0 → ...

Therefore the engine correctly interpreted the zeros as flattening instructions.

A proper persistent long-to-short test should use:

signals = pd.Series(index=df.index, dtype=float)

signals.iloc[:5] = 1.0
signals.iloc[5:] = -1.0

Result

TEST DESIGN CORRECTED

The execution-accounting behavior remains a research item.

19. Weight Bounds

The engine documentation specifies that target weights should remain within:

-1.0 ≤ weight ≤ +1.0

This corresponds to:

100% short ≤ target ≤ 100% long

The baseline implementation should eventually have an explicit test for values such as:

+1.5
-1.5
+2.0
-2.0

The intended research question is whether the engine should:

Reject invalid weights, or

Clip them to the supported range.

This has not yet been finalized.

Result

PENDING

20. Milestone 2 Test Summary

Test

Result

Buy & Hold

✅ PASS

Next-Bar Execution

✅ PASS

Slippage

✅ PASS

Commission

✅ PASS

Transaction Cost Impact

✅ PASS

Long → Flat

❌ Accounting issue

Long → Short

⚠️ Test design corrected

Short → Flat

⏳ Pending

Short → Long

⏳ Pending

Weight Bounds

⏳ Pending

21. Known Limitations

Milestone 2 is intentionally a simple execution engine.

It does not yet model:

Partial fills

Bid/ask spread explicitly

Market depth

Order queue position

Limit orders

Stop orders

Intrabar execution

Tick data

Slippage based on volatility

Slippage based on liquidity

Exchange-specific fees

Taxes

Brokerage

STT

GST

Stamp duty

Short-selling restrictions

Futures contract specifications

Contract rolls

Corporate actions

Multiple simultaneous assets

Portfolio-level risk constraints

These are future milestones/research areas.

22. Timeframe Support

The core engine itself is timeframe-agnostic.

It operates on sequential OHLC bars.

Therefore the same engine can theoretically process:

1-minute
3-minute
5-minute
15-minute
30-minute
1-hour
4-hour
Daily
Weekly
Monthly

provided the data pipeline supplies correctly ordered bars.

The engine itself does not know whether a bar represents 5 minutes or one day.

Timeframe-specific logic belongs in the data and strategy layers.

For example, a 30-minute ORB strategy using 5-minute data requires the strategy layer to understand the market session and aggregate the first six 5-minute bars into a 30-minute opening range.

23. NIFTY 5-Minute Dataset

Milestone 2 was tested against:

data/raw/master_5min.csv

The dataset successfully loaded through the baseline pipeline and was processed by the engine.

Observed:

193,984 bars

Timestamps are timezone-aware and use IST (+05:30).

The observed dataset ends at:

2025-04-25 15:25:00+05:30

The actual data coverage should always be determined from the file rather than assumed from the filename.

24. Research Policy

The baseline engine should remain stable while experiments are performed.

Research implementations belong under:

engine/research/

Research documentation belongs under:

docs/research/

Each experiment should record:

Hypothesis
    ↓
Implementation
    ↓
Test
    ↓
Measurement
    ↓
Result
    ↓
Decision

An experimental change should only be promoted into the baseline after validation.

25. Next Steps

Before building the ORB strategy, the following should be completed:

Fix/validate target-weight accounting experimentally.

Add explicit assertions to engine tests.

Test Long → Flat.

Test Long → Short.

Test Short → Flat.

Test Short → Long.

Test target-weight bounds.

Build a dedicated NIFTY 5-minute data-quality validator.

Validate trading sessions and missing bars.

Validate 09:15–15:25 session structure.

Only then implement the 30-minute ORB strategy.

Milestone 2 Conclusion

The baseline QuantForge engine successfully demonstrates the fundamental mechanics required for a bar-based backtester:

Market Data
    ↓
Signal
    ↓
Next-Bar Execution
    ↓
Slippage
    ↓
Commission
    ↓
Portfolio Accounting
    ↓
Equity Curve

The core mechanics pass the initial sanity tests, while position-transition accounting has identified a specific issue that should be handled as a documented research experiment rather than silently modifying the baseline.

Milestone 2 status: Core engine operational; transition-accounting validation remains.