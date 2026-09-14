# VWAP Strategy Implementation Workflow

Complete phase-by-phase guide for adding, testing, and validating a new trading strategy in QuantForge.

---

## Phase 1: Implement the Strategy

### 1.1 Create the Strategy File

Create `strategies/24_vwap_reversion.py`:

```python
"""24 — VWAP Mean Reversion

Entry: price closes > 1.5% above VWAP → short
       price closes > 1.5% below VWAP → long
Exit: mean reversion back to VWAP
"""
import pandas as pd

def generate_signals(df, params=None):
    """Generate VWAP mean reversion signals."""
    params = params or {}
    threshold = params.get("threshold", 0.015)  # 1.5%
    
    # Calculate VWAP
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    vwap = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()
    
    # Calculate deviation from VWAP
    deviation = (df["close"] - vwap) / vwap
    
    # Generate signals
    signals = pd.Series(0.0, index=df.index)
    signals[deviation > threshold] = -1.0   # Short when above VWAP
    signals[deviation < -threshold] = 1.0   # Long when below VWAP
    
    return signals
```

### 1.2 Create Config File

Create `configs/experiments/gold_vwap.yaml`:

```yaml
data:
  path: data/raw/daily/xauusd_1D_comma.csv
  symbol: XAUUSD

strategy:
  path: strategies/24_vwap_reversion.py
  params:
    threshold: 0.015

engine:
  initial_cash: 100000.0
  commission_bps: 1.0
  slippage_bps: 5.0
  no_trade_band: 0.01
  warmup_bars: 0

monte_carlo:
  enabled: true
  n_sims: 5000
  seed: 42

output:
  results_dir: results
  save_manifest: true
```

**Checkpoint:** ✓ Two files created. Move to Phase 2.

---

## Phase 2: Validate the Strategy Contract

### 2.1 Test Strategy Loading

```bash
python -c "
from engine.loader import load_strategy
fn = load_strategy('strategies/24_vwap_reversion.py')
print('✅ Strategy loads successfully')
print(f'Function: {fn.__name__}')
"
```

**Expected output:**
```
✅ Strategy loads successfully
Function: generate_signals
```

### 2.2 Test Signal Generation

```bash
python -c "
from engine.data import load_csv
from engine.loader import load_strategy, call_strategy

df = load_csv('data/raw/daily/xauusd_1D_comma.csv')
fn = load_strategy('strategies/24_vwap_reversion.py')
signals = call_strategy(fn, df, params={'threshold': 0.015})

print(f'✅ Signals generated: {len(signals)} bars')
print(f'Signal range: [{signals.min():.2f}, {signals.max():.2f}]')
print(f'Non-zero signals: {(signals != 0).sum()}')
print(f'Long signals: {(signals > 0).sum()}')
print(f'Short signals: {(signals < 0).sum()}')
"
```

**What to look for:**
- ✅ Signals generated without error
- ✅ Range is [-1, 0, 1]
- ✅ Reasonable number of trades (not 0, not thousands)

**Checkpoint:** ✓ Contract validated. Signals look reasonable. Move to Phase 3.

---

## Phase 3: Single Backtest (Sanity Check)

### 3.1 Run Basic Backtest

```bash
python -m execute.run_from_config configs/experiments/gold_vwap.yaml --no-mc
```

**Expected output:**
```
================================================================================
BACKTEST
================================================================================
  data         : data/raw/daily/xauusd_1D_comma.csv
  strategy     : strategies/24_vwap_reversion.py
  initial cash : 100000.0
================================================================================

Results saved to: results/runs/<run_id>/
```

### 3.2 Check Outputs

```bash
ls -lh results/runs/<run_id>/
```

**Expected files:**
```
manifest.json
equity.csv
trades.csv
fills.csv
metrics.json
```

### 3.3 Quick Metrics Review

```bash
cat results/runs/<run_id>/metrics.json | jq '.sharpe, .CAGR, .max_drawdown, .num_trades'
```

**What to look for:**
- ✅ Backtest completes without errors
- ✅ Metrics are computed (Sharpe, CAGR, MaxDD)
- ⚠️ Don't trust the results yet — this is just validation

**Checkpoint:** ⚠️ Sanity check passed. This is NOT a verdict—it's just validation that the engine works. Move to Phase 4.

---

## Phase 4: Monte Carlo Validation

### 4.1 Run Full Backtest with Monte Carlo

```bash
python -m execute.run_from_config configs/experiments/gold_vwap.yaml
```

This runs 5000 simulations to test if the Sharpe is statistically significant.

### 4.2 Check Monte Carlo Results

```bash
cat results/runs/<run_id>/monte_carlo.json | jq '.[] | {method, p_value_sharpe, observed_sharpe}'
```

### 4.3 Key Metrics to Review

| Metric | Interpretation | Action |
|--------|---|---|
| IID p-value | < 0.05 = significant \| > 0.10 = noise | Check if Sharpe beats randomness |
| Null bootstrap p-value | < 0.05 = meaningful skill \| > 0.10 = zero-skill world | Check if strategy beats zero-mean |
| Block bootstrap p-value | < 0.05 = structure matters \| > 0.10 = random | Check if timing skill exists |
| Signal shuffle p-value | < 0.05 = timing skill \| > 0.10 = no edge | Critical test for alpha |

### 4.4 Interpret Results

- **Pass:** All p-values < 0.05 → Proceed to Phase 5
- **Fail:** Any p-value > 0.10 → Strategy likely noise. Consider stopping or parameter sweep.

**Checkpoint:** ⚠️ If p-values are high, strategy may not have edge. Phase 5 walk-forward is the definitive test.

---

## Phase 5: Walk-Forward Validation (OUT-OF-SAMPLE TEST)

### 5.1 Create Walk-Forward Config

Create `configs/experiments/gold_vwap_wf.yaml`:

```yaml
data:
  path: data/raw/daily/xauusd_1D_comma.csv
  symbol: XAUUSD

strategy:
  path: strategies/24_vwap_reversion.py
  params:
    threshold: 0.015

engine:
  initial_cash: 100000.0
  commission_bps: 1.0
  slippage_bps: 5.0
  no_trade_band: 0.01

walk_forward:
  train_bars: 756        # 3 years
  test_bars: 252         # 1 year
  step_bars: 126         # 6-month slide
  warmup_bars: 252       # indicator warmup
  compute_benchmark: true
  min_trades_high_confidence: 5

monte_carlo:
  enabled: false

output:
  results_dir: results
  save_manifest: true
```

### 5.2 Run Walk-Forward Validation

```bash
python -m execute.run_walk_forward configs/experiments/gold_vwap_wf.yaml
```

### 5.3 THE CRITICAL METRICS

| Metric | Robust (✅) | Acceptable (⚠️) | Overfit (❌) |
|--------|---|---|---|
| **Degradation Ratio** | > 0.7 | 0.5-0.7 | < 0.5 |
| **Chained OOS Excess Sharpe** | > 0.2 | 0 to 0.2 | < 0 |
| **% Positive OOS Windows** | > 70% | 50-70% | < 50% |
| **Low-Confidence Windows** | Few | Some | All |

### 5.4 Read the Full Report

```bash
cat results/runs/<run_id>/walk_forward_aggregate.json | jq
```

### 5.5 What the Verdict Tells You

- **Robust = YES:** Strategy is not overfit. OOS performance matches IS. Proceed to Phase 6.
- **Has edge = YES:** Chained excess Sharpe > 0.2. Strategy beats same-exposure benchmark. KEEP.
- **Has edge = NO:** Chained excess Sharpe < 0. Strategy worse than passive. STOP or iterate.

**Checkpoint:** 🎯 This is the definitive test. If excess Sharpe < 0, strategy has no edge. If > 0.2, it has meaningful alpha.

---

## Phase 6: Benchmark Comparison

### 6.1 Extract Benchmark Metrics

```bash
cat results/runs/<run_id>/walk_forward_aggregate.json | jq '{
  chained_strategy_sharpe: .chained_OOS_sharpe,
  chained_benchmark_sharpe: .chained_OOS_benchmark_sharpe,
  chained_excess_sharpe: .chained_OOS_excess_sharpe,
  mean_OOS_excess_sharpe: .mean_OOS_excess_sharpe,
  has_edge: .has_edge
}'
```

### 6.2 Interpretation

| Excess Sharpe | Meaning | Action |
|---|---|---|
| > 0.2 | Strategy significantly beats passive | ✅ HAS EDGE — Keep & validate |
| 0 to 0.2 | Strategy slightly beats passive | ⚠️ WEAK — Needs stronger signal |
| < 0 | Passive beats strategy | ❌ NO EDGE — Stop or redesign |

**Checkpoint:** ✓ If has_edge = true, proceed to Phase 7. If false, strategy is finished.

---

## Phase 7: Cross-Asset Screening (Optional)

### 7.1 Test on All Assets

Only do this if Phase 5 showed edge.

```bash
python -m execute.screen_all_assets
```

### 7.2 View Results

```bash
cat results/screen_all_assets.csv | column -t -s,
```

### 7.3 Look For

- Which assets show positive edge?
- Is gold special, or does edge hold across multiple assets?
- Consistent results suggest genuine signal vs data quirk

**Checkpoint:** ✓ If edge is broad (multiple assets), strategy is more robust. Move to Phase 8.

---

## Phase 8: Parameter Sweep

### 8.1 Test Threshold Variations

Only do this if Phase 5-7 showed edge.

Create multiple configs:
- `gold_vwap_threshold_010.yaml` (threshold: 0.010)
- `gold_vwap_threshold_015.yaml` (threshold: 0.015)
- `gold_vwap_threshold_020.yaml` (threshold: 0.020)
- `gold_vwap_threshold_025.yaml` (threshold: 0.025)

### 8.2 Run Walk-Forward on Each

```bash
for threshold in 010 015 020 025; do
  python -m execute.run_walk_forward \
    configs/experiments/gold_vwap_threshold_$threshold.yaml
done
```

### 8.3 Compare Results

```bash
for threshold in 010 015 020 025; do
  echo "Threshold $threshold:"
  cat results/runs/*/walk_forward_aggregate.json | \
    jq '.chained_OOS_excess_sharpe'
done
```

### 8.4 Look for Parameter Neighborhoods

| Pattern | Meaning | Signal |
|---|---|---|
| Multiple nearby values work | Parameter neighborhood (robust) | ✅ GOOD |
| Only one value works | Isolated optimum (likely overfit) | ⚠️ RISKY |
| No values work | Parameter irrelevant | ❌ STOP |

**Checkpoint:** ✓ Parameter sweep identifies if edge is robust or dependent on one magic number.

---

## Decision Tree

```
Strategy implemented
        ↓
    Loads without error? → NO → Fix contract violation
        ↓ YES
    Generates signals? → NO → Fix logic
        ↓ YES
    Backtest completes? → NO → Debug engine
        ↓ YES
    Passes Monte Carlo? → NO → Likely noise → STOP
        ↓ YES
    Walk-forward robust? → NO → Overfit → STOP
        ↓ YES
    Has positive excess Sharpe? → NO → No edge → STOP
        ↓ YES
    Test cross-asset
        ↓
    Parameter sweep
        ↓
    ✅ ADD TO PRODUCTION CANDIDATES
```

---

## Quick Reference: All Commands

### Phase 2: Validation
```bash
python -c "from engine.loader import load_strategy; load_strategy('strategies/24_vwap_reversion.py')"
```

### Phase 3: Sanity Check
```bash
python -m execute.run_from_config configs/experiments/gold_vwap.yaml --no-mc
```

### Phase 4: Monte Carlo
```bash
python -m execute.run_from_config configs/experiments/gold_vwap.yaml
```

### Phase 5: Walk-Forward (THE KEY TEST)
```bash
python -m execute.run_walk_forward configs/experiments/gold_vwap_wf.yaml
```

### Phase 7: Cross-Asset
```bash
python -m execute.screen_all_assets
```

### Phase 8: Parameter Sweep
```bash
for threshold in 010 015 020 025; do
  python -m execute.run_walk_forward configs/experiments/gold_vwap_threshold_$threshold.yaml
done
```

---

## Expected Outcome Based on Gold Analysis

Based on your gold daily findings (Absolute Momentum and Golden Cross):

- ✅ Strategy **not overfit** (degradation ratio ≈ 1.0)
- ❌ **No edge** (excess Sharpe < 0)
- ⚠️ All windows **low-confidence** (< 5 trades per year)
- 📊 Chained benchmark beats strategy

**The critical test:** Phase 5 walk-forward with `compute_benchmark: true`

If `chained_OOS_excess_sharpe < 0`, VWAP has no edge on gold daily — same conclusion as existing strategies.

---

## Key Insights

1. **Phase 5 is decisive** — Walk-forward validation reveals true out-of-sample performance
2. **Excess Sharpe matters** — Tells you if strategy beats a simple passive alternative
3. **Low-confidence windows are normal** — Intraday strategies trade infrequently; sample sizes are small
4. **Chained OOS is what counts** — Pools all windows for meaningful statistics
5. **Parameter neighborhoods > isolated optima** — Robust signals work across similar parameters

---

## Next Steps

1. Implement VWAP strategy (Phase 1)
2. Run through Phase 2 validation
3. If it passes Phase 5 walk-forward with positive excess Sharpe, investigate further
4. If it fails Phase 5, add to rejection list alongside Absolute Momentum and Golden Cross
