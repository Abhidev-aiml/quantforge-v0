# NY Opening Range Breakout Strategies

**Technical reference for QuantForge's ORB strategy suite and trade execution infrastructure**

---

## ⚠️ Implementation Status: Staged for Future Work

This document describes a complete but **not yet integrated** ORB strategy research system. All components exist as working code but are isolated from the main QuantForge pipeline until current P0 issues are resolved (MC annualization, strategy params wiring, multi-asset data hash).

---

## Overview

The NY Opening Range Breakout (ORB) system represents a complete intraday trading strategy research framework for XAUUSD 5-minute data. Unlike the existing daily/4H/1H strategies in QuantForge, these strategies:

- Operate on **5-minute bars** with explicit timezone handling (UTC+3 source → America/New_York)
- Use a **discrete trade plan model** with explicit stop-loss and take-profit levels, rather than continuous portfolio weight signals
- Require **intraday session logic** (9:30-10:00 NY opening range, 15:30 entry cutoff)
- Include a **trade-by-trade execution simulator** separate from the main BacktestEngine

### Current Implementation Status

**Core Components** — ✅ Implemented
- Seven ORB strategy variations (17-23)
- Shared utilities (orb_utils.py)
- Trade plan dataclass (trade_plan.py)
- Trade execution engine (trade_execution.py)

**Integration with Main Pipeline** — ⚠️ Not Started
- ORB strategies do **not yet connect** to execute/run_from_config.py or the main analytics/Monte Carlo pipeline
- They require a different execution model (discrete trades vs continuous signals)

---

## Architecture

### Two-Layer Execution Model

**Design Principle**: ORB strategies separate **signal generation** (when to enter) from **trade execution** (how to manage the trade with stops and targets). This enables testing entry logic independently before adding risk management complexity.

**Layer 1: Signal Generation**
- Each strategy implements the standard QuantForge `generate_signals(df)` contract
- Returns a Series of {-1, 0, +1} directional signals
- Signals indicate breakout direction but do not specify stops or targets

**Layer 2: Trade Execution**
- The `TradePlan` and `execute_trade()` infrastructure converts signals into discrete trades
- Includes entry price, stop-loss/take-profit levels, risk per unit calculation
- Bar-by-bar exit logic (stop hit, target hit, or end of data)

### File Structure

```
strategies/
├── orb_utils.py                    # Shared ORB infrastructure
├── 17_ny_orb_breakout.py          # Pure breakout
├── 18_ny_orb_retest.py            # Breakout + retest
├── 19_ny_orb_retest_rejection.py  # Retest + rejection quality
├── 20_ny_orb_quality.py           # Quality confirmation filters
├── 21_ny_orb_clv.py               # Close location value filter
├── 22_ny_orb_atr_range.py         # ORB/ATR range filter
└── 23_ny_orb_atr_regime.py        # ATR regime filter

engine/
├── trade_plan.py                   # TradePlan dataclass
└── trade_execution.py              # execute_trade() function

scripts/explore/
├── orb_data_diagnostic.py          # Dataset validation
└── orb_signal_audit.py             # Signal verification

tests/
├── test_ny_orb_variations.py       # ORB utility tests
├── test_trade_plan.py              # TradePlan validation tests
└── test_trade_execution.py         # Trade execution tests
```

---

## ORB Strategy Variations

All strategies share the same core logic but differ in **entry confirmation requirements**. The progression moves from simple breakout to increasingly filtered entries.

### Strategy 17: Pure Breakout
First 5M close above ORB high (long) or below ORB low (short) after 10:00 NY. No confirmation required.

### Strategy 18: Retest
Breakout → retest (touches ORB level and closes beyond it) → confirmation candle closes past breakout extreme.

### Strategy 19: Retest + Rejection
Adds quality filter to retest: long retest must close in upper half, short retest in lower half.

### Strategy 20: Quality Confirmation
Confirmation candle must have body/range ≥ 0.60 and CLV ≥ 0.70 (long) or ≤ 0.30 (short).

### Strategy 21: CLV Filter
Confirmation CLV ≥ 0.70 (long) or ≤ 0.30 (short) only, no body ratio filter.

### Strategy 22: ORB/ATR Range
Accepts only when 0.50 ≤ (ORB range / pre-breakout ATR) ≤ 2.50. Filters out extreme volatility days.

### Strategy 23: ATR Regime
Requires pre-breakout ATR(14) ≥ historical 50th percentile. Only trades elevated volatility environments.

### Common ORB Specifications

| Parameter | Value | Notes |
|-----------|-------|-------|
| Instrument | XAUUSD | Gold spot vs US Dollar |
| Timeframe | 5 minutes | ~288 bars per day |
| Source Timezone | UTC+3 | Raw CSV timestamps |
| Target Timezone | America/New_York | EDT/EST automatic handling |
| ORB Window | 09:30–10:00 NY | Exactly 6 bars required |
| Entry Cutoff | 15:30 NY | No entries after this time |
| ORB High | `max(ORB bars high)` | Calculated per day |
| ORB Low | `min(ORB bars low)` | Calculated per day |

---

## Trade Execution Infrastructure

### TradePlan Dataclass

The `TradePlan` represents one intended trade with full entry and risk specification:

```python
@dataclass(frozen=True)
class TradePlan:
    trade_date: object          # NY calendar date
    direction: Direction        # "LONG" or "SHORT"
    
    signal_time: object         # When signal was generated
    entry_time: object          # Execution timestamp
    
    entry_price: float          # Entry level
    stop_price: float           # Stop-loss level
    target_price: float         # Take-profit level
    
    risk_per_unit: float        # Distance from entry to stop
```

**Validation rules:**
- **LONG:** `stop_price < entry_price < target_price`
- **SHORT:** `target_price < entry_price < stop_price`
- `risk_per_unit` must be > 0

**Computed properties:**
- `risk_points` — absolute entry-to-stop distance
- `reward_points` — absolute entry-to-target distance
- `planned_rr` — reward/risk ratio

### Trade Execution Logic

The `execute_trade(df, trade_plan)` function simulates one trade against OHLC data:

**Execution Assumptions:**
1. Entry occurs at the `TradePlan.entry_time` bar at `entry_price`
2. Stop and target are evaluated from bars **after** entry
3. If both stop and target are touched in the same bar, **stop takes precedence** (conservative)
4. Gap through stop or target → execution at bar open
5. If neither is reached before data ends → exit at final close

**Exit reasons:**
- `"STOP"` — stop-loss was hit
- `"TARGET"` — take-profit was reached
- `"END_OF_DATA"` — neither reached, exited at last available price

**Returns ExecutionResult with:**
- Exit time, price, and reason
- Bars held
- `gross_points` — price PnL in asset units
- `r_multiple` — outcome measured in risk units (e.g., +2.5R = 2.5× risk captured)

---

## Diagnostic Tools

### Data Diagnostic (orb_data_diagnostic.py)

Validates the raw XAUUSD 5M dataset **before** attempting strategy logic. Checks:
- Dataset existence and structure
- Timestamp parsing and timezone conversion
- Duplicate timestamp detection
- ORB window coverage (exactly 6 bars at 09:30–10:00 NY?)
- Bar spacing (5-minute intervals)
- Breakout candidate audit

**Purpose:** Isolate data quality issues from strategy bugs.

### Signal Audit (orb_signal_audit.py)

Independent validation of **strategy #17 (pure breakout)** signal generation:
- Does **not** import `orb_utils.py` for its reference calculation
- Reconstructs the ORB/breakout logic from scratch
- Loads strategy #17 and compares its signals to the independent reference
- Reports matched, missing, unexpected, and direction-mismatched signals

**Purpose:** Verify that `generate_orb_signals()` produces exactly the signals expected from the research specification.

---

## Test Coverage

### tests/test_ny_orb_variations.py
Unit tests for ORB utilities:
- Summer/winter UTC+3 → NY timezone conversion
- ORB level calculation from exactly 6 bars
- Invalid ORB detection (missing bars, wrong spacing)

### tests/test_trade_plan.py
Tests for `TradePlan` validation:
- Valid LONG plan (stop below entry, target above)
- Valid SHORT plan (stop above entry, target below)
- Rejection of inverted geometry
- Risk calculation correctness
- `planned_rr` property computation

### tests/test_trade_execution.py
Tests for `execute_trade()` logic:
- LONG/SHORT trade hitting stop
- LONG/SHORT trade hitting target
- Gap through stop/target (execution at open)
- Both stop and target touched in same bar → stop wins
- End-of-data exit when neither is reached
- Entry at last bar (immediate END_OF_DATA)

---

## Integration Plan

To connect ORB strategies to the main QuantForge pipeline, the following work is required:

### 1. Create ORB-Specific Runner

A new `execute/run_orb_from_config.py` module that:
- Loads 5M XAUUSD data
- Generates ORB signals via `generate_signals()`
- Converts signals to `TradePlan` objects (requires defining stop/target placement rules)
- Executes each plan via `execute_trade()`
- Aggregates `ExecutionResult` objects into equity curve and trade list
- Computes metrics via `analytics/metrics.py`
- Runs Monte Carlo validation

### 2. Define Stop/Target Rules

Current implementation separates signal generation from risk management. Integration requires choosing:
- **Fixed R:R ratio** (e.g., 1:2 or 1:1.5)
- **ATR-based stops** (e.g., stop = entry ± 1.5× ATR)
- **ORB-range-based stops** (e.g., stop = ORB boundary)
- **Time-based exits** (e.g., close at end of day if neither stop/target hit)

### 3. Extend Config Schema

Add ORB-specific config fields to `engine/config.py`:

```python
@dataclass
class OrbConfig:
    data_path: str              # 5M XAUUSD CSV
    strategy_path: str          # strategies/17-23_*.py
    stop_atr_multiple: float    # Stop distance in ATR
    rr_ratio: float             # Target distance as multiple of stop
    entry_cutoff: str           # "15:30"
```

### 4. Handle Intraday Annualization

Current `analytics/metrics.py` assumes daily or lower frequency. For 5M bars:
- Infer `periods_per_year` from data (should be ~75,000 for 5M)
- Or compute equity curve at **daily** frequency (one equity point per day, aggregating intraday trades)
- Monte Carlo methods may need adjustment for trade-level bootstrap vs return-level bootstrap

### 5. Test End-to-End

Once integrated:
- Run full backtest for strategy #17 (simplest)
- Verify equity curve, trade extraction, metrics
- Compare to manual calculation of 10 sample trades
- Run Monte Carlo validation
- Extend to strategies 18-23

---

## Next Steps

### ⚠️ Priority Queue

ORB integration is **deferred** until P0 issues in the main QuantForge system are resolved. Do not start ORB integration work until the following are complete.

### Current P0 Blockers

1. **Fix MC annualization inconsistency** — `validation/monte_carlo.py` functions must accept and use `periods_per_year` consistently
2. **Wire strategy params to execution** — `execute/run_from_config.py` must pass `strategy.params` to `generate_signals()`
3. **Add multi-asset data hash** — `execute/run_multi_from_config.py` must compute and record universe data fingerprint in manifest
4. **Standardize benchmark API** — Resolve multiple cost-adjusted benchmark implementations

### Once P0 Work is Complete

Resume ORB integration with this sequence:
1. Load `artifact-capabilities` skill (if available) to enable live data / persistence
2. Implement stop/target placement rules (start with simplest: fixed R:R ratio)
3. Create `execute/run_orb_from_config.py` following the integration plan above
4. Test strategy #17 end-to-end
5. Extend to strategies 18-23
6. Run parameter sweeps on stop/target rules
7. Compare ORB performance to existing daily strategies on out-of-sample data

### Open Research Questions

- What stop/target placement rules produce stable out-of-sample results?
- Do any ORB variations (18-23) beat pure breakout (#17) after transaction costs?
- How sensitive are results to entry cutoff time (15:30 vs 14:00 vs EOD)?
- Should confirmation filters be optimized per-asset or kept as cross-asset constants?
- Does intraday ORB edge hold on other instruments (equity indices, FX majors)?

---

## Final Note

The ORB system represents a **complete but parallel** research track. All components are functional and tested. Integration requires bridging two execution models (continuous signals vs discrete trades) and ensuring intraday data handling is consistent with QuantForge's existing timeframe-agnostic design.

---

**Generated:** 2026-09-13  
**Status:** Deferred pending P0 resolution  
**Components:** 9 files (strategies, engine, tests, diagnostics)
