# QuantForge Architecture

## Document Purpose

This document is the architecture-level handoff for QuantForge. It
describes the **actual project structure and responsibilities
reconstructed from the current repository files reviewed during the
audit**, rather than relying only on the original mental model.

QuantForge is a research-oriented event-driven backtesting framework
designed for solo quantitative research across single assets, multiple
assets, daily data, and intraday data including 4H and 1H datasets. The
system separates data ingestion, configuration, execution, strategy
generation, analytics, validation, and experiment orchestration.

---

## 1. High-Level Architecture

```
                           QuantForge
                               |
        +----------------------+----------------------+
        |                      |                      |
        v                      v                      v
     Data Layer          Configuration          Research / Execution
        |                      |                      |
        |                      v                      v
        |                 Run Context          Experiment Runners
        |                      |                      |
        +----------+-----------+-----------+----------+
                   |                       |
                   v                       v
             Strategy Layer          Engine Layer
                   |                       |
                   +-----------+-----------+
                               |
                               v
                         Analytics Layer
                               |
                               v
                       Validation Layer
                               |
                               v
                         Results / Reports
```

The intended control flow for a canonical single-asset run is:

```
YAML config
   -> load/validate config
   -> create RunContext
   -> load + validate data
   -> hash/cache data
   -> load strategy
   -> validate signal contract
   -> run BacktestEngine
   -> extract trades
   -> compute metrics
   -> run configured validation
   -> write artifacts + manifest
```

The multi-asset path follows the same principle but uses multi-symbol
data preparation, cross-sectional signals, MultiAssetBacktestEngine,
and multi-asset analytics.

---

## 2. Layered Components

### 2.1 Data Layer

#### engine/data.py

Primary single-file OHLCV ingestion and integrity layer.

Responsibilities:

- Load a CSV into a pandas DataFrame.
- Normalize column names and supported aliases.
- Parse the date column into the index.
- Sort chronologically.
- Remove duplicate timestamps.
- Validate OHLC relationships.
- Validate non-negative volume.
- Drop rows with required-column NaNs.
- Cache cleaned data as Parquet.
- Produce a deterministic SHA-256 data fingerprint.

Current production contract requires:

```
open
high
low
close
volume
```

The active aliases include date, datetime, timestamp, vol, and
adj close. A historical NIFTY/OHLC-only implementation remains as
commented code and is not the active path.

#### engine/multi_data.py

Multi-symbol data preparation layer.

Responsibilities:

- Discover symbols from CSV files.
- Load multiple single-asset datasets.
- Determine a common/union index.
- Align symbols to a shared timeline.
- Prepare the data structure expected by the multi-asset engine.
- Compute a deterministic universe-level data hash.

The current design deliberately uses a union of timestamps so that a
missing market session for one asset does not remove the entire
timestamp from the universe.

A current research concern is the distinction between a forward-filled
price used for portfolio valuation and a genuinely tradable bar. The
implementation currently forward-fills OHLC for alignment and sets
missing volume to zero, so this behavior must remain an explicit
research consideration and should be strengthened with a
tradability/session model in a future refinement.

#### Data layout

```
data/raw/daily/       daily CSV datasets
data/raw/fourhours/   4H datasets
data/raw/onehours/    1H datasets
data/raw/daily_mc/    legacy/MC-oriented daily dataset collection
data/cache/           Parquet caches
```

### 2.2 Configuration Layer

#### engine/config.py

Pydantic-based configuration and experiment overlay system.

Single-asset configuration contains models for:

- DataConfig
- EngineConfig
- StrategyConfig
- MonteCarloConfig
- OutputConfig
- AppConfig

Multi-asset configuration adds:

- MultiDataConfig
- XSMomentumConfig
- MultiAssetAppConfig

The loader supports:

```
base YAML
   +
experiment overlay
   -> deep merge
   -> Pydantic validation
   -> typed configuration
```

Configuration hashes are generated deterministically for
reproducibility. A separate multi-asset hash function also exists.

#### Configuration layout

```
configs/
├── base.yaml
└── experiments/
    ├── gold_abs_momentum.yaml
    ├── gold_abs_momentum_wf.yaml
    ├── gold_goldencross.yaml
    ├── gold_goldencross_wf.yaml
    ├── xs_momentum_14assets.yaml
    └── xs_momentum_daily.yaml
```

### 2.3 Run Context and Reproducibility

#### engine/run_context.py

RunContext is the reproducibility/artifact boundary for canonical runs.

It creates a unique run directory and writes manifest.json containing
run metadata including:

- run ID
- UTC start time
- Git SHA
- dirty/clean Git state
- config hash
- Python/platform information
- serialized configuration

It can subsequently persist:

- data hash
- results summary
- finish time

Standard artifact names include:

```
manifest.json
equity.csv
fills.csv
trades.csv
metrics.json
monte_carlo.json
```

The run-context tests verify manifest creation, config hash persistence,
data hash persistence, result persistence, completion timestamp, and
unique run IDs.

---

## 3. Engine Layer

### 3.1 Single-Asset Engine

#### engine/core.py

BacktestEngine is the core event-driven single-asset execution engine.

#### Execution invariant

```
Signal generated from bar t close
        |
        v
Queued target
        |
        v
Execute at bar t+1 open
        |
        +--> slippage in direction of trade
        +--> commission on notional
        |
        v
Position / cash update
        |
        v
Mark portfolio to current close
```

The engine supports:

- long exposure
- flat exposure
- short exposure
- no-trade bands
- warmup bars
- commission
- slippage
- exact flattening
- fill records
- deterministic equity curves

When the target is exactly flat, the engine sells the exact current
position so floating-point dust cannot create a phantom sign flip.

The current tests explicitly cover next-bar execution, last-bar
non-execution, long/short accounting, transaction costs, exact flat
exits, deterministic results, and fill structure.

Warmup support suppresses early signals and is regression-tested.

### 3.2 Multi-Asset Engine

#### engine/multi_core.py

MultiAssetBacktestEngine and MultiAssetPortfolio extend the
execution model to multiple symbols with shared cash and per-symbol
positions/fills.

The engine:

- accepts symbol-keyed DataFrames
- accepts a date × symbol target-weight matrix
- processes the union of symbol timestamps
- supports warmup
- supports short restrictions
- supports no-trade bands
- records symbol-aware fills
- maintains per-symbol positions within one portfolio

The multi-asset tests cover construction, equal-weight exposure, flat
portfolios, shorts, exact flattening, costs, determinism,
allow_short=False, and symbol-aware fills.

A research issue remains around missing-symbol sessions and
tradability after multi-symbol alignment.

---

## 4. Strategy Layer

### 4.1 Strategy Contract

#### engine/loader.py

Strategies are dynamically loaded from Python modules and must define:

```python
def generate_signals(df):
    ...
```

Optionally, strategies may accept a params argument:

```python
def generate_signals(df, params=None):
    ...
```

The loader validates:

- file existence
- .py extension
- importability
- presence of generate_signals
- callable function
- pandas Series return type
- equal length to data
- exact index match
- numeric dtype
- values constrained to [-1, +1]
- NaN conversion to zero

call_strategy(fn, df, params) inspects the function signature and
passes params only if the signature accepts them. This keeps older
strategies compatible while allowing new parameterized strategies.

### 4.2 Shared Indicators

#### strategies/indicators/indicators.py

The shared indicator library currently contains:

```
SMA
EMA
RSI
Bollinger Bands
ATR
Donchian Channel
MACD
Z-score
ROC
```

### 4.3 Classic Strategy Files

The current source tree contains:

```
00_buy_hold.py
01_goldencross.py
02_emacross.py
03_rsi_meanrev.py
04_bollinger_meanrev.py
05_donchian_breakout.py
06_macd_cross.py
07_absolute_momentum.py
08_atr_breakout.py
09_zscore_meanrev.py
10_roc_momentum.py
15_trend_pullback_4h.py
16_trend_pullback_1h.py
25_bollinger_rsi_double.py
xs_momentum.py
```

Historical/experimental strategies also exist in compiled artifacts and
research history, including Donchian/ADX and Orion-style variants.
Those are not all active source files in the current tree.

### 4.4 Cross-Sectional Momentum

#### strategies/xs_momentum.py

The cross-sectional momentum generator ranks symbols by historical
return while skipping a recent period, then constructs target weights
for the strongest symbols and optionally the weakest symbols.

Current defaults:

```
lookback       = 252
skip           = 21
top_k          = 3
bottom_k       = 3
rebalance      = monthly
offset         = long/short
gross exposure = 1.0
```

The implementation keeps weights fixed between rebalances using forward
filling.

---

## 5. Analytics Layer

#### analytics/metrics.py

The analytics layer computes portfolio-level and trade-level
diagnostics.

Current metric families include:

```
Returns
- total return
- CAGR (calendar-aware when DatetimeIndex available)
- number of periods
- years

Risk
- volatility
- downside deviation
- maximum drawdown
- average drawdown
- drawdown duration (bars and days)

Risk-adjusted
- Sharpe
- Sortino
- Calmar

Tail/distribution
- VaR 95
- CVaR 95
- VaR 99
- CVaR 99
- skew
- kurtosis

Trade-level
- number of trades
- win rate
- profit factor
- expectancy
- average win/loss
- payoff ratio
- expectancy %
- average win/loss %

Portfolio analytics
- multi-asset trade extraction
- turnover
- gross exposure
- net exposure
```

compute_metrics accepts periods_per_year=None and auto-infers the
annualization factor from a DatetimeIndex. It also auto-detects
elapsed years when not supplied.

Trade extraction supports flat-to-position, position-to-flat,
directional flips, same-direction scale-ins, and floating-point
tolerance. The resulting trade record contains entry/exit information,
direction, quantity, PnL, commissions, and a scale_ins count.

---

## 6. Validation Layer

### validation/monte_carlo.py

Current validation primitives include:

```
bootstrap_returns_iid              (timeframe-aware)
bootstrap_returns_block            (timeframe-aware)
bootstrap_returns_under_null       (timeframe-aware)
bootstrap_trades                   (timestamp-aware years)
bootstrap_trades_block             (timestamp-aware years)
signal_block_shuffle               (uses configured costs)
same_exposure_benchmark_cost_adjusted
```

All MC functions accept periods_per_year and auto-infer it from
DatetimeIndex if None. All engine construction inside MC uses the
experiment's commission/slippage parameters.

### validation/walk_forward.py

Rolling-window in-sample / out-of-sample validation with per-window
benchmark comparison.

Splits data into overlapping windows:

```
[---- train ----][-- test --]
    [---- train ----][-- test --]
        [---- train ----][-- test --]
```

Each OOS window is compared against a same-exposure cost-adjusted
passive benchmark. The module also builds a chained OOS equity
curve by concatenating non-overlapping OOS segments, which recovers
the full statistical power of the out-of-sample period.

Two verdicts:

- **robust** — degradation_ratio ≥ 0.5 and mean OOS Sharpe > 0 and
  percentage of positive OOS windows ≥ 50%
- **has_edge** — chained OOS excess Sharpe > 0.20

Per-window fields include low_confidence (fewer than N trades),
which is critical for low-turnover strategies.

### validation/whites_reality_check.py

White's Reality Check (2000). Multiple-testing correction across K
strategy-asset combinations.

Accepts a (T, K) matrix of per-bar excess returns (strategy return
minus same-exposure benchmark return). Uses Politis & Romano (1994)
stationary block bootstrap with the SAME resampled time indices across
all K columns, preserving cross-strategy correlation.

Test statistic: V = sqrt(T) · max_k(mean(f_k))

Bootstrap distribution: resample with each column centered at its
observed mean under H0. p-value = fraction of bootstrap V ≥ observed V.

Reports p-value, best combo, top-5 combos by excess return, bootstrap
distribution summary, and interpretation.

---

## 7. Execution / Experiment Layer

### Canonical execution paths

#### execute/run_from_config.py

The primary config-driven single-asset pipeline.

Intended flow:

```
config
 -> RunContext
 -> load data
 -> cache/hash
 -> load strategy
 -> validate signals (via call_strategy)
 -> BacktestEngine
 -> trades
 -> metrics
 -> MC
 -> artifacts + manifest
```

It uses configured engine costs and warmup values, passes strategy
params via call_strategy, and records the data hash in the run
context.

#### execute/run_multi_from_config.py

The primary multi-asset pipeline. Discovers symbols from a directory,
builds the XS momentum weight matrix, runs the multi-asset engine,
compares against an equal-weight benchmark, and records the universe
hash.

#### execute/run_walk_forward.py

Walk-forward validation runner. Reads walk_forward: config section,
loads strategy, runs rolling IS/OOS with benchmark comparison, saves
per-window metrics and aggregate to results/runs/<run_id>/.

#### execute/run_whites_rc.py

White's Reality Check runner. Enumerates strategies × assets, builds
the excess-return matrix, runs RC, saves results to
results/whites_rc/<timestamp>/.

### Exploratory / legacy execution tooling

The repository also contains:

```
execute/execute_all.py
execute/execute_runner.py
execute/execute_montecarlo.py
execute/screen_all_assets.py
execute/golden_cross_sweep.py
execute/golden_cross_sweep_fast.py
execute/mc_targeted.py
execute/researcher_workflow.py
```

These are historical research tooling. Useful for reference but not
part of the canonical pipeline.

---

## 8. ORB Research Infrastructure (Deferred)

The ORB (Opening Range Breakout) suite exists as parallel
infrastructure:

```
strategies/orb_utils.py
strategies/17_ny_orb_breakout.py
strategies/18_ny_orb_retest.py
strategies/19_ny_orb_retest_rejection.py
strategies/20_ny_orb_quality.py
strategies/21_ny_orb_clv.py
strategies/22_ny_orb_atr_range.py
strategies/23_ny_orb_atr_regime.py

engine/trade_plan.py
engine/trade_execution.py
```

Test coverage exists in test_ny_orb_variations.py,
test_orb_signal_audit.py, test_trade_execution.py, and
test_trade_plan.py.

Status: All components implemented and tested. Not integrated with
main pipeline. Requires a dedicated runner (run_orb_from_config.py)
and stop/target placement rules.

---

## 9. Testing Architecture

The repository contains 146 passing tests across 21 modules. Test
categories:

```
Config layer:      test_config, test_run_context
Data layer:        test_data, test_multi_data_hash
Engine layer:      test_engine, test_engine_warmup, test_multi_engine
Strategy layer:    test_loader, test_strategy_params, test_xs_momentum
Analytics layer:   test_metrics, test_metrics_cagr
Validation:        test_montecarlo, test_montecarlo_cost_adj,
                   test_montecarlo_timeframe, test_walk_forward,
                   test_whites_reality_check
ORB layer:         test_ny_orb_variations, test_orb_signal_audit,
                   test_trade_execution, test_trade_plan
```

Deterministic fixtures are generated in tests/fixtures/ by
tests/fixtures/generate.py.

Core invariants under test:

```
Signal on bar t close -> execution on t+1 open
Last-bar signal does not execute
Transaction costs reduce returns
Flat target returns position exactly to zero
Equity curve length/index matches data
Same inputs produce deterministic outputs
Signals stay within [-1, +1]
Invalid strategies are rejected
CAGR can use actual datetime duration
Monte Carlo procedures are deterministic for fixed seed
Null bootstrap SE matches theoretical value
Walk-forward windows are non-overlapping
White's RC centers each column at zero under null
```

---

## 10. Results and Artifact Layout

```
results/
├── golden_cross_daily_*.csv       (legacy research)
├── golden_cross_fast_*.csv        (legacy research)
├── golden_cross_sweep_fast.csv    (legacy research)
├── screen_all_assets.csv          (cross-asset screen)
├── monte_carlo/                   (per-strategy MC JSON)
├── mc_targeted/                   (focused MC JSON)
├── whites_rc/                     (White's RC runs)
└── runs/                          (canonical RunContext runs)
```

Canonical runs write to results/runs/<run_id>/ with manifest,
equity, fills, trades, metrics, and any validation artifacts.

---

## 11. Architecture Invariants

### Execution

- Signals are interpreted from the close of bar t.
- The resulting target is executed at the open of bar t+1.
- The final bar cannot execute a signal.
- Flat targets close exactly the current position.
- Slippage moves execution price against the trade.
- Commission is charged on executed notional.

### Strategy contract

- Strategies expose generate_signals(df) or
  generate_signals(df, params).
- The returned signal object is a pandas Series.
- Its index exactly matches the input data.
- Values must be numeric and lie in [-1, +1].

### Reproducibility

- Configuration is schema-validated.
- Configuration hashes are deterministic.
- Data hashes are deterministic (single-asset and multi-asset).
- RunContext stores a manifest containing run metadata and hashes.
- Fixed-seed Monte Carlo operations are deterministic.

### Research methodology

- Screening results are not treated as final engine results.
- Fast Golden Cross Stage 1 is explicitly approximate.
- Stage 2 uses the real execution engine.
- Low-sample candidates require caution.
- Monte Carlo and benchmark comparisons are used as validation
  layers rather than optimization objectives.
- Walk-forward must include per-window benchmark comparison; a
  strategy that is walk-forward robust but has no excess return
  over beta has no edge.

---

## 12. Current Architecture Gaps

### Resolved (Session A)

- ~~MC annualization inconsistency~~
- ~~Trade bootstrap hard-coded 21.6 years~~
- ~~Strategy params not wired~~
- ~~Multi-asset data hash missing~~

### Remaining

- **Tradability semantics for multi-asset** — union-index forward-fill
  means some symbols are valued on bars where they did not trade.
- **Benchmark implementations not unified** — single-asset uses
  same_exposure_benchmark_cost_adjusted; multi-asset uses a
  monthly-rebalanced equal-weight benchmark that doesn't charge costs
  the same way.
- **periods_per_year=252 default** in compute_metrics signature —
  callers can override but the default can be misused on intraday data.
- **extract_trades scale-in limitation** — same-direction scale-ins
  are folded into the parent trade, not split out as separate lots.

### Research roadmap (deferred)

- White's Reality Check ✅ (implemented)
- Walk-forward ✅ (implemented)
- Purged cross-validation
- Deflated Sharpe ratio
- Combinatorially Symmetric Cross-Validation
- Optuna / systematic hyperparameter optimization

---

## 13. Environment

```
Python 3.11
.venv/

pandas
numpy
pyarrow
scipy
pydantic
PyYAML
statsmodels
pytest
```

Run from repository root using .venv.

---

## 14. Architectural Status

The codebase has evolved from a single-asset backtesting prototype into
a multi-layer research framework with a complete validation stack.

```
Data
  ↓
Config / Run Context
  ↓
Strategy
  ↓
Engine
  ↓
Analytics
  ↓
Validation
  ↓
Research Results
```

The most important architectural principle is separation of concerns:

- strategies produce target signals/weights
- engines handle execution and portfolio accounting
- analytics measure performance
- validation tests whether the observed performance is plausibly
  attributable to skill rather than noise
- configuration and run context preserve reproducibility

As of Session C, the framework has been used to produce a definitive
negative result: the classic retail strategy universe on daily/4H
data across 13 assets has no demonstrable edge over a same-exposure
passive benchmark.
