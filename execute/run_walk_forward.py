"""
Walk-forward validation runner with benchmark comparison.

Usage:
    python -m execute.run_walk_forward configs/experiments/gold_abs_momentum_wf.yaml
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from engine.config import load_config
from engine.run_context import RunContext
from engine.data import load_csv, cache
from engine.loader import load_strategy
from analytics.metrics import compute_metrics
from validation.walk_forward import walk_forward, windows_to_dataframe


# ---------------------------------------------------------------- helpers

def _chain_oos_equity(
    windows,
    attr: str,
    step_bars: int,
    starting_capital: float = 100_000.0,
) -> pd.Series | None:
    """
    Reconstruct the chained OOS equity curve from per-window equities.

    Takes the first `step_bars` returns of each window's equity, concatenates
    them, dedupes overlapping indices, and rebuilds an equity curve.
    """
    parts = []
    for w in windows:
        eq = getattr(w, attr, None)
        if eq is None or len(eq) < 2:
            continue
        rets = eq.pct_change().dropna()
        if len(rets) == 0:
            continue
        rets = rets.iloc[:step_bars] if len(rets) > step_bars else rets
        parts.append(rets)
    if not parts:
        return None
    chained = pd.concat(parts).sort_index()
    chained = chained[~chained.index.duplicated(keep="first")]
    if len(chained) < 2:
        return None
    return starting_capital * (1.0 + chained).cumprod()


def _infer_ppy(idx: pd.DatetimeIndex) -> float:
    if len(idx) < 3:
        return 252.0
    days = (idx[-1] - idx[0]).days
    if days <= 0:
        return 252.0
    return float(len(idx) / (days / 365.25))


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser()
    p.add_argument("config", help="path to experiment YAML")
    args = p.parse_args()

    with open(args.config) as f:
        cfg_dict = yaml.safe_load(f)

    cfg = load_config(args.config, base_path="configs/base.yaml")

    wf_cfg = cfg_dict.get("walk_forward", {})
    train_bars = wf_cfg.get("train_bars", 756)
    test_bars = wf_cfg.get("test_bars", 252)
    step_bars = wf_cfg.get("step_bars", None) or test_bars
    warmup_bars = wf_cfg.get("warmup_bars", 0)
    compute_benchmark = wf_cfg.get("compute_benchmark", True)
    min_trades_high_conf = wf_cfg.get("min_trades_high_confidence", 5)

    print("=" * 78)
    print("WALK-FORWARD VALIDATION (with benchmark)")
    print("=" * 78)
    print(f"  config       : {args.config}")
    print(f"  strategy     : {cfg.strategy.path}")
    print(f"  data         : {cfg.data.path}")
    print(f"  train bars   : {train_bars}")
    print(f"  test bars    : {test_bars}")
    print(f"  step bars    : {step_bars}")
    print(f"  warmup bars  : {warmup_bars}")
    print(f"  benchmark    : {'on' if compute_benchmark else 'off'}")
    print("=" * 78)

    df = load_csv(cfg.data.path)
    cache(df, cfg.data.path)
    fn = load_strategy(cfg.strategy.path)
    params = getattr(cfg.strategy, "params", {}) or {}

    engine_params = {
        "initial_cash": cfg.engine.initial_cash,
        "commission_bps": cfg.engine.commission_bps,
        "slippage_bps": cfg.engine.slippage_bps,
        "no_trade_band": cfg.engine.no_trade_band,
        "warmup_bars": 0,
    }

    windows, agg = walk_forward(
        df, fn,
        strategy_params=params,
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        warmup_bars=warmup_bars,
        engine_params=engine_params,
        commission_bps=cfg.engine.commission_bps,
        slippage_bps=cfg.engine.slippage_bps,
        compute_benchmark=compute_benchmark,
        min_trades_high_confidence=min_trades_high_conf,
    )

    print(f"\n[1] In/Out-of-sample summary")
    print(f"    Windows:              {agg['n_windows']}")
    print(f"    Clean OOS windows:    {agg['n_oos_clean']}")
    print(f"    Mean IS Sharpe:       {agg['mean_IS_sharpe']:+.3f}")
    print(f"    Mean OOS Sharpe:      {agg['mean_OOS_sharpe']:+.3f}")
    print(f"    Median OOS Sharpe:    {agg['median_OOS_sharpe']:+.3f}")
    print(f"    Std OOS Sharpe:       {agg['std_OOS_sharpe']:.3f}")
    print(f"    Min/Max OOS:          {agg['min_OOS_sharpe']:+.3f} / {agg['max_OOS_sharpe']:+.3f}")
    print(f"    % positive OOS:       {agg['pct_positive_OOS']:.1%}")
    print(f"    Degradation ratio:    {agg['degradation_ratio']:.3f}")
    print(f"    Robust (WF):          {'YES' if agg['robust'] else 'NO'}")

    if compute_benchmark:
        print(f"\n[2] Per-window benchmark comparison")
        print(f"    Mean OOS excess Sharpe:   {agg['mean_OOS_excess_sharpe']:+.3f}")
        print(f"    Median OOS excess Sharpe: {agg['median_OOS_excess_sharpe']:+.3f}")
        print(f"    Std OOS excess Sharpe:    {agg['std_OOS_excess_sharpe']:.3f}")
        print(f"    % positive excess OOS:    {agg['pct_positive_excess_OOS']:.1%}")

    print(f"\n[3] Chained OOS equity (all windows concatenated)")
    print(f"    Bars:                     {agg['chained_OOS_bars']}")
    print(f"    Chained OOS Sharpe:       {agg['chained_OOS_sharpe']:+.3f}")
    print(f"    Chained OOS CAGR:         {agg['chained_OOS_CAGR']*100:+.2f}%")
    print(f"    Chained OOS MaxDD:        {agg['chained_OOS_maxdd']*100:+.2f}%")
    if compute_benchmark:
        print(f"    Chained benchmark Sharpe: {agg['chained_OOS_benchmark_sharpe']:+.3f}")
        print(f"    Chained EXCESS Sharpe:    {agg['chained_OOS_excess_sharpe']:+.3f}")
        print(f"    Chained EXCESS CAGR:      {agg['chained_OOS_excess_CAGR']*100:+.2f}%")

    print(f"\n[4] Data quality")
    print(f"    Low-confidence windows (< {min_trades_high_conf} trades): "
          f"{agg['n_low_confidence_windows']}/{agg['n_windows']}")

    print(f"\n[5] Verdict")
    print(f"    Walk-forward robust:      {'YES' if agg['robust'] else 'NO'}")
    print(f"    Has edge (excess > 0.2):  {'YES' if agg['has_edge'] else 'NO'}")

    # ---------------------------------------------------------------
    # Save artifacts, INCLUDING chained equity + metrics so that
    # reporting.build can consume this run like any other.
    # ---------------------------------------------------------------
    ctx = RunContext.create(cfg)

    # 1. Per-window table
    df_windows = windows_to_dataframe(windows)
    out_windows = ctx.run_dir / "walk_forward_windows.csv"
    df_windows.to_csv(out_windows, index=False)

    # 2. Aggregate metrics
    out_agg = ctx.run_dir / "walk_forward_aggregate.json"
    out_agg.write_text(json.dumps(agg, indent=2, default=str))

    # 3. Chained OOS equity curve
    chained_eq = _chain_oos_equity(windows, "oos_equity", step_bars,
                                   starting_capital=cfg.engine.initial_cash)
    if chained_eq is not None:
        eq_df = pd.DataFrame({
            "timestamp": chained_eq.index,
            "equity": chained_eq.values,
        })
        eq_df.to_csv(ctx.run_dir / "equity.csv", index=False)

        # 4. Derived metrics (so reporting.build works)
        ppy = _infer_ppy(chained_eq.index)
        metrics = compute_metrics(chained_eq, periods_per_year=ppy)
        (ctx.run_dir / "metrics.json").write_text(
            json.dumps(metrics, indent=2, default=str)
        )

    # 5. Chained benchmark equity (if computed)
    chained_bench = _chain_oos_equity(windows, "oos_benchmark_equity", step_bars,
                                      starting_capital=cfg.engine.initial_cash)
    if chained_bench is not None:
        bench_df = pd.DataFrame({
            "timestamp": chained_bench.index,
            "equity": chained_bench.values,
        })
        bench_df.to_csv(ctx.run_dir / "benchmark.csv", index=False)

    print(f"\n✅ Windows saved to {out_windows}")
    print(f"✅ Aggregate saved to {out_agg}")
    if chained_eq is not None:
        print(f"✅ Chained OOS equity saved → equity.csv  ({len(chained_eq)} bars)")
        print(f"✅ Metrics saved → metrics.json")
    if chained_bench is not None:
        print(f"✅ Chained benchmark saved → benchmark.csv")


if __name__ == "__main__":
    main()