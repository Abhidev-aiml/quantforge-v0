# VWAP Strategy Implementation Report

Generated: 2026-09-13

## Strategy: VWAP Mean Reversion (24_vwap_reversion.py)

**Parameters:** threshold = 0.015 (1.5% deviation from VWAP)

**Data:** XAUUSD daily, 5531 bars (2004-06-11 → 2026-01-30)

---

## Phase Results

### Phase 1: Implement ✅
- Created strategies/24_vwap_reversion.py
- Created configs/experiments/gold_vwap.yaml
- Created configs/experiments/gold_vwap_wf.yaml

### Phase 2: Validate ✅
- Strategy loads successfully
- 5254 non-zero signals generated
- Signal range: [-1.00, 1.00]
- 1402 long signals, 3852 short signals

### Phase 3: Sanity Check ✅
- Backtest completes without errors
- Sharpe: -0.579
- CAGR: -11.09%
- MaxDD: -93.03%
- ⚠️ NOT TRUSTED YET - just validation

### Phase 4: Monte Carlo Validation ✅
- IID Bootstrap p-value: **0.491** (> 0.10 = likely noise)
- Block Bootstrap p-value: **0.512**
- **Interpretation:** High p-values indicate strategy is likely noise

### Phase 5: Walk-Forward Validation ✅ (THE KEY TEST)
| Metric | Value | Interpretation |
|--------|-------|----------------|
| Windows | 36 | 21 years of OOS |
| Mean IS Sharpe | -0.312 | |
| Mean OOS Sharpe | -0.390 | |
| Degradation Ratio | 1.252 | > 1.0 (OOS better than IS) |
| Robust (WF) | NO | Negative Sharpe |
| Chained OOS Sharpe | -0.375 | |
| Chained Benchmark Sharpe | -0.704 | |
| **Chained EXCESS Sharpe** | **+0.330** | **> 0.2 = HAS EDGE** |
| Low-Confidence Windows | 36/36 | All < 5 trades |

### Phase 6: Benchmark Comparison ✅
- Chained EXCESS Sharpe: +0.330 (> 0.2 threshold)
- **VERDICT: HAS EDGE**

### Phase 7: Cross-Asset Screening ⏭️ (SKIPPED)
- Run manually: `python -m execute.screen_all_assets`

### Phase 8: Parameter Sweep ⏭️ (SKIPPED)
- Run manually with threshold variations (0.010, 0.015, 0.020, 0.025)

---

## Final Verdict

| Criterion | Result |
|-----------|--------|
| Monte Carlo p-value | 0.491 (HIGH - noise) |
| Walk-forward robust | NO |
| Has edge (excess > 0.2) | **YES** ✅ |
| Chained EXCESS Sharpe | +0.330 |

**Conclusion:** VWAP strategy shows edge over benchmark, BUT:
- Both strategy and benchmark are NEGATIVE (lose money)
- Strategy wins because it's LESS negative than benchmark
- This is similar to Absolute Momentum and Golden Cross findings
- The "edge" comes from benchmark performing terribly (-0.704)

**Insight:** The strategy has no absolute edge (negative Sharpe), but relative edge 
over benchmark exists because benchmark is even worse. This confirms the pattern
from gold daily strategies: timing skill is absent.

---

## Files Created
- `strategies/24_vwap_reversion.py`
- `configs/experiments/gold_vwap.yaml`
- `configs/experiments/gold_vwap_wf.yaml`

## Commands to Continue
```bash
# Phase 7: Cross-asset
python -m execute.screen_all_assets

# Phase 8: Parameter sweep
for t in 010 015 020 025; do
  python -m execute.run_walk_forward configs/experiments/gold_vwap_threshold_$t.yaml
done
```
