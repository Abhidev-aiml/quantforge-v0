"""
VWAP Strategy Multi-Asset Parameter Sweep

Tests VWAP mean reversion across multiple thresholds on ALL available
1D and 4H data. Ranks top candidates by OOS excess Sharpe.

Usage:
    python -m execute.vwap_multi_asset_sweep
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
import glob

import pandas as pd

from engine.config import load_config
from engine.data import load_csv, cache
from engine.loader import load_strategy
from validation.walk_forward import walk_forward, windows_to_dataframe


def discover_data_files():
    """Discover all available CSV data files."""
    daily_files = sorted(glob.glob('data/raw/daily/*_comma.csv'))
    fourh_files = sorted(glob.glob('data/raw/fourhours/*_comma.csv'))

    assets = {}

    for f in daily_files:
        name = Path(f).stem.replace('1440_comma', '').replace('_comma', '')
        assets[name] = {'1D': f}

    for f in fourh_files:
        name = Path(f).stem.replace('240_comma', '').replace('_comma', '')
        if name in assets:
            assets[name]['4H'] = f
        else:
            assets[name] = {'4H': f}

    return assets


def get_window_params(timeframe: str):
    """Get walk-forward window parameters for each timeframe."""
    if timeframe == '1D':
        return {'train_bars': 756, 'test_bars': 252, 'step_bars': 126}  # 3y/1y/6m
    else:  # 4H
        # ~6 bars/day, ~1500 bars/year
        return {'train_bars': 4500, 'test_bars': 1500, 'step_bars': 750}


def run_single_sweep(data_path: str, threshold: float, train_bars: int,
                     test_bars: int, step_bars: int) -> dict:
    """Run one VWAP sweep configuration."""
    try:
        df = load_csv(data_path)
        cache(df, data_path)
        fn = load_strategy('strategies/24_vwap_reversion.py')

        engine_params = {
            'initial_cash': 100000,
            'commission_bps': 1.0,
            'slippage_bps': 5.0,
            'no_trade_band': 0.01,
            'warmup_bars': 0
        }

        windows, agg = walk_forward(
            df, fn,
            strategy_params={'threshold': threshold},
            train_bars=train_bars,
            test_bars=test_bars,
            step_bars=step_bars,
            warmup_bars=252,
            compute_benchmark=True,
            min_trades_high_confidence=5,
            engine_params=engine_params
        )

        return {
            'threshold': threshold,
            'data_path': data_path,
            'n_windows': agg.get('n_windows', 0),
            'mean_IS_sharpe': round(agg.get('mean_IS_sharpe', 0), 3),
            'mean_OOS_sharpe': round(agg.get('mean_OOS_sharpe', 0), 3),
            'degradation_ratio': round(agg.get('degradation_ratio', 0), 3),
            'robust': agg.get('robust', False),
            'chained_OOS_sharpe': round(agg.get('chained_OOS_sharpe', 0), 3),
            'chained_OOS_benchmark_sharpe': round(agg.get('chained_OOS_benchmark_sharpe', 0), 3),
            'chained_OOS_excess_sharpe': round(agg.get('chained_OOS_excess_sharpe', 0), 3),
            'chained_OOS_CAGR': round(agg.get('chained_OOS_CAGR', 0) * 100, 2),
            'chained_OOS_maxdd': round(agg.get('chained_OOS_maxdd', 0) * 100, 2),
            'n_low_confidence': agg.get('n_low_confidence_windows', 0),
            'has_edge': agg.get('has_edge', False),
            'status': 'success'
        }
    except Exception as e:
        return {
            'threshold': threshold,
            'data_path': data_path,
            'status': 'error',
            'error': str(e)
        }


def main():
    print("=" * 90)
    print("VWAP STRATEGY MULTI-ASSET PARAMETER SWEEP")
    print("=" * 90)
    print(f"Started: {datetime.now().isoformat()}\n")

    # Thresholds to test
    thresholds = [0.005, 0.008, 0.010, 0.012, 0.015, 0.018, 0.020, 0.022, 0.025, 0.030, 0.035, 0.040]

    # Discover all data
    assets = discover_data_files()

    print(f"Discovered {len(assets)} assets:")
    for name, tfs in sorted(assets.items()):
        print(f"  {name}: {list(tfs.keys())}")

    # Filter to assets with sufficient data
    valid_assets = {}
    for name, tfs in assets.items():
        for tf, path in tfs.items():
            try:
                df = load_csv(path)
                if len(df) >= 3000:  # Minimum bars for walk-forward
                    if name not in valid_assets:
                        valid_assets[name] = {}
                    valid_assets[name][tf] = path
            except:
                pass

    print(f"\nValid assets with sufficient data: {len(valid_assets)}")

    # Build sweep configurations
    configs = []
    for name, tfs in sorted(valid_assets.items()):
        for tf, path in tfs.items():
            params = get_window_params(tf)
            for threshold in thresholds:
                configs.append({
                    'asset': name,
                    'timeframe': tf,
                    'data_path': path,
                    'threshold': threshold,
                    'train_bars': params['train_bars'],
                    'test_bars': params['test_bars'],
                    'step_bars': params['step_bars']
                })

    print(f"\nTotal sweep combinations: {len(configs)}")
    print("-" * 90)

    # Run sweep
    results = []
    total = len(configs)
    completed = 0

    for config in configs:
        completed += 1
        pct = (completed / total) * 100

        print(f"\n[{completed}/{total} ({pct:.1f}%)] "
              f"{config['asset']} | {config['timeframe']} | "
              f"threshold={config['threshold']:.3f} ({config['threshold']*100:.1f}%)")

        result = run_single_sweep(
            data_path=config['data_path'],
            threshold=config['threshold'],
            train_bars=config['train_bars'],
            test_bars=config['test_bars'],
            step_bars=config['step_bars']
        )

        result['asset'] = config['asset']
        result['timeframe'] = config['timeframe']
        results.append(result)

        if result['status'] == 'success':
            print(f"  OOS: {result['mean_OOS_sharpe']:+.3f} | "
                  f"Excess: {result['chained_OOS_excess_sharpe']:+.3f} | "
                  f"Deg: {result['degradation_ratio']:.3f} | "
                  f"Robust: {'✓' if result['robust'] else '✗'} | "
                  f"LowConf: {result['n_low_confidence']}/{result['n_windows']} | "
                  f"Edge: {'YES' if result['has_edge'] else 'NO'}")
        else:
            print(f"  ERROR: {result['error']}")

    # Filter successful
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'error']

    print(f"\n{'='*90}")
    print(f"SWEEP COMPLETE: {len(successful)} succeeded, {len(failed)} failed")
    print(f"{'='*90}")

    # Sort by excess Sharpe
    successful.sort(key=lambda x: x['chained_OOS_excess_sharpe'], reverse=True)

    # =========== TOP 10 OVERALL ===========
    print(f"\n{'='*90}")
    print(f"TOP 10 CANDIDATES OVERALL (by Chained OOS Excess Sharpe)")
    print(f"{'='*90}")
    print(f"{'Rank':>4} | {'Asset':>12} | {'TF':>3} | {'Thresh':>6} | {'Excess':>7} | {'OOS':>7} | {'Bench':>7} | "
          f"{'Degrad':>6} | {'Robust':>6} | {'LowConf':>7} | {'Edge':>4}")
    print("-" * 110)

    for i, r in enumerate(successful[:10], 1):
        print(f"{i:>4} | {r['asset']:>12} | {r['timeframe']:>3} | {r['threshold']*100:>5.1f}% | "
              f"{r['chained_OOS_excess_sharpe']:>+7.3f} | "
              f"{r['chained_OOS_sharpe']:>+7.3f} | "
              f"{r['chained_OOS_benchmark_sharpe']:>+7.3f} | "
              f"{r['degradation_ratio']:>6.3f} | "
              f"{'YES' if r['robust'] else 'NO':>6} | "
              f"{r['n_low_confidence']}/{r['n_windows']:>4} | "
              f"{'YES' if r['has_edge'] else 'NO':>4}")

    # =========== BY TIMEFRAME ===========
    for tf in ['1D', '4H']:
        tf_results = [r for r in successful if r['timeframe'] == tf]
        if not tf_results:
            continue
        tf_results.sort(key=lambda x: x['chained_OOS_excess_sharpe'], reverse=True)

        print(f"\n{'='*90}")
        print(f"TOP 10 {tf} CANDIDATES")
        print(f"{'='*90}")
        print(f"{'Rank':>4} | {'Asset':>12} | {'Thresh':>6} | {'Excess':>7} | {'OOS':>7} | {'Bench':>7} | "
              f"{'Degrad':>6} | {'Robust':>6} | {'LowConf':>7} | {'Edge':>4}")
        print("-" * 110)

        for i, r in enumerate(tf_results[:10], 1):
            print(f"{i:>4} | {r['asset']:>12} | {r['threshold']*100:>5.1f}% | "
                  f"{r['chained_OOS_excess_sharpe']:>+7.3f} | "
                  f"{r['chained_OOS_sharpe']:>+7.3f} | "
                  f"{r['chained_OOS_benchmark_sharpe']:>+7.3f} | "
                  f"{r['degradation_ratio']:>6.3f} | "
                  f"{'YES' if r['robust'] else 'NO':>6} | "
                  f"{r['n_low_confidence']}/{r['n_windows']:>4} | "
                  f"{'YES' if r['has_edge'] else 'NO':>4}")

    # =========== BY ASSET ===========
    print(f"\n{'='*90}")
    print(f"BEST PER ASSET (across all timeframes and thresholds)")
    print(f"{'='*90}")

    best_per_asset = {}
    for r in successful:
        key = r['asset']
        if key not in best_per_asset or r['chained_OOS_excess_sharpe'] > best_per_asset[key]['chained_OOS_excess_sharpe']:
            best_per_asset[key] = r

    sorted_assets = sorted(best_per_asset.values(), key=lambda x: x['chained_OOS_excess_sharpe'], reverse=True)

    print(f"{'Rank':>4} | {'Asset':>12} | {'Best TF':>4} | {'Thresh':>6} | {'Excess':>7} | {'OOS':>7} | {'Bench':>7} | "
          f"{'Degrad':>6} | {'Robust':>6} | {'LowConf':>7} | {'Edge':>4}")
    print("-" * 110)

    for i, r in enumerate(sorted_assets, 1):
        print(f"{i:>4} | {r['asset']:>12} | {r['timeframe']:>4} | {r['threshold']*100:>5.1f}% | "
              f"{r['chained_OOS_excess_sharpe']:>+7.3f} | "
              f"{r['chained_OOS_sharpe']:>+7.3f} | "
              f"{r['chained_OOS_benchmark_sharpe']:>+7.3f} | "
              f"{r['degradation_ratio']:>6.3f} | "
              f"{'YES' if r['robust'] else 'NO':>6} | "
              f"{r['n_low_confidence']}/{r['n_windows']:>4} | "
              f"{'YES' if r['has_edge'] else 'NO':>4}")

    # =========== SUMMARY ===========
    print(f"\n{'='*90}")
    print(f"SUMMARY")
    print(f"{'='*90}")

    best = successful[0] if successful else None
    if best:
        print(f"\n🥇 OVERALL BEST:")
        print(f"   {best['asset']} | {best['timeframe']} | threshold={best['threshold']*100:.1f}%")
        print(f"   Chained Excess Sharpe: {best['chained_OOS_excess_sharpe']:+.3f}")
        print(f"   Chained OOS Sharpe: {best['chained_OOS_sharpe']:+.3f}")
        print(f"   Chained Benchmark: {best['chained_OOS_benchmark_sharpe']:+.3f}")
        print(f"   Has Edge: {'YES' if best['has_edge'] else 'NO'}")

    # Positive OOS check
    positive_oos = [r for r in successful if r['chained_OOS_sharpe'] > 0]
    print(f"\n✅ Configurations with POSITIVE OOS Sharpe: {len(positive_oos)}")
    if positive_oos:
        for r in positive_oos[:10]:
            print(f"   {r['asset']} {r['timeframe']} {r['threshold']*100:.1f}%: "
                  f"Sharpe={r['chained_OOS_sharpe']:+.3f}, Excess={r['chained_OOS_excess_sharpe']:+.3f}")
    else:
        print("   ❌ NONE - all strategies have negative absolute performance")

    # Robust check
    robust = [r for r in successful if r['robust']]
    print(f"\n🛡️ Robust configurations: {len(robust)}")
    if robust:
        for r in robust[:10]:
            print(f"   {r['asset']} {r['timeframe']} {r['threshold']*100:.1f}%: "
                  f"Sharpe={r['chained_OOS_sharpe']:+.3f}, Excess={r['chained_OOS_excess_sharpe']:+.3f}")

    # Save results
    output = {
        'sweep_date': datetime.now().isoformat(),
        'strategy': '24_vwap_reversion.py',
        'thresholds_tested': thresholds,
        'assets_tested': list(valid_assets.keys()),
        'top_10_overall': successful[:10],
        'top_10_by_timeframe': {
            '1D': [r for r in successful if r['timeframe'] == '1D'][:10],
            '4H': [r for r in successful if r['timeframe'] == '4H'][:10]
        },
        'best_per_asset': {k: v for k, v in sorted_assets[:20]},
        'all_results': successful
    }

    out_path = Path('results/vwap_multi_asset_sweep_results.json')
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\n✅ JSON saved to {out_path}")

    df_results = pd.DataFrame(successful)
    csv_path = Path('results/vwap_multi_asset_sweep_results.csv')
    df_results.to_csv(csv_path, index=False)
    print(f"✅ CSV saved to {csv_path}")


if __name__ == "__main__":
    main()