<div align="center">

# ⚡ QuantForge

### Research-Grade Backtesting Framework with Complete Statistical Validation

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Tests-146_passing-00C851?style=for-the-badge" alt="Tests">
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Status-Production-success?style=for-the-badge" alt="Status">
</p>

<p align="center">
  <strong>Event-driven • Multi-asset • Walk-forward validated • Statistically rigorous</strong>
</p>

---

### 🎯 What is QuantForge?

QuantForge is a **research-oriented quantitative backtesting framework** designed to separate signal from noise in trading strategy research. Built to prevent the common pitfalls of overfitting, data snooping, and look-ahead bias, it provides a complete validation stack that distinguishes skill-based strategies from random chance.

</div>

---

## ✨ Key Features

<table>
<tr>
<td width="50%">

### 🏗️ **Core Architecture**
- **Event-driven execution engine** with next-bar semantics
- **Single-asset & multi-asset** portfolio support
- **Cross-sectional strategies** with weight-based signals
- **Transaction costs** (commission + slippage)
- **Warmup periods** for indicator initialization
- **Exact position flattening** (no floating-point dust)

</td>
<td width="50%">

### 📊 **Analytics Layer**
- **Performance metrics**: CAGR, Sharpe, Sortino, Calmar
- **Risk metrics**: Volatility, drawdowns, VaR, CVaR
- **Distribution analysis**: Skew, kurtosis, tail risk
- **Trade-level analytics**: Win rate, profit factor, expectancy
- **Timeframe-agnostic** (daily, 4H, 1H auto-detection)

</td>
</tr>
<tr>
<td width="50%">

### 🔬 **Validation Stack**
- **Monte Carlo simulation** (6 variants: IID, block, null, trade, signal-shuffle)
- **Walk-forward validation** with benchmark comparison
- **White's Reality Check** for multiple-testing correction
- **Same-exposure benchmark** (honest performance attribution)
- **Chained OOS equity** for low-turnover strategies

</td>
<td width="50%">

### ⚙️ **Research Infrastructure**
- **Typed YAML configuration** with Pydantic validation
- **Run manifests** for reproducibility
- **Data fingerprinting** (SHA-256 hashing)
- **Git integration** for version tracking
- **Canonical artifact structure**
- **146 passing tests** with full regression coverage

</td>
</tr>
</table>

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/Abhidev-aiml/quantforge-v0.git
cd quantforge-v0

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run Your First Backtest

```bash
# Run a single-asset backtest from config
python -m execute.run_from_config configs/experiments/gold_goldencross.yaml

# Run walk-forward validation
python -m execute.run_walk_forward configs/experiments/gold_goldencross_wf.yaml

# Run White's Reality Check across strategy universe
python -m execute.run_whites_rc
```

### Verify Installation

```bash
# Run the full test suite (should show 146 passing)
python -m pytest -v
```

---

## 📐 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        QuantForge Pipeline                       │
└─────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
            ┌───────▼────────┐       ┌───────▼────────┐
            │  Data Layer    │       │  Config Layer   │
            │  • OHLCV load  │       │  • YAML schema  │
            │  • Validation  │       │  • Type safety  │
            │  • Hashing     │       │  • Versioning   │
            └───────┬────────┘       └───────┬────────┘
                    │                         │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Strategy Layer        │
                    │   • Signal generation   │
                    │   • Contract validation │
                    │   • Parameter wiring    │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Engine Layer          │
                    │   • Event-driven exec   │
                    │   • Single/multi-asset  │
                    │   • Cost accounting     │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Analytics Layer       │
                    │   • Performance metrics │
                    │   • Trade extraction    │
                    │   • Risk measurement    │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Validation Layer      │
                    │   • Monte Carlo         │
                    │   • Walk-forward        │
                    │   • White's RC          │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Reporting Layer       │
                    │   • HTML tearsheets     │
                    │   • Interactive charts  │
                    │   • Result artifacts    │
                    └─────────────────────────┘
```

---

## 📚 Project Structure

```
quantforge-v0/
├── analytics/           # Performance metrics and trade analytics
├── configs/             # YAML configuration files
│   ├── base.yaml
│   └── experiments/     # Strategy-specific configs
├── data/
│   ├── raw/             # Market data CSVs (daily, 4H, 1H)
│   └── cache/           # Parquet caches
├── docs/                # Architecture and milestone documentation
│   ├── architecture.md
│   ├── state.md
│   └── milestones/
├── engine/              # Core backtesting engine
│   ├── core.py          # Single-asset engine
│   ├── multi_core.py    # Multi-asset portfolio engine
│   ├── config.py        # Configuration schema
│   ├── data.py          # Data loading & validation
│   ├── loader.py        # Strategy loading
│   └── run_context.py   # Reproducibility layer
├── execute/             # Execution scripts
│   ├── run_from_config.py
│   ├── run_walk_forward.py
│   ├── run_whites_rc.py
│   └── ...sweeps
├── reporting/           # HTML tearsheet generation
│   ├── engine.py
│   ├── tearsheet.py
│   ├── charts/
│   └── templates/
├── strategies/          # Strategy implementations
│   ├── 01_goldencross.py
│   ├── 02_emacross.py
│   ├── xs_momentum.py   # Cross-sectional momentum
│   └── indicators/
├── tests/               # 146 passing tests
├── validation/          # Statistical validation modules
│   ├── monte_carlo.py
│   ├── walk_forward.py
│   └── whites_reality_check.py
└── results/
    └── runs/            # Canonical run artifacts
```

---

## 🎓 Core Concepts

### Execution Semantics

QuantForge follows strict **next-bar execution**:

```
Bar t close → Generate signal → Queue target → Execute at bar t+1 open
```

- **Signal lag**: Signals from bar `t` execute at bar `t+1` open
- **Transaction costs**: Directional slippage + commission on notional
- **No look-ahead**: Future data never influences past decisions
- **Deterministic**: Same inputs → same outputs (fixed seed)

### Strategy Contract

Strategies implement a simple interface:

```python
def generate_signals(df: pd.DataFrame, params: dict = None) -> pd.Series:
    """
    Generate target position weights from OHLCV data.
    
    Returns:
        pd.Series with index matching df.index
        Values in [-1, +1] where:
            +1 = full long
             0 = flat
            -1 = full short
    """
    # Your strategy logic here
    return signals
```

### Configuration-Driven

Define experiments in YAML:

```yaml
data:
  path: data/raw/daily/xauusd_1D_comma.csv
  symbol: XAUUSD
  start: "2020-01-01"

engine:
  initial_cash: 100000
  commission_bps: 1.0
  slippage_bps: 5.0
  warmup_bars: 200

strategy:
  path: strategies/01_goldencross.py
  params:
    fast: 50
    slow: 200

monte_carlo:
  enabled: true
  n_simulations: 5000
  method: block
```

---

## 🔬 Validation Methodology

### 1. Monte Carlo Simulation

Test whether observed performance could be attributed to random chance:

- **IID bootstrap**: Resample daily returns with replacement
- **Block bootstrap**: Preserve autocorrelation structure
- **Null bootstrap**: Test against zero-mean hypothesis
- **Trade-level**: Bootstrap round-trip trades
- **Signal shuffle**: Randomize entry/exit timing

**Verdict**: `p-value < 0.05` suggests skill-based performance

### 2. Walk-Forward Validation

Rolling in-sample optimization with out-of-sample testing:

```
[---- Train ----][-- Test --]
    [---- Train ----][-- Test --]
        [---- Train ----][-- Test --]
```

- **No look-ahead**: OOS window never used for parameter selection
- **Benchmark comparison**: Same-exposure passive holding
- **Degradation ratio**: OOS Sharpe / IS Sharpe
- **Chained OOS equity**: Concatenated OOS periods for statistical power

**Verdicts**:
- **Robust**: Degradation ratio ≥ 0.5, mean OOS Sharpe > 0
- **Has edge**: Chained OOS excess Sharpe > 0.20

### 3. White's Reality Check

Multiple-testing correction for data-snooping bias:

- **Problem**: Testing 100 strategies gives ~99% chance of false positive
- **Solution**: Stationary block bootstrap across (T, K) excess-return matrix
- **Test statistic**: `V = sqrt(T) · max_k(mean(excess_k))`
- **p-value**: Probability best combo is due to chance

**Verdict**: Corrects for universe-wide data mining

---

## 📊 Example Results

### Single-Asset Backtest

```python
from engine.config import load_config
from engine.run_context import RunContext
from execute.run_from_config import run_single_asset_from_config

# Load configuration
config = load_config("configs/experiments/gold_goldencross.yaml")

# Create run context for reproducibility
ctx = RunContext(config)

# Execute backtest
results = run_single_asset_from_config(config, ctx)

# Results saved to: results/runs/<run_id>/
# - manifest.json
# - equity.csv
# - trades.csv
# - metrics.json
# - monte_carlo.json
```

### Walk-Forward Validation

```python
from execute.run_walk_forward import run_walk_forward_from_config

# Run walk-forward validation
wf_results = run_walk_forward_from_config(
    "configs/experiments/gold_goldencross_wf.yaml"
)

print(f"Mean IS Sharpe: {wf_results['mean_is_sharpe']:.3f}")
print(f"Mean OOS Sharpe: {wf_results['mean_oos_sharpe']:.3f}")
print(f"Degradation Ratio: {wf_results['degradation_ratio']:.3f}")
print(f"Robust: {wf_results['robust']}")
print(f"Has Edge: {wf_results['has_edge']}")
```

---

## 🧪 Testing

QuantForge maintains **146 passing tests** with full regression coverage:

```bash
# Run all tests
python -m pytest -v

# Run specific test module
python -m pytest tests/test_engine.py -v

# Run with coverage
python -m pytest --cov=. --cov-report=html
```

### Test Coverage

- **Config layer**: Schema validation, run context
- **Data layer**: OHLCV validation, hashing
- **Engine layer**: Execution semantics, costs, determinism
- **Strategy layer**: Signal validation, parameter wiring
- **Analytics layer**: Metrics computation, trade extraction
- **Validation layer**: MC correctness, WF windows, WRC centering

---

## 🎯 Strategy Library

QuantForge includes 25+ strategies across multiple families:

### Trend Following
- `01_goldencross.py` - SMA/EMA crossover (5 variants)
- `02_emacross.py` - Exponential moving average cross
- `07_absolute_momentum.py` - Time-series momentum
- `15_trend_pullback_4h.py` - 4H trend + pullback entry

### Mean Reversion
- `03_rsi_meanrev.py` - RSI overbought/oversold
- `04_bollinger_meanrev.py` - Bollinger band extremes
- `09_zscore_meanrev.py` - Z-score reversion
- `24_vwap_reversion.py` - VWAP deviation

### Breakout
- `05_donchian_breakout.py` - Donchian channel breakout
- `08_atr_breakout.py` - ATR-based volatility breakout
- `17-23_ny_orb_*.py` - NY Opening Range Breakout (7 variants)

### Cross-Sectional
- `xs_momentum.py` - Relative strength ranking across universe

### Combined Indicators
- `25_bollinger_rsi_double.py` - Bollinger + RSI confirmation
- `25_vwap_refined.py` - Enhanced VWAP strategy

---

## 📈 Milestone Progress

QuantForge has completed **10 major milestones**:

| Milestone | Component | Status |
|-----------|-----------|--------|
| **M1** | Data Pipeline | ✅ Complete |
| **M2** | Core Backtesting Engine | ✅ Complete |
| **M3** | Strategy Contract | ✅ Complete |
| **M4** | Analytics & Metrics | ✅ Complete |
| **M5** | Monte Carlo Simulation | ✅ Complete |
| **M6** | Config System & Execution | ✅ Complete |
| **M7** | Multi-Asset Execution | ✅ Complete |
| **M8** | Walk-Forward Validation | ✅ Complete |
| **M9** | White's Reality Check | ✅ Complete |
| **M10** | Reporting & Tearsheet | ✅ Complete |

See `docs/milestones/` for detailed documentation of each milestone.

---

## 🔧 Configuration

### Engine Configuration

```yaml
engine:
  initial_cash: 100000      # Starting capital
  commission_bps: 1.0       # Commission in basis points
  slippage_bps: 5.0         # Slippage in basis points
  no_trade_band: 0.01       # Min weight change to trigger rebalance
  warmup_bars: 0            # Initial bars to skip (for indicators)
```

### Walk-Forward Configuration

```yaml
walk_forward:
  train_bars: 252           # In-sample window size (1 year daily)
  test_bars: 63             # Out-of-sample window size (3 months)
  step_bars: 21             # Step size between windows (1 month)
```

### Monte Carlo Configuration

```yaml
monte_carlo:
  enabled: true
  n_simulations: 5000       # Number of bootstrap iterations
  method: block             # bootstrap method: iid, block, null, trade
  seed: 42                  # Random seed for reproducibility
```

---

## 📖 Documentation

- **[Architecture](docs/architecture.md)** - System design and component responsibilities
- **[State](docs/state.md)** - Current project state and handoff guide
- **[Milestones](docs/milestones/)** - Detailed milestone completion reports
- **[Context](docs/context/)** - Strategy-specific documentation and references

---

## 🤝 Contributing

Contributions are welcome! Before contributing:

1. Read `docs/architecture.md` and `docs/state.md`
2. Run `pytest -v` to verify the test suite passes
3. Add regression tests for any engine semantic changes
4. Follow the existing code style and conventions

### Development Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature

# Make changes and add tests
# ...

# Run test suite
python -m pytest -v

# Commit with conventional commits
git commit -m "feat(engine): add new feature"

# Push and create PR
git push origin feature/your-feature
```

---

## 📊 Research Methodology Lessons

Key learnings from QuantForge development:

1. **Same-exposure benchmark is the honest test** - Equity-table Sharpe alone is misleading on trending assets
2. **Walk-forward doesn't catch beta** - A strategy can be robust and still have no edge
3. **RC corrects for cherry-picking** - Testing 143 combos means the best one is likely just luck
4. **Trade count per window matters** - Low-turnover strategies need chained OOS for statistical power
5. **Do not re-tune failed hypotheses** - Further parameter tweaks are data mining

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

QuantForge is built on the shoulders of giants:

- **pandas** & **numpy** - Data manipulation and numerical computing
- **scipy** - Statistical functions
- **pydantic** - Configuration validation
- **pytest** - Test framework

Research methodology inspired by:
- **Advances in Financial Machine Learning** by Marcos López de Prado
- **Evidence-Based Technical Analysis** by David Aronson
- **White's Reality Check** (2000) for multiple testing
- **Politis & Romano** (1994) stationary bootstrap

---

## 📞 Contact

- **GitHub**: [@Abhidev-aiml](https://github.com/Abhidev-aiml)
- **Repository**: [quantforge-v0](https://github.com/Abhidev-aiml/quantforge-v0)

---

<div align="center">

### ⚡ QuantForge - Built for Research Rigor

**[Documentation](docs/)** • **[Milestones](docs/milestones/)** • **[Architecture](docs/architecture.md)** • **[Issues](https://github.com/Abhidev-aiml/quantforge-v0/issues)**

</div>
