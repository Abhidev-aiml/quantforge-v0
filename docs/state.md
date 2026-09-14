# QuantForge Current State

**Last updated:** 2026-09-13 (Session C — White's Reality Check)

## Document Purpose

Current-state handoff for QuantForge. Read before making changes.
The repository is the source of truth if this document diverges.

---

## 1. Current Position

QuantForge is now a **research-grade framework with a complete validation
stack**. It has been used end-to-end to test the classic retail strategy
universe and reach a definitive conclusion.

**Complete:**
- Single-asset and multi-asset engines
- Config system + run manifests
- Walk-forward validation with benchmark comparison
- Monte Carlo (IID, block, null, trade, block-trade, signal-shuffle)
- White's Reality Check (multiple-testing correction)
- 143-combo cross-asset screen with RC
- 146 passing tests

**Deliberately deferred:**
- ORB strategy integration (staged, see ORB doc)
- Live trading path
- Point-in-time data / FIGI / CUSIP
- 6-tier testing framework

---

## 2. Test State

**146 tests passing** as of Session C.

Breakdown:
```
test_config.py                    6
test_data.py                     10
test_engine.py                   13
test_engine_warmup.py             2
test_loader.py                   14
test_metrics.py                  11
test_metrics_cagr.py              2
test_montecarlo.py                7
test_montecarlo_cost_adj.py       3
test_montecarlo_timeframe.py      9
test_multi_data_hash.py           4
test_multi_engine.py              9
test_ny_orb_variations.py         5
test_orb_signal_audit.py          5
test_run_context.py               4
test_strategy_params.py           4
test_trade_execution.py          10
test_trade_plan.py                8
test_walk_forward.py             17
test_whites_reality_check.py      8
test_xs_momentum.py               4
```

To verify: `python -m pytest -v` from repo root.

---

## 3. Session A — Foundation Hardening (Complete)

### Fixes applied

1. **MC annualization consistency** — every MC function now accepts
   `periods_per_year` (auto-inferred from DatetimeIndex when None).
   `signal_block_shuffle` receives commission and slippage from config
   instead of hard-coding defaults.
2. **Trade bootstrap elapsed years** — inferred from trade timestamps
   via `_infer_trade_years`. No longer hard-codes 21.6.
3. **Strategy params wiring** — `call_strategy()` inspects the
   function signature and passes `params` only if accepted. Fully
   backward-compatible.
4. **Multi-asset data hash** — `compute_universe_hash()` produces a
   deterministic SHA-256 over all symbols' content, sorted by name.
   Written to the manifest as `data_hash`.

### Regression tests added

`test_montecarlo_timeframe.py` (9), `test_multi_data_hash.py` (4),
`test_strategy_params.py` (4).

---

## 4. Session B — Walk-Forward Validation (Complete)

### Module: `validation/walk_forward.py`

Rolling IS/OOS windows. Each OOS window is benchmarked against a
same-exposure cost-adjusted passive position. Reports:

- Per-window IS Sharpe, OOS Sharpe, benchmark Sharpe, excess Sharpe
- Chained OOS equity (concatenated OOS returns, no overlap)
- Degradation ratio (mean OOS Sharpe / mean IS Sharpe)
- Two verdicts: `robust` (WF) and `has_edge` (chained excess > 0.2)

### Results on gold daily (2004–2026)

| Metric | Absolute Momentum | Golden Cross |
|---|---|---|
| Mean IS Sharpe | +0.275 | +0.323 |
| Mean OOS Sharpe | +0.252 | +0.280 |
| Chained OOS Sharpe | +0.416 | +0.504 |
| Chained benchmark Sharpe | +0.800 | +0.874 |
| **Chained excess Sharpe** | **−0.385** | **−0.370** |
| Robust (WF) | YES | YES |
| **Has edge** | **NO** | **NO** |
| Low-confidence windows | 36/36 | 36/36 |

**Interpretation:** Both strategies are walk-forward robust (no
overfitting) but have no excess return over a passive position with
the same average exposure. Their "returns" are entirely captured by
gold's secular drift.

---

## 5. Session C — White's Reality Check (Complete)

### Module: `validation/whites_reality_check.py`

Stationary block bootstrap over a (T, K) excess-return matrix.
Resamples identical time indices across all K columns to preserve
cross-strategy correlation. Tests whether the observed max excess
return is unusual under a null where every combo has zero mean.

### Universe tested

- 13 assets (Brent, DAX, EURUSD, GBPUSD, GBR index, US30, US500,
  US Tech, USDCAD, USDCHF, USDJPY, Silver, Gold)
- 11 strategies (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 25)
- **143 total combos**

Common index: 3199 bars (2013-05-23 → 2026-01-30)

### Result
```
Observed V statistic:             0.0302
Bootstrap V mean:                 0.0296
Bootstrap V 95th percentile:      0.0520
Bootstrap V 99th percentile:      0.0672
p-value:                          0.4054
Verdict:                          FAIL TO REJECT H0
```

**The best combo (EMA cross × Brent, +13.47%/yr excess) is
indistinguishable from what random chance produces across 143 trials.**

Supporting facts:
- 92/143 combos have negative excess return
- Only 51/143 combos show positive excess
- Best combo ranks at the 41st percentile of the bootstrap max
  distribution

### What this establishes

Across the full classic retail strategy universe, on daily/4H data,
across 13 diverse assets, **no single-signal strategy has statistically
significant edge over a same-exposure passive benchmark** after
multiple-testing correction.

---

## 6. The Definitive Negative Result

Three independent validation layers, same conclusion:

| Layer | Test | Result |
|---|---|---|
| Full sample | Same-exposure benchmark | Negative excess Sharpe |
| Walk-forward | Chained OOS excess | −0.37 to −0.39 Sharpe |
| Multiple testing | White's Reality Check | p = 0.41 |

**The classic daily trend/momentum/mean-reversion strategy universe
on this data does not contain demonstrable edge.** This is a valid,
comprehensive, well-supported research finding.

---

## 7. New Observations

**New strategy file observed:** `strategies/25_bollinger_rsi_double.py`
Not previously in the codebase audit. Characteristics:
- High turnover (1000+ trades per asset)
- Frequently near-zero average weight (aggressive in/out)
- Shows up in top-5 excess returns on DEU index, US30, Brent
- RC says these are not significant after correction

**Markets that repeatedly appear in top performers:**
- Brent crude (EMA cross, Bollinger-RSI double ×2)
- German DAX index
- US Tech index

Post-hoc observation. Do not treat as evidence of edge without
pre-registered hypothesis.

**Low trade counts on trend strategies:**
- Golden Cross: ~15 trades over 22 years (2/3 per year)
- Absolute Momentum: ~67 trades over 22 years (~3/year)

This is why 36/36 walk-forward windows are flagged low-confidence:
no single 1-year window has enough trades to distinguish skill from
noise. Only the chained OOS equity (pooled trades) is meaningful.

---

## 8. ORB System (Deferred)

The ORB (Opening Range Breakout) suite exists as parallel infrastructure:

- 7 strategies (#17–23) on 5M XAUUSD
- 30-minute NY opening range, explicit timezone handling
- TradePlan dataclass + execute_trade() discrete-trade simulator
- 28 passing tests covering ORB geometry, execution, trade plans
- **Not yet integrated** into the main pipeline

ORB represents a **different execution paradigm** (discrete trades with
stops/targets) vs the continuous-weight-signal engine. Integration
requires a dedicated runner.

Status: staged pending decision on research direction (see §11).

---

## 9. Current Architecture Gaps

### Resolved in Session A

- ~~MC annualization inconsistency~~ ✅
- ~~Trade bootstrap 21.6-year assumption~~ ✅
- ~~Strategy params not wired~~ ✅
- ~~Multi-asset data hash missing~~ ✅

### Remaining

- **Tradability semantics for multi-asset** — union-index forward-fill
  means some symbols are valued on bars where they didn't trade.
  Multi-asset results may be optimistic.
- **Benchmark implementations not unified** — `same_exposure_benchmark_cost_adjusted`
  is canonical, but `run_multi_from_config.py` uses its own equal-weight
  monthly-rebalance benchmark. Different semantics.
- **`periods_per_year=252` default** still in `compute_metrics`
  signature. Callers can override; MC functions do. Runner scripts
  use inferred values.

---

## 10. Research Methodology Lessons

Accumulated across the project:

1. **Same-exposure benchmark is the honest test.** Equity-table Sharpe
   alone is misleading on trending assets.
2. **Walk-forward doesn't catch beta.** A strategy can be robust and
   still have no edge. Benchmark comparison is required.
3. **RC corrects for the temptation to cherry-pick.** Testing 143
   combos means the best one is likely just a lucky sample.
4. **Trade count per window matters.** Trend strategies trade ~3×/year,
   which is too few for per-window Sharpe to be informative.
5. **Chained OOS equity recovers statistical power.** Pooling OOS
   trades across windows is the only way to get meaningful statistics
   from low-turnover strategies.
6. **Do not re-tune failed hypotheses.** Donchian+ADX, Orion-style,
   trend-pullback, and now the entire classic retail universe have
   been tested and rejected. Further parameter tweaks are data mining.

---

## 11. Next Research Direction — Open Decision

The validation stack has done its job. Three paths forward:

### Path A — Cross-sectional momentum on a larger universe

Current XS momentum test used 12 assets. Academic momentum research
uses 30–100+ instruments. Requires:
- More CSVs (equity indices, commodity futures, FX pairs, bonds)
- Cross-sectional rebalance (already implemented)
- Multi-asset walk-forward (not yet built)

**Effort:** 1–2 weeks for data acquisition + 1 week for multi-asset WF.

### Path B — ORB intraday on 5M XAUUSD

ORB operates in a different regime (intraday, discrete trades,
explicit stops). Standard validation tests need adaptation:
- Trade-level metrics dominate (few bars per trade)
- Walk-forward needs to be per-day or per-week, not per-bar
- Benchmark = "no-trade" baseline

**Effort:** 1–2 weeks for integration + validation adaptations.

### Path C — Accept the negative result

The classic retail universe doesn't have edge. Document and move on.
This is a legitimate stopping point.

### Path D — New hypothesis generation

Try something structurally different:
- Volatility targeting overlays
- Regime filters (VIX-based allocation)
- Multi-strategy portfolio construction (combine uncorrelated losers)
- Cross-asset correlations

**Effort:** Unknown.

---

## 12. Immediate Next Session Plan

**Before adding any new strategy:**

1. Confirm the test suite is at 146 passing
   (`python -m pytest -v`)
2. Update `docs/architecture.md` (see changelog below)
3. Decide direction: A, B, C, or D

**Do not** start Path A or Path B without first making the decision
explicit. The infrastructure is stable; the research direction is the
open question.

---

## 13. Handoff Rules

Before modifying QuantForge:

1. Read `docs/architecture.md` and this file.
2. Run `pytest -v` first — the suite must be green.
3. If you change engine semantics, add a regression test.
4. If you change MC functions, verify against the theoretical
   standard error (see `test_montecarlo.py::test_null_bootstrap_se_matches_theory`).
5. Do not re-tune a rejected hypothesis. See §10.6.
6. Keep walk-forward, White's RC, and deflated Sharpe ahead of any
   parameter optimization.

---

## 14. Architecture Changes Since Last State Doc

**New files (add to `docs/architecture.md`):**

Validation layer:
- `validation/walk_forward.py` — rolling IS/OOS with benchmark
- `validation/whites_reality_check.py` — multiple-testing correction

Execution layer:
- `execute/run_walk_forward.py`
- `execute/run_whites_rc.py`

Config files:
- `configs/experiments/gold_abs_momentum_wf.yaml`
- `configs/experiments/gold_goldencross_wf.yaml`

**Modified:**
- `validation/monte_carlo.py` — annualization + cost consistency
- `engine/loader.py` — added `call_strategy()`
- `engine/multi_data.py` — added `compute_universe_hash()`
- `analytics/metrics.py` — defensive `periods_per_year=None` handling
