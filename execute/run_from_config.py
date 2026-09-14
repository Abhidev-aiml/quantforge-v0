"""
Unified run entry point.

Usage:
    python -m execute.run_from_config configs/experiments/gold_abs_momentum.yaml
    python -m execute.run_from_config <exp.yaml> --no-mc
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from engine.config import load_config, config_hash, summarize
from engine.run_context import RunContext
from engine.data import load_csv, cache
from engine.core import BacktestEngine
from analytics.metrics import compute_metrics, extract_trades
from engine.loader import load_strategy, validate_signals, call_strategy


def main():
    p = argparse.ArgumentParser()
    p.add_argument("config", help="path to experiment YAML")
    p.add_argument("--no-mc", action="store_true",
                   help="skip Monte Carlo (fast loop)")
    args = p.parse_args()

    # 1. Load + validate config
    cfg = load_config(args.config, base_path="configs/base.yaml")
    print("=" * 78)
    print(summarize(cfg))
    print("=" * 78)

    if args.no_mc:
        cfg.monte_carlo.enabled = False

    # 2. Create run context
    ctx = RunContext.create(cfg)
    print(f"\nRun ID: {ctx.run_id}")
    print(f"Run dir: {ctx.run_dir}")

    # 3. Load data
    df = load_csv(cfg.data.path)
    data_hash = cache(df, cfg.data.path)
    ctx.set_data_hash(data_hash)
    print(f"\nData: {cfg.data.path}")
    print(f"      {len(df)} bars ({df.index[0].date()} → {df.index[-1].date()})")
    print(f"      hash={data_hash}")

    # 4. Load + validate strategy
    fn = load_strategy(cfg.strategy.path)
    params = getattr(cfg.strategy, "params", {}) or {}
    raw_sig = call_strategy(fn, df, params=params)
    sig = validate_signals(raw_sig, df)
    print(f"\nStrategy: {cfg.strategy.path}")
    print(f"{int((sig != 0).sum())} bars with non-flat position")

    # 5. Run backtest
    eng = BacktestEngine(
        initial_cash=cfg.engine.initial_cash,
        commission_bps=cfg.engine.commission_bps,
        slippage_bps=cfg.engine.slippage_bps,
        no_trade_band=cfg.engine.no_trade_band,
        warmup_bars=cfg.engine.warmup_bars,
    )
    equity = eng.run(df, sig)
    trades = extract_trades(eng.pf.fills)

    # 6. Save equity / trades / fills
    equity.to_frame("equity").to_csv(ctx.equity_path)
    if len(trades):
        trades.to_csv(ctx.trades_path, index=False)
    if eng.pf.fills:
        import pandas as pd
        pd.DataFrame(eng.pf.fills).to_csv(ctx.fills_path, index=False)

    # 7. Metrics
    metrics = compute_metrics(
        equity,
        rf_annual=0.0,
        trades=trades if len(trades) else None,
    )
    ctx.metrics_path.write_text(json.dumps(metrics, indent=2, default=str))

    print(f"\nMetrics:")
    print(f"  Sharpe:      {metrics['sharpe']:+.3f}")
    print(f"  CAGR:        {metrics['CAGR']*100:+.2f}%")
    print(f"  MaxDD:       {metrics['max_drawdown']*100:+.2f}%")
    print(f"  Calmar:      {metrics['calmar']:+.3f}")
    if "num_trades" in metrics:
        print(f"  Trades:      {int(metrics['num_trades'])}")
        print(f"  Win rate:    {metrics['win_rate']:.2%}")
        print(f"  Profit fac:  {metrics['profit_factor']:.3f}")

    # 8. Monte Carlo (optional)
    if cfg.monte_carlo.enabled:
        from validation.monte_carlo import (
            bootstrap_returns_under_null,
            bootstrap_returns_iid,
            bootstrap_trades,
            signal_block_shuffle,
        )
        print(f"\nMonte Carlo ({cfg.monte_carlo.n_sims} sims, seed={cfg.monte_carlo.seed})...")

        mc_report: dict = {}
        mc_report["null_bootstrap"] = bootstrap_returns_under_null(
            equity,
            n_sims=cfg.monte_carlo.n_sims,
            block_size=21,
            seed=cfg.monte_carlo.seed,
        )
        mc_report["iid_ci"] = bootstrap_returns_iid(
            equity,
            n_sims=cfg.monte_carlo.n_sims,
            seed=cfg.monte_carlo.seed,
        )
        if len(trades) >= 20:
            mc_report["trade_ci"] = bootstrap_trades(
                trades,
                n_sims=cfg.monte_carlo.n_sims,
                seed=cfg.monte_carlo.seed,
            )

        sweep = []
        for bs in cfg.monte_carlo.block_sizes:
            r = signal_block_shuffle(
                df, fn, block_size=bs,
                n_sims=cfg.monte_carlo.n_perm,
                seed=cfg.monte_carlo.seed,
            )
            sweep.append({"block": bs, **r})
        mc_report["signal_shuffle_sweep"] = sweep

        ctx.mc_path.write_text(json.dumps(mc_report, indent=2, default=str))
        print(f"  null bootstrap p = {mc_report['null_bootstrap']['p_value_one_sided']:.4f}")
        best = min(sweep, key=lambda x: x["p_value"])
        print(f"  best block={best['block']} p = {best['p_value']:.4f}")

    # 9. Write final manifest
    ctx.add_results({
        "sharpe": metrics["sharpe"],
        "cagr": metrics["CAGR"],
        "max_drawdown": metrics["max_drawdown"],
        "calmar": metrics["calmar"],
        "n_trades": int(metrics.get("num_trades", 0)),
    })
    print(f"\n✅ Run complete → {ctx.run_dir}/")
    print(f"   Manifest: {ctx.manifest_path}")


if __name__ == "__main__":
    main()