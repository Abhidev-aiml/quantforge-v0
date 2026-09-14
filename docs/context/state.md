# QuantForge Current State

## Document Purpose

This document is the **current-state handoff** for QuantForge. It is intended to be read by another AI coding/research agent before making changes so that the agent understands:

- what has actually been built;
- which milestones and tiers are complete;
- what has been tested;
- what research has already been attempted;
- which hypotheses were rejected;
- what remains technically unresolved;
- what should happen next.

This document reflects the repository reconstructed from the actual files reviewed in the current audit. Where the code contradicted the older architecture notes, the codebase was treated as the source of truth.

---

# 1. Current Project Position

QuantForge is no longer a simple backtesting script. It currently contains:

```text
Single-asset engine             ✅
Multi-asset engine              ✅
Data validation                 ✅
Config system                   ✅
Run manifests                  ✅
Strategy contract               ✅
Indicator library               ✅
Analytics layer                 ✅
Monte Carlo validation          ✅
Cost-adjusted benchmark        ✅
Cross-sectional momentum       ✅
Automated regression tests     ✅
Multi-timeframe research       ✅
Golden Cross parameter sweeps  ✅
```

The project is currently in the transition from:

> **working research framework**

toward:

> **research-grade, internally consistent research framework**.

The next work should therefore prioritize correctness, reproducibility, and validation consistency before adding large amounts of new strategy complexity.

---

# 2. Milestone / Tier Status

## Milestones 0–5

The project history and current implementation support the following completed milestone areas:

```text
Milestone 0 — project foundation        ✅
Milestone 1 — data pipeline             ✅
Milestone 2 — backtesting engine        ✅
Milestone 3 — strategy contract         ✅
Milestone 4 — analytics / metrics       ✅
Milestone 5 — validation / MC           ✅
```

The original milestone names have evolved during implementation, so the layer descriptions in `architecture.md` should be treated as more authoritative than old milestone wording.

## Tier 1

The intended Tier 1 objective was tests, configuration, and reproducible manifests.

Current state:

```text
pytest infrastructure          ✅
Config models                   ✅
YAML base + overlays            ✅
Deterministic config hashes     ✅
RunContext                      ✅
Manifest generation             ✅
Data hashes                     ✅ in single-asset path
Regression suite                ✅ substantial
```

The test tree contains 12 named test modules covering config, data, engine, warmup, loader, metrics, CAGR, Monte Carlo, cost-adjusted validation, multi-engine, run context, and cross-sectional momentum.

An earlier observed test run reported 64 passing tests. The project tree and subsequent additions suggest a larger current suite, but **the final current test count should be established by running `pytest -v` in the present repository rather than copying an older count**.

## Tier 2

The intended Tier 2 work has already begun and several components are implemented:

```text
Engine fixes                         ✅ largely implemented
Cost-adjusted benchmark             ✅ implemented
Warmup                              ✅ implemented
Calendar-aware CAGR                 ✅ implemented
Phantom-flip fix                    ✅ implemented
Scale-in support                    ✅ implemented
Block trade bootstrap               ✅ implemented
Multi-asset engine                  ✅ implemented
Multi-symbol data                   ✅ implemented
XS momentum                         ✅ implemented
Multi-asset run pipeline            ✅ implemented
```

The parts still unfinished or not yet robust enough are listed in the open-work section below.

---

# 3. Current Repository Structure

Important active directories:

```text
analytics/
configs/
data/
docs/
engine/
execute/
results/
scripts/
strategies/
tests/
validation/
```

Key production components:

```text
engine/core.py
engine/data.py
engine/loader.py
engine/config.py
engine/multi_core.py
engine/multi_data.py
engine/run_context.py

analytics/metrics.py
validation/monte_carlo.py

strategies/indicators/indicators.py
strategies/xs_momentum.py

execute/run_from_config.py
execute/run_multi_from_config.py
```

The repository also contains a collection of exploratory and historical research runners. These are useful but should not be assumed to be canonical merely because they exist in `execute/`.

---

# 4. Data State

## Data universes

Current data organization supports:

```text
data/raw/daily/
data/raw/fourhours/
data/raw/onehours/
data/raw/daily_mc/
```

The daily and intraday universes have included assets such as:

```text
BRENT
DAX / DEU index
EURUSD
GBPUSD
GBR index
US30
S&P 500
US Tech
USDCAD
USDCHF
USDJPY
XAGUSD
XAUUSD
```

The actual current file inventory should always be checked from the filesystem before claiming a precise asset count.

## Data loading

The production loader currently expects OHLCV and cleans/validates data before returning it. It can also cache a cleaned DataFrame as Parquet and generate a hash.

Deterministic fixture generation is implemented in `tests/fixtures/generate.py`, producing valid, invalid, duplicate-date, and missing-volume cases. fileciteturn21file2L20-L30 fileciteturn21file2L34-L51 fileciteturn21file2L55-L82

## Intraday state

Daily, 4H, and 1H datasets have all been used in research runs.

Timeframe-aware annualization was added using observed timestamps rather than blindly applying 252 periods/year. The current runner computes both:

```text
periods_per_year
elapsed_years
```

from the dataset timestamps.

This is a significant improvement, but it is still an **empirical observation-frequency approach**, not a complete exchange/session calendar model.

---

# 5. Engine State

## Single asset

The single-asset engine is event-driven and deterministic.

The canonical execution model is:

```text
bar t signal
   -> queued target
   -> bar t+1 open execution
   -> commission/slippage
   -> mark-to-market at close
```

The core tests explicitly protect this behavior. fileciteturn18file3L99-L128

The flat-target regression protects against the earlier floating-point phantom-flip bug. fileciteturn18file3L198-L222

Warmup support is implemented and tested. fileciteturn19file0L6-L30

## Multi asset

The multi-asset engine supports per-symbol positions and a shared portfolio cash balance. It has deterministic behavior and supports long-only constraints and short positions. fileciteturn20file1L48-L75 fileciteturn20file1L148-L190

### Current technical concern

The multi-symbol data layer forward-fills prices when aligning to a union index. The intent is to keep valuation continuous across differing market calendars, but the current design needs a stronger distinction between:

```text
"price exists for valuation"
vs
"asset is tradable at this timestamp"
```

This should be addressed before claiming the multi-asset engine is fully production/research grade.

---

# 6. Strategy State

## Strategy contract

Strategies must provide:

```python
def generate_signals(df):
    ...
```

and return a numeric pandas Series aligned exactly to the input index with values in `[-1, +1]`. NaNs are converted to zero during validation. fileciteturn19file2L49-L106

## Existing strategy families

The initial benchmark universe contains:

```text
Golden Cross
EMA Cross
RSI Mean Reversion
Bollinger Mean Reversion
Donchian Breakout
MACD Cross
Absolute Momentum
ATR Breakout
Z-score Mean Reversion
ROC Momentum
```

Additional experimental strategy files have included trend pullback, Donchian+ADX, and Orion-style formulations.

## Research outcomes so far

### Rejected / weak hypotheses

The research process tested and rejected several approaches as generally unconvincing in the tested configurations:

```text
Donchian + ADX refinements
Orion-style oscillator combinations
Trend-pullback multi-indicator formulations
Several generic FX applications of the baseline strategies
```

These should not be reintroduced merely because further parameter tuning might produce a visually attractive result. They were useful hypothesis tests and produced learning about the limitations of indicator combinations.

### Current strongest hypothesis

Golden Cross became the primary research candidate after systematic sweeps across assets and timeframes.

Observed patterns included:

- stronger performance in equity-index assets than in many FX assets;
- parameter neighborhoods rather than a single isolated optimum in several datasets;
- better results for long-only configurations in several equity/index datasets;
- strong but high-drawdown long/short behavior in some commodities such as Brent.

These are **in-sample historical findings**, not yet validated edges.

---

# 7. Golden Cross Research State

Two sweep systems exist.

## Full sweep

The full Golden Cross sweep runs every structured variant through the actual engine.

Parameters explored include:

```text
Fast SMA
Slow SMA
Long-only / Long-short
Confirmation filter
Crossover buffer
```

Filters include:

```text
none
price vs slow SMA
slow SMA slope
fast SMA slope
combined confirmation
```

## Fast sweep

The fast version was created because exhaustive engine calls were too slow.

Its architecture is:

```text
~2,960 structured variants / dataset
       ↓
vectorized Stage 1 screening
       ↓
ranked candidates
       ↓
Top-N full BacktestEngine validation
```

Stage 1 is explicitly an approximation and should never be treated as the final truth. The code states this directly and only Stage 2 uses the real engine. fileciteturn23file2L5-L22

The current fast script sends only 10 candidates to the full engine by default and filters out candidates with fewer than 10 approximate events. fileciteturn24file8L1437-L1441

### Important research caveat

Because only a subset of Stage 1 candidates reaches the true engine, the fast sweep does **not prove that the true engine's global top 10 has been found**. The screening approximation can filter out candidates that would score differently under exact execution.

For serious validation, use a broader finalist pool or a diversified selection such as:

```text
Top by Sharpe
Top by Calmar
Top by CAGR
Top by drawdown
```

then revalidate the combined candidate set through the actual engine.

---

# 8. Analytics State

Current analytics include:

```text
CAGR
volatility
Sharpe
Sortino
Calmar
VaR / CVaR
skew
kurtosis
max drawdown
drawdown duration
trade count
win rate
profit factor
expectancy
payoff ratio
trade percentage metrics
turnover
average gross exposure
average net exposure
```

Calendar-aware CAGR was explicitly added and tested. fileciteturn19file1L6-L20

Trade extraction handles reversals and floating-point tolerance.

### Remaining analytics concern

`metrics.py` still has a default `periods_per_year=252`. While callers can override it, this can silently produce incorrect annualized Sharpe/volatility/Sortino for intraday data if they forget to pass the correct factor.

The correct future architecture is to make timeframe/calendar context explicit and difficult to omit.

---

# 9. Validation State

Current Monte Carlo functionality includes:

```text
IID return bootstrap
Block return bootstrap
Null bootstrap
Trade bootstrap
Block trade bootstrap
Signal block shuffle
Cost-adjusted same-exposure benchmark
```

The tests verify deterministic seeded behavior, null centering, p-value validity, CI ordering, minimum trade requirements, and cost drag. fileciteturn20file3L30-L60 fileciteturn20file3L64-L91 fileciteturn20file0L9-L46

### Current validation weaknesses

The following are known and should be addressed:

```text
1. MC annualization is not consistently timeframe-aware.
2. Trade bootstrap contains a hard-coded ~21.6-year span assumption.
3. Some MC functions use hard-coded execution assumptions.
4. Some MC metric calls fall back to 252 annualization.
5. Signal block-shuffle and null-bootstrap paths need unified experiment-cost/timeframe parameters.
```

These should be fixed before adding White's Reality Check.

---

# 10. Reproducibility State

The run-context infrastructure is in place.

Each canonical run can have:

```text
run_id
started_utc
finished_utc
git_sha
git_dirty
config_hash
data_hash
config snapshot
results summary
```

Run IDs are unique and manifests are persisted and tested. fileciteturn20file2L28-L66

### Remaining reproducibility concern

The single-asset config runner records a data hash, while the multi-asset runner does not yet clearly compute/store a complete universe-level data hash. This needs to be standardized.

---

# 11. Current Configuration State

Base configuration currently defines:

```text
XAUUSD daily default data path
initial cash = 100,000
commission = 1 bp
slippage = 5 bp
no-trade band = 1%
warmup = 0
MC enabled
n_sims = 5,000
n_perm = 500
seed = 42
```

as documented in `configs/base.yaml`. fileciteturn22file0L1-L31

Experiment overlays currently cover:

```text
Gold Absolute Momentum
Gold Golden Cross
XS Momentum 14 assets
XS Momentum daily universe
```

The XS momentum 14-asset configuration explicitly uses 252 lookback, 21-bar skip, top/bottom 3 selection, monthly rebalancing, long/short enabled, 1.0 gross exposure, and 273 warmup bars. fileciteturn22file3L1-L30

The daily XS momentum configuration discovers `_comma.csv` files from `data/raw/daily/` and enables Monte Carlo. fileciteturn22file4L1-L33

---

# 12. Parameter / Strategy Configuration Gap

This is a confirmed architecture issue.

The configuration model supports:

```text
strategy.params: dict
```

but the canonical single-asset runner currently loads the strategy and invokes it as:

```python
fn(df)
```

rather than explicitly passing the configured strategy parameters.

This means the config layer currently advertises a parameter mechanism that is not fully wired into arbitrary strategy execution.

This should be fixed before parameterized strategy experiments are treated as reproducibly config-driven.

---

# 13. Benchmark State

There are currently multiple benchmark implementations.

### Cost-adjusted single-asset benchmark

The validation layer contains `same_exposure_benchmark_cost_adjusted`, and dedicated tests verify that adding costs lowers the benchmark equity and preserves exposure. fileciteturn20file0L9-L34

### Older benchmark implementations

Several legacy scripts still contain a simpler synthetic same-exposure benchmark that does not include the full strategy cost treatment.

### Multi-asset benchmark

The multi-asset execution runner currently uses an equal-weight benchmark implementation, but that benchmark is not yet fully cost-adjusted.

Therefore, whenever benchmark results are reported, the exact benchmark implementation must be stated.

---

# 14. Current Research Result: Cross-Sectional Momentum

The current multi-asset XS momentum experiment was run on a daily multi-asset universe.

The previously recorded result was:

```text
Strategy Sharpe       0.324
Benchmark Sharpe      0.609
Excess Sharpe        -0.285
Null MC p-value       0.066
Trades                  111
Profit factor          1.485
```

Interpretation:

```text
Observed strategy performance exists,
but it did not beat the same broad benchmark,
and the null p-value was only marginal rather than conventionally significant.
```

The current unresolved questions are:

- Is 12–14 assets too small for robust cross-sectional momentum?
- Is the long/short leg inappropriate during a historically bullish sample?
- Does the strategy need a larger universe?
- Is timing skill present but weak enough that it is overwhelmed by beta/benchmark exposure?
- Does portfolio timing need a dedicated null test?

Do not treat the current XS result as a validated edge.

---

# 15. Research Process Lessons Already Established

Several useful process decisions have emerged.

## Do not blindly optimize bad hypotheses

Donchian/ADX, Orion-style, and trend-pullback experiments were allowed to fail rather than being tuned until a favorable historical result appeared.

## Separate screening from validation

The Golden Cross fast sweep clearly distinguishes approximate screening from exact engine validation. fileciteturn23file2L5-L22

## Treat parameter neighborhoods as more interesting than isolated winners

A cluster of nearby parameters that produces similar performance is more credible than a single sharp optimum.

## Do not confuse more trades with more edge

Moving from Daily to 4H/1H increased sample counts but did not automatically improve performance.

## Execution assumptions matter

The project has repeatedly encountered issues caused by mismatches between theoretical signal logic and actual next-bar execution.

---

# 16. Current Test State

Tests reviewed so far cover:

```text
Config
Data
Engine
Warmup
Loader
Metrics
CAGR
Monte Carlo
Cost-adjusted benchmark
RunContext
Multi-asset engine
XS momentum
Fixture generation
```

Specific established tests include:

- exact next-bar execution; fileciteturn18file3L114-L128
- final-bar signal does not execute; fileciteturn18file3L101-L110
- exact flattening; fileciteturn18file3L134-L147
- warmup suppression; fileciteturn19file0L6-L20
- strategy contract failures; fileciteturn19file2L14-L43
- analytical Sharpe and drawdown; fileciteturn19file3L49-L75
- calendar CAGR; fileciteturn19file1L6-L20
- deterministic MC behavior; fileciteturn20file3L30-L60
- cost-adjusted benchmark; fileciteturn20file0L9-L46
- manifest persistence; fileciteturn20file2L28-L66
- multi-asset execution behavior; fileciteturn20file1L58-L104
- XS momentum weight construction; fileciteturn21file1L8-L25

The current exact suite count should be obtained with a fresh `pytest -v` run before putting a number into any future report.

---

# 17. High-Priority Technical Fix List

Before adding more advanced research methods, the following should be completed.

### P0 — consistency / correctness

```text
1. Make annualization/timeframe context consistent across:
   metrics.py
   monte_carlo.py
   execute runners
   MC tests

2. Remove the hard-coded trade-bootstrap 21.6-year assumption.

3. Wire strategy.params from YAML into canonical strategy execution.

4. Add a complete multi-asset data hash to RunContext manifests.

5. Make benchmark cost treatment explicit and consistent.

6. Resolve tradability semantics for union-index multi-asset alignment.
```

### P1 — testing hardening

```text
7. Add 1H/4H timezone and timestamp-format tests.
8. Add asynchronous-session multi-asset tests.
9. Tighten broad exception assertions.
10. Add MC tests that explicitly verify timeframe-aware annualization.
11. Add config-to-strategy parameter propagation tests.
```

### P2 — cleanup

```text
12. Classify or retire legacy execute scripts.
13. Remove large commented historical implementations from production files.
14. Standardize experiment configuration rather than hardcoding costs in research utilities.
15. Establish one canonical benchmark API.
```

---

# 18. Deferred Research Roadmap

Do **not** jump directly into all of these after seeing promising backtest numbers.

Preferred order:

```text
Foundation hardening
        ↓
MC consistency
        ↓
Benchmark consistency
        ↓
Golden Cross focused robustness
        ↓
Out-of-sample validation
        ↓
Walk-forward validation
        ↓
White's Reality Check
        ↓
Deflated Sharpe
        ↓
Purged CV
        ↓
Optuna / systematic optimization
```

Cross-sectional momentum expansion can proceed in parallel only after the multi-asset data/tradability semantics are sufficiently reliable.

---

# 19. Immediate Next Session Plan

The next session should begin with **refining and leveling up the completed milestones**, not with a new strategy invention.

Recommended sequence:

## Step 1 — Baseline verification

Run:

```bash
pytest -v
```

Record the exact current count and execution time.

## Step 2 — Audit the six highest-priority issues

Start with:

```text
MC annualization
trade bootstrap elapsed years
strategy parameter wiring
multi-asset data hash
benchmark cost adjustment
missing-bar tradability
```

## Step 3 — Add regression tests before fixes

For each issue:

```text
write failing / target regression test
        ↓
make smallest implementation change
        ↓
pytest
        ↓
review
```

## Step 4 — Re-run representative research

After the foundation is stable:

```text
Golden Cross candidate
XS momentum
same-exposure benchmark
Monte Carlo
```

## Step 5 — Lock the research contract

Only after the above is stable should the project proceed into more advanced multiple-testing and out-of-sample methodology.

---

# 20. Handoff Rules for Another AI Agent

Before modifying QuantForge:

1. Read `docs/architecture.md` and this file.
2. Treat the actual repository code as the authority if documentation and implementation diverge.
3. Read relevant tests before changing implementation.
4. Do not optimize a strategy before checking execution semantics and statistical validation.
5. Do not treat a parameter-sweep winner as a validated edge.
6. Keep screening and exact-engine validation conceptually separate.
7. Test after every isolated change.
8. Stop and fix failures instead of accumulating unverified modifications.
9. Preserve reproducibility metadata for research runs.
10. Keep later-stage methods such as White's Reality Check, walk-forward, purged CV, and Deflated Sharpe behind a stable foundation.

---

# 21. Current Status Summary

```text
                    QuantForge
                         |
       +-----------------+------------------+
       |                 |                  |
       v                 v                  v
    Foundation        Research            Validation
       |                 |                  |
       v                 v                  v
 Data / Engine       Golden Cross       Monte Carlo
 Config / Tests      XS Momentum        Benchmarking
       |                 |                  |
       +-----------------+------------------+
                         |
                         v
              RESEARCH-GRADE HARDENING
                         |
             +-----------+-----------+
             |           |           |
             v           v           v
         Consistency  OOS / WF   Multiple-testing
```

### Overall status

```text
Core framework                  🟢 Strong
Regression coverage             🟢 Strong baseline
Multi-asset capability          🟢 Working
Configuration                   🟢 Working
Reproducibility                 🟢 Working, multi-asset needs completion
Analytics                       🟢 Broad coverage
Monte Carlo                     🟡 Needs consistency hardening
Benchmarking                    🟡 Multiple implementations need unification
Intraday research               🟢 Working
Calendar/session modeling       🟡 Needs refinement
Strategy research               🟢 Active
Golden Cross                    ⭐ Main current hypothesis
XS momentum                     🟡 Interesting but not validated
White's Reality Check           ⏳ Not implemented
Walk-forward                    ⏳ Not implemented
Purged CV                       ⏳ Deferred
Deflated Sharpe                 ⏳ Deferred
Optuna                          ⏳ Deferred
```

The project is at the point where **hardening the research infrastructure is more valuable than adding another ten indicators**.
