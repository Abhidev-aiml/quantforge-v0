# QuantForge Architecture

## Document Purpose

This document is the architecture-level handoff for QuantForge. It describes the **actual project structure and responsibilities reconstructed from the current repository files reviewed during the audit**, rather than relying only on the original mental model.

QuantForge is a research-oriented event-driven backtesting framework designed for solo quantitative research across single assets, multiple assets, daily data, and intraday data including 4H and 1H datasets. The system separates data ingestion, configuration, execution, strategy generation, analytics, validation, and experiment orchestration.

---

## 1. High-Level Architecture

```text
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

```text
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

The multi-asset path follows the same principle but uses multi-symbol data preparation, cross-sectional signals, `MultiAssetBacktestEngine`, and multi-asset analytics.

---

# 2. Layered Components

## 2.1 Data Layer

### `engine/data.py`

Primary single-file OHLCV ingestion and integrity layer.

Responsibilities:

- Load a CSV into a pandas DataFrame.
- Normalize column names and supported aliases.
- Parse the `date` column into the index.
- Sort chronologically.
- Remove duplicate timestamps.
- Validate OHLC relationships.
- Validate non-negative volume.
- Drop rows with required-column NaNs.
- Cache cleaned data as Parquet.
- Produce a deterministic SHA-256 data fingerprint.

Current production contract requires:

```text
open
high
low
close
volume
```

The active aliases include `date`, `datetime`, `timestamp`, `vol`, and `adj close`. A historical NIFTY/OHLC-only implementation remains as commented code and is not the active path.

### `engine/multi_data.py`

Multi-symbol data preparation layer.

Responsibilities:

- Discover symbols from CSV files.
- Load multiple single-asset datasets.
- Determine a common/union index.
- Align symbols to a shared timeline.
- Prepare the data structure expected by the multi-asset engine.

The current design deliberately uses a **union of timestamps** so that a missing market session for one asset does not remove the entire timestamp from the universe.

A current research concern is the distinction between a forward-filled price used for portfolio valuation and a genuinely tradable bar. The implementation currently forward-fills OHLC for alignment and sets missing volume to zero, so this behavior must remain an explicit research consideration and should be strengthened with a tradability/session model in a future refinement.

### Data layout

```text
 data/raw/daily/       daily CSV datasets
 data/raw/fourhours/   4H datasets
 data/raw/onehours/    1H datasets
 data/raw/daily_mc/    legacy/MC-oriented daily dataset collection
 data/cache/           Parquet caches
```

---

## 2.2 Configuration Layer

### `engine/config.py`

Pydantic-based configuration and experiment overlay system.

Single-asset configuration contains models for:

- `DataConfig`
- `EngineConfig`
- `StrategyConfig`
- `MonteCarloConfig`
- `OutputConfig`
- `AppConfig`

Multi-asset configuration adds:

- `MultiDataConfig`
- `XSMomentumConfig`
- `MultiAssetAppConfig`

The loader supports:

```text
base YAML
   +
experiment overlay
   -> deep merge
   -> Pydantic validation
   -> typed configuration
```

Configuration hashes are generated deterministically for reproducibility. A separate multi-asset hash function also exists.

### Configuration layout

```text
configs/
├── base.yaml
└── experiments/
    ├── gold_abs_momentum.yaml
    ├── gold_goldencross.yaml
    ├── xs_momentum_14assets.yaml
    └── xs_momentum_daily.yaml
```

`configs/base.yaml` currently defines the general XAUUSD daily defaults, execution costs, Monte Carlo defaults, and output configuration. fileciteturn22file0L1-L31

The experiment configurations override the base configuration for specific research hypotheses such as Gold Absolute Momentum and Gold Golden Cross. fileciteturn22file1L1-L11 fileciteturn22file2L1-L11

---

## 2.3 Run Context and Reproducibility

### `engine/run_context.py`

`RunContext` is the reproducibility/artifact boundary for canonical runs.

It creates a unique run directory and writes `manifest.json` containing run metadata including:

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

```text
manifest.json
equity.csv
fills.csv
trades.csv
metrics.json
monte_carlo.json
```

The run-context tests verify manifest creation, config hash persistence, data hash persistence, result persistence, completion timestamp, and unique run IDs.

---

# 3. Engine Layer

## 3.1 Single-Asset Engine

### `engine/core.py`

`BacktestEngine` is the core event-driven single-asset execution engine.

### Execution invariant

```text
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

When the target is exactly flat, the engine sells the exact current position so floating-point dust cannot create a phantom sign flip.

The current tests explicitly cover next-bar execution, last-bar non-execution, long/short accounting, transaction costs, exact flat exits, deterministic results, and fill structure. fileciteturn18file3L2-L9 fileciteturn18file3L99-L128 fileciteturn18file3L198-L222

Warmup support suppresses early signals and is regression-tested. fileciteturn19file0L6-L30

## 3.2 Multi-Asset Engine

### `engine/multi_core.py`

`MultiAssetBacktestEngine` and `MultiAssetPortfolio` extend the execution model to multiple symbols with shared cash and per-symbol positions/fills.

The engine:

- accepts symbol-keyed DataFrames
- accepts a date × symbol target-weight matrix
- processes the union of symbol timestamps
- supports warmup
- supports short restrictions
- supports no-trade bands
- records symbol-aware fills
- maintains per-symbol positions within one portfolio

The multi-asset tests cover construction, equal-weight exposure, flat portfolios, shorts, exact flattening, costs, determinism, `allow_short=False`, and symbol-aware fills. fileciteturn20file1L48-L75 fileciteturn20file1L78-L105 fileciteturn20file1L107-L145 fileciteturn20file1L148-L190

A research issue remains around missing-symbol sessions and tradability after multi-symbol alignment.

---

# 4. Strategy Layer

## 4.1 Strategy Contract

### `engine/loader.py`

Strategies are dynamically loaded from Python modules and must define:

```python
def generate_signals(df):
    ...
```

The loader validates:

- file existence
- `.py` extension
- importability
- presence of `generate_signals`
- callable function
- pandas Series return type
- equal length to data
- exact index match
- numeric dtype
- values constrained to `[-1, +1]`
- NaN conversion to zero

The loader tests cover the major failure and acceptance paths. fileciteturn19file2L14-L43 fileciteturn19file2L47-L106

## 4.2 Shared Indicators

### `strategies/indicators/indicators.py`

The shared indicator library currently contains:

```text
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

The implementations use standard rolling/EMA formulations, with Wilder-style smoothing for RSI and ATR. fileciteturn17file0L6-L23 fileciteturn17file0L26-L40 fileciteturn17file0L42-L62

## 4.3 Classic Strategy Files

The current source tree contains:

```text
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
xs_momentum.py
```

Historical/experimental strategies also exist in compiled artifacts and research history, including Donchian/ADX and Orion-style variants. Those are not all active source files in the current tree.

## 4.4 Cross-Sectional Momentum

### `strategies/xs_momentum.py`

The cross-sectional momentum generator ranks symbols by historical return while skipping a recent period, then constructs target weights for the strongest symbols and optionally the weakest symbols.

Current defaults:

```text
lookback       = 252
skip           = 21
top_k          = 3
bottom_k       = 3
rebalance      = monthly
offset         = long/short
 gross exposure = 1.0
```

The implementation keeps weights fixed between rebalances using forward filling. fileciteturn17file1L14-L34 fileciteturn17file1L36-L40 fileciteturn17file1L41-L51 fileciteturn17file1L63-L80

The tests verify long/short counts, long-only behavior, gross exposure normalization, and warmup behavior. fileciteturn21file1L8-L25 fileciteturn21file1L44-L71

---

# 5. Analytics Layer

## `analytics/metrics.py`

The analytics layer computes portfolio-level and trade-level diagnostics.

Current metric families include:

```text
Returns
- total return
- CAGR
- number of periods
- years

Risk
- volatility
- downside deviation
- maximum drawdown
- average drawdown
- drawdown duration

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

The analytics layer has explicit support for elapsed calendar years when a datetime index is available. Calendar-aware CAGR was introduced and has dedicated tests. fileciteturn19file1L6-L20

Trade extraction supports flat-to-position, position-to-flat, directional flips, same-direction scale-ins, and floating-point tolerance. The resulting trade record contains entry/exit information, direction, quantity, PnL, and commissions.

A remaining design issue is that `TRADING_DAYS = 252` is still the default API value. Callers must supply the appropriate annualization for intraday research; future architecture should make accidental 252-based annualization harder.

---

# 6. Validation Layer

## `validation/monte_carlo.py`

Current validation primitives include:

```text
bootstrap_returns_iid
bootstrap_returns_block
bootstrap_returns_under_null
bootstrap_trades
bootstrap_trades_block
signal_block_shuffle
same_exposure_benchmark_cost_adjusted
```

The validation layer is intended to distinguish observed strategy performance from return-distribution noise, trade-order effects, and signal-timing effects.

The null bootstrap centers returns under a zero-skill null and estimates a Sharpe distribution/p-value. The signal block shuffle attempts to preserve signal structure while breaking price alignment.

The test suite covers determinism, null centering, p-value bounds, null Sharpe standard-error sanity, confidence-interval ordering, trade minimum-sample behavior, and cost-adjusted benchmark behavior. fileciteturn20file3L30-L60 fileciteturn20file3L64-L91 fileciteturn20file0L9-L46

### Current validation concerns

The Monte Carlo layer still contains legacy assumptions that need refinement:

1. Some MC Sharpe calculations use a 252 annualization factor even when the primary analytics layer has been made timeframe-aware.
2. Trade bootstrap code contains a hard-coded approximately 21.6-year span assumption.
3. Some validation functions construct `BacktestEngine` with hard-coded/default cost assumptions instead of receiving the experiment's configured costs.
4. Some MC calls invoke `compute_metrics()` without forwarding the original `periods_per_year` and elapsed-year context.

These are implementation consistency issues, not evidence that the tests are failing.

---

# 7. Execution / Experiment Layer

## Canonical execution paths

### `execute/run_from_config.py`

The primary config-driven single-asset pipeline.

Intended flow:

```text
config
 -> RunContext
 -> load data
 -> cache/hash
 -> load strategy
 -> validate signals
 -> BacktestEngine
 -> trades
 -> metrics
 -> MC
 -> artifacts + manifest
```

It uses configured engine costs and warmup values, and records the data hash in the run context.

### `execute/run_multi_from_config.py`

The primary multi-asset pipeline.

It performs:

```text
discovery
 -> multi-data preparation
 -> XS momentum signal generation
 -> MultiAssetBacktestEngine
 -> equal-weight benchmark
 -> multi-asset trade extraction
 -> exposure/turnover analytics
 -> metrics
 -> manifest
```

The runner has a benchmark implementation, but the current equal-weight benchmark is not yet cost-adjusted in the same way as the dedicated cost-adjusted benchmark primitive.

### Exploratory / legacy execution tooling

The repository also contains:

```text
execute/execute_all.py
execute/execute_runner.py
execute/execute_montecarlo.py
execute/screen_all_assets.py
execute/golden_cross_sweep.py
execute/golden_cross_sweep_fast.py
execute/mc_targeted.py
execute/researcher_workflow.py
```

These represent accumulated research tooling. They are useful for exploration, historical experiments, and parameter searches, but they are not all equivalent to the canonical config-driven architecture.

---

# 8. Golden Cross Research Infrastructure

Two sweep generations exist.

## Full sweep

`execute/golden_cross_sweep.py` performs a structured grid in which every parameter combination is run through the actual `BacktestEngine`. It evaluates:

- fast SMA periods
- slow SMA periods
- long-only vs long/short
- confirmation filters
- crossover buffers

It uses timeframe-aware `periods_per_year` and elapsed-year calculations for reporting. fileciteturn23file3L49-L94 fileciteturn23file3L365-L378

## Fast sweep

`execute/golden_cross_sweep_fast.py` was created because the full sweep became computationally expensive.

Its architecture is:

```text
all parameter combinations
        |
        v
vectorized signal / return screening
        |
        v
rank candidates
        |
        v
send only top candidates
        |
        v
full BacktestEngine validation
```

It precomputes requested SMA series once and treats Stage 1 as a **screening model only**, not the final backtest truth. fileciteturn24file5L914-L975

The current fast sweep uses a candidate cutoff of 10 and rejects first-stage candidates with fewer than 10 approximate events. fileciteturn24file8L1430-L1441

The results are saved per dataset and also into a master sweep CSV. fileciteturn24file3L547-L677

---

# 9. Testing Architecture

The repository contains a substantial pytest suite with generated deterministic fixtures.

Current test categories include:

```text
test_config.py
test_data.py
test_engine.py
test_engine_warmup.py
test_loader.py
test_metrics.py
test_metrics_cagr.py
test_montecarlo.py
test_montecarlo_cost_adj.py
test_multi_engine.py
test_run_context.py
test_xs_momentum.py
```

### Test fixture system

`tests/fixtures/generate.py` creates deterministic fixture files:

```text
valid_ohlc.csv
bad_ohlc.csv
dupes.csv
missing_column.csv
```

The fixture generator is idempotent and can be invoked directly or automatically through `conftest.py`. fileciteturn21file2L20-L30 fileciteturn21file2L34-L51 fileciteturn21file2L55-L82 fileciteturn21file2L85-L95

### Core invariants under test

```text
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
```

---

# 10. Results and Artifact Layout

Current output locations include:

```text
results/
├── golden_cross_daily_*.csv
├── golden_cross_fast_fourhours_*.csv
├── golden_cross_fast_onehours_*.csv
├── golden_cross_sweep_fast.csv
├── screen_all_assets.csv
├── monte_carlo/
├── mc_targeted/
└── runs/
```

Canonical `RunContext` runs are stored under:

```text
results/runs/<run_id>/
```

with manifest and analysis artifacts.

Golden Cross research outputs are stored separately as sweep results rather than being treated as ordinary production runs.

---

# 11. Architecture Invariants

These are the most important behavioral invariants currently established by implementation and/or tests.

## Execution

1. Signals are interpreted from the close of bar `t`.
2. The resulting target is executed at the open of bar `t+1`.
3. The final bar cannot execute a signal because no next bar exists.
4. Flat targets close exactly the current position.
5. Slippage moves execution price against the trade.
6. Commission is charged on executed notional.

## Strategy contract

1. Strategies expose `generate_signals(df)`.
2. The returned signal object is a pandas Series.
3. Its index exactly matches the input data.
4. Values must be numeric and lie in `[-1, +1]`.

## Reproducibility

1. Configuration is schema-validated.
2. Configuration hashes are deterministic.
3. Data hashes are deterministic.
4. RunContext stores a manifest containing run metadata and hashes.
5. Fixed-seed Monte Carlo operations are deterministic.

## Research methodology

1. Screening results are not treated as final engine results.
2. Fast Golden Cross Stage 1 is explicitly approximate.
3. Stage 2 uses the real execution engine.
4. Low-sample candidates require caution.
5. Monte Carlo and benchmark comparisons are used as validation layers rather than optimization objectives.

---

# 12. Current Architecture Gaps

These are known gaps identified from the actual code review.

### High priority

- Propagate timeframe/calendar-aware annualization consistently into all Monte Carlo functions and their tests.
- Remove hard-coded trade-bootstrap elapsed-year assumptions.
- Make experiment strategy parameters from YAML actually reach strategy functions in the canonical single-asset runner.
- Ensure multi-asset run manifests contain a data hash representing the complete input universe.
- Make benchmark cost treatment consistent and explicit across single-asset and multi-asset pipelines.
- Distinguish missing data/session gaps from synthetic forward-filled prices that should not be tradable.

### Medium priority

- Make `periods_per_year=252` harder to misuse.
- Consolidate execution costs and other runtime assumptions under configuration instead of hardcoded exploratory defaults.
- Tighten tests that currently assert broad `Exception` instead of the intended error class.
- Add intraday/timezone-specific loader and annualization tests.
- Add multi-asset asynchronous-session/tradability tests.
- Clarify canonical versus legacy execution scripts.

### Research roadmap

Deferred until the foundation is stable:

- White's Reality Check
- Walk-forward validation
- Purged cross-validation
- Deflated Sharpe
- Optuna / systematic hyperparameter optimization
- Larger cross-sectional momentum universes
- Long/short attribution
- Per-symbol multi-asset trade metrics

---

# 13. Environment

Current project environment:

```text
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

The project is intended to be run from the repository root using the project environment.

---

# 14. Architectural Status

The codebase has evolved from a single-asset backtesting prototype into a multi-layer research framework.

The core architectural split is now:

```text
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

- strategies produce **target signals/weights**;
- engines handle **execution and portfolio accounting**;
- analytics measure **performance**;
- validation tests whether the observed performance is plausibly attributable to skill rather than noise;
- configuration and run context preserve **reproducibility**.

The repository is not yet fully research-grade in every dimension, but the core architecture and regression-test foundation are substantially established.
