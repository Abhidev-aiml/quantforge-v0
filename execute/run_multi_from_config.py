"""
Multi-asset backtest runner.

Usage:
    python -m execute.run_multi_from_config configs/experiments/xs_momentum_daily.yaml
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from engine.multi_data import compute_universe_hash

import numpy as np
import pandas as pd

from engine.config import load_multi_config, multi_config_hash
from engine.run_context import RunContext
from engine.multi_data import discover_symbols, prepare_multi_data
from engine.multi_core import MultiAssetBacktestEngine
from strategies.xs_momentum import cross_sectional_momentum
from analytics.metrics import (
    compute_metrics,
    extract_trades_multi,
    portfolio_turnover,
    avg_gross_exposure,
    avg_net_exposure,
)


def equal_weight_benchmark(
    data: dict[str, pd.DataFrame],
    rebalance_freq: str = "MS",
) -> pd.Series:
    """Equal-weight monthly-rebalanced buy-and-hold of all symbols."""
    idx = None
    for df in data.values():
        idx = df.index if idx is None else idx.union(df.index)
    idx = idx.sort_values()

    n = len(data)
    weight = 1.0 / n

    # Rebalance dates
    target_dates = pd.date_range(idx.min(), idx.max(), freq=rebalance_freq)
    rebalance_dates = []
    for d in target_dates:
        candidates = idx[idx >= d]
        if len(candidates):
            rebalance_dates.append(candidates[0])
    rebalance_dates = sorted(set(rebalance_dates))

    # Build returns matrix
    closes = pd.DataFrame({sym: df["close"] for sym, df in data.items()})
    closes = closes.reindex(idx).ffill()
    returns = closes.pct_change().fillna(0.0)

    # Simulate equal-weight with monthly rebalance
    equity = 100_000.0
    curve = []
    current_w = pd.Series(0.0, index=list(data.keys()))

    for i, ts in enumerate(idx):
        if ts in rebalance_dates:
            current_w = pd.Series(weight, index=list(data.keys()))

        bar_ret = float((current_w * returns.loc[ts]).sum())
        equity *= (1.0 + bar_ret)
        curve.append({"timestamp": ts, "equity": equity})

    return pd.DataFrame(curve).set_index("timestamp")["equity"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("config", help="path to multi-asset experiment YAML")
    p.add_argument("--no-mc", action="store_true",
                   help="skip Monte Carlo (fast loop)")
    args = p.parse_args()

    # 1. Load config
    cfg = load_multi_config(args.config, base_path="configs/base.yaml")
    print("=" * 78)
    print(f"Multi-asset run  (config_hash={multi_config_hash(cfg)})")
    print(f"  data dir     : {cfg.data.directory}")
    print(f"  pattern      : {cfg.data.pattern}")
    print(f"  engine       : cash={cfg.engine.initial_cash:.0f} "
          f"comm={cfg.engine.commission_bps}bps slip={cfg.engine.slippage_bps}bps")
    print(f"  strategy     : XS momentum  lookback={cfg.strategy.lookback} "
          f"skip={cfg.strategy.skip} top_k={cfg.strategy.top_k} "
          f"bottom_k={cfg.strategy.bottom_k} "
          f"long_short={cfg.strategy.long_short}")
    print(f"  monte carlo  : {'on' if (cfg.monte_carlo.enabled and not args.no_mc) else 'off'}")
    print("=" * 78)

    if args.no_mc:
        cfg.monte_carlo.enabled = False

    # 2. Run context
    ctx = RunContext.create(cfg)
    print(f"\nRun ID: {ctx.run_id}")
    print(f"Run dir: {ctx.run_dir}")

    # 3. Load data
    symbol_paths = discover_symbols(cfg.data.directory,
                                    pattern=cfg.data.pattern,
                                    exclude=cfg.data.exclude)
    print(f"\nDiscovered {len(symbol_paths)} symbols:")
    for sym in list(symbol_paths)[:20]:
        print(f"  - {sym}")
    if len(symbol_paths) > 20:
        print(f"  ... and {len(symbol_paths) - 20} more")

    data, index = prepare_multi_data(symbol_paths,
                                     start=cfg.data.start,
                                     end=cfg.data.end)
    print(f"\nUnified index: {len(index)} bars "
          f"({index[0].date()} → {index[-1].date()})")

    universe_hash = compute_universe_hash(data)
    ctx.manifest["data_hash"] = universe_hash
    ctx._write_manifest()
    print(f"Universe hash: {universe_hash}")

    # 4. Generate signals
    close_matrix = pd.DataFrame(
        {sym: df["close"] for sym, df in data.items()}
    ).reindex(index).ffill()

    signals = cross_sectional_momentum(
        close_matrix,
        lookback=cfg.strategy.lookback,
        skip=cfg.strategy.skip,
        top_k=cfg.strategy.top_k,
        bottom_k=cfg.strategy.bottom_k,
        rebalance_freq=cfg.strategy.rebalance_freq,
        long_short=cfg.strategy.long_short,
        gross_exposure=cfg.strategy.gross_exposure,
    )

    print(f"\nSignal summary:")
    print(f"  turnover per bar   : {portfolio_turnover(signals):.4f}")
    print(f"  avg gross exposure : {avg_gross_exposure(signals):.3f}")
    print(f"  avg net exposure   : {avg_net_exposure(signals):+.3f}")
    print(f"  non-flat bars      : {int((signals.abs().sum(axis=1) > 0).sum())}")

    # 5. Run backtest
    warmup = cfg.strategy.lookback + cfg.strategy.skip
    eng = MultiAssetBacktestEngine(
        symbols=list(data.keys()),
        initial_cash=cfg.engine.initial_cash,
        commission_bps=cfg.engine.commission_bps,
        slippage_bps=cfg.engine.slippage_bps,
        no_trade_band=cfg.engine.no_trade_band,
        warmup_bars=max(warmup, cfg.engine.warmup_bars),
        allow_short=cfg.strategy.long_short,
    )
    equity = eng.run(data, signals)

    # 6. Benchmark
    bench_eq = equal_weight_benchmark(data, rebalance_freq=cfg.strategy.rebalance_freq)

    # 7. Trades + metrics
    trades = extract_trades_multi(eng.pf.fills)
    metrics = compute_metrics(equity, rf_annual=0.0,
                              trades=trades if len(trades) else None)
    bench_metrics = compute_metrics(bench_eq, rf_annual=0.0)

    # 8. Save artifacts
    equity.to_frame("equity").to_csv(ctx.equity_path)
    if len(trades):
        trades.to_csv(ctx.trades_path, index=False)
    if eng.pf.fills:
        pd.DataFrame(eng.pf.fills).to_csv(ctx.fills_path, index=False)

    extended = {
        "strategy": metrics,
        "benchmark": bench_metrics,
        "excess_sharpe": metrics["sharpe"] - bench_metrics["sharpe"],
        "excess_CAGR": metrics["CAGR"] - bench_metrics["CAGR"],
        "avg_turnover": portfolio_turnover(signals),
        "avg_gross_exposure": avg_gross_exposure(signals),
        "avg_net_exposure": avg_net_exposure(signals),
    }
    ctx.metrics_path.write_text(json.dumps(extended, indent=2, default=str))

    # 9. Print results
    print(f"\n" + "=" * 78)
    print("RESULTS")
    print("=" * 78)
    print(f"                       Strategy      Benchmark     Excess")
    print(f"  Sharpe               {metrics['sharpe']:+8.3f}     {bench_metrics['sharpe']:+8.3f}     "
          f"{metrics['sharpe'] - bench_metrics['sharpe']:+8.3f}")
    print(f"  CAGR                 {metrics['CAGR']*100:+7.2f}%     {bench_metrics['CAGR']*100:+7.2f}%     "
          f"{(metrics['CAGR'] - bench_metrics['CAGR'])*100:+7.2f}%")
    print(f"  MaxDD                {metrics['max_drawdown']*100:+7.2f}%     "
          f"{bench_metrics['max_drawdown']*100:+7.2f}%")
    print(f"  Calmar               {metrics['calmar']:+8.3f}     {bench_metrics['calmar']:+8.3f}")
    print(f"  Volatility           {metrics['volatility']*100:+7.2f}%     "
          f"{bench_metrics['volatility']*100:+7.2f}%")
    if "num_trades" in metrics:
        print(f"\n  Trades               {int(metrics['num_trades'])}")
        print(f"  Win rate             {metrics['win_rate']:.2%}")
        print(f"  Profit factor        {metrics['profit_factor']:.3f}")
        print(f"  Expectancy %         {metrics['expectancy_pct']*100:+.3f}%")

    # 10. Monte Carlo
    if cfg.monte_carlo.enabled:
        from validation.monte_carlo import (
            bootstrap_returns_under_null,
            bootstrap_returns_iid,
        )
        print(f"\nMonte Carlo ({cfg.monte_carlo.n_sims} sims, seed={cfg.monte_carlo.seed})...")
        mc_report = {
            "null_bootstrap": bootstrap_returns_under_null(
                equity, n_sims=cfg.monte_carlo.n_sims, block_size=21,
                seed=cfg.monte_carlo.seed,
            ),
            "iid_ci": bootstrap_returns_iid(
                equity, n_sims=cfg.monte_carlo.n_sims,
                seed=cfg.monte_carlo.seed,
            ),
        }
        ctx.mc_path.write_text(json.dumps(mc_report, indent=2, default=str))
        print(f"  null bootstrap p = {mc_report['null_bootstrap']['p_value_one_sided']:.4f}")
        print(f"  IID Sharpe 90% CI = "
              f"[{mc_report['iid_ci']['sharpe_p05']:.3f}, "
              f"{mc_report['iid_ci']['sharpe_p95']:.3f}]")

    # 11. Manifest
    ctx.add_results({
        "strategy_sharpe": metrics["sharpe"],
        "benchmark_sharpe": bench_metrics["sharpe"],
        "excess_sharpe": metrics["sharpe"] - bench_metrics["sharpe"],
        "strategy_CAGR": metrics["CAGR"],
        "strategy_maxdd": metrics["max_drawdown"],
        "n_trades": int(metrics.get("num_trades", 0)),
        "n_symbols": len(data),
    })
    print(f"\n✅ Run complete → {ctx.run_dir}/")


if __name__ == "__main__":
    main()