"""
VWAP Strategy Parameter Sweep

Tests VWAP mean reversion across multiple thresholds on 1D and 4H data.
Ranks top 10 candidates by OOS excess Sharpe (walk-forward).

Usage:
    python -m execute.vwap_sweep
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime

import pandas as pd

from engine.config import load_config
from engine.data import load_csv, cache
from engine.loader import load_strategy
from validation.walk_forward import walk_forward, windows_to_dataframe


def run_single_sweep(data_path: str, threshold: float, train_bars: int = 756,
                     test_bars: int = 252, step_bars: int = 126) -> dict:
    """Run one VWAP sweep configuration."""
    try:
        # Load data
        df = load_csv(data_path)
        cache(df, data_path)

        # Load strategy
        fn = load_strategy('strategies/24_vwap_reversion.py')

        engine_params = {
            'initial_cash': 100000,
            'commission_bps': 1.0,
            'slippage_bps': 5.0,
            'no_trade_band': 0.01,
            'warmup_bars': 0
        }

        # Run walk-forward
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
            'timeframe': '1D' if '1D' in data_path else '4H',
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
            'timeframe': '1D' if '1D' in data_path else '4H',
            'status': 'error',
            'error': str(e)
        }


def main():
    print("=" * 80)
    print("VWAP STRATEGY PARAMETER SWEEP")
    print("=" * 80)
    print(f"Started: {datetime.now().isoformat()}\n")

    # Define sweep configurations
    thresholds = [0.005, 0.008, 0.010, 0.012, 0.015, 0.018, 0.020, 0.022, 0.025, 0.030, 0.035, 0.040]

    # Data paths for different timeframes
    data_configs = [
        ('data/raw/daily/xauusd_1D_comma.csv', '1D'),
        ('data/raw/fourhours/xauusd_4H_comma.csv', '4H'),
    ]

    # Filter to only existing files
    available_data = []
    for path, tf in data_configs:
        if Path(path).exists():
            available_data.append((path, tf))
            print(f"✓ Found {tf} data: {path}")
        else:
            print(f"✗ Missing {tf} data: {path}")

    if not available_data:
        print("\n❌ No data files found!")
        return

    print(f"\nSweep space: {len(thresholds)} thresholds × {len(available_data)} timeframes = {len(thresholds) * len(available_data)} combinations")
    print("-" * 80)

    # Run sweep
    results = []
    total = len(thresholds) * len(available_data)
    completed = 0

    for data_path, tf in available_data:
        print(f"\n{'='*80}")
        print(f"TIMEFRAME: {tf} ({data_path})")
        print(f"{'='*80}")

        # Determine window sizes based on timeframe
        if tf == '1D':
            train_bars, test_bars, step_bars = 756, 252, 126  # 3y/1y/6m
        else:  # 4H
            # ~6 bars per day, ~1500 bars per year
            train_bars, test_bars, step_bars = 4500, 1500, 750  # ~3y/1y/6m in 4H bars

        for threshold in thresholds:
            completed += 1
            print(f"\n[{completed}/{total}] {tf} | threshold={threshold:.3f} ({threshold*100:.1f}%)")

            result = run_single_sweep(
                data_path=data_path,
                threshold=threshold,
                train_bars=train_bars,
                test_bars=test_bars,
                step_bars=step_bars
            )
            results.append(result)

            if result['status'] == 'success':
                print(f"  OOS Sharpe: {result['mean_OOS_sharpe']:+.3f} | "
                      f"Excess: {result['chained_OOS_excess_sharpe']:+.3f} | "
                      f"Degradation: {result['degradation_ratio']:.3f} | "
                      f"Robust: {'✓' if result['robust'] else '✗'} | "
                      f"Low-conf: {result['n_low_confidence']}/{result['n_windows']}")
            else:
                print(f"  ERROR: {result['error']}")

    # Filter successful results
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'error']

    print(f"\n{'='*80}")
    print(f"SWEEP COMPLETE: {len(successful)} succeeded, {len(failed)} failed")
    print(f"{'='*80}")

    # Rank by chained OOS excess Sharpe (descending)
    successful.sort(key=lambda x: x['chained_OOS_excess_sharpe'], reverse=True)

    # Top 10
    print(f"\n{'='*80}")
    print(f"TOP 10 CANDIDATES (by Chained OOS Excess Sharpe)")
    print(f"{'='*80}")

    # Header
    print(f"{'Rank':>4} | {'TF':>3} | {'Thresh':>6} | {'Excess':>7} | {'OOS':>7} | {'Bench':>7} | "
          f"{'Degrad':>6} | {'Robust':>6} | {'LowConf':>7} | {'Edge':>4}")
    print("-" * 100)

    for i, r in enumerate(successful[:10], 1):
        print(f"{i:>4} | {r['timeframe']:>3} | {r['threshold']*100:>5.1f}% | "
              f"{r['chained_OOS_excess_sharpe']:>+7.3f} | "
              f"{r['chained_OOS_sharpe']:>+7.3f} | "
              f"{r['chained_OOS_benchmark_sharpe']:>+7.3f} | "
              f"{r['degradation_ratio']:>6.3f} | "
              f"{'YES' if r['robust'] else 'NO':>6} | "
              f"{r['n_low_confidence']}/{r['n_windows']:>4} | "
              f"{'YES' if r['has_edge'] else 'NO':>4}")

    # Full results table
    print(f"\n{'='*80}")
    print(f"ALL RESULTS")
    print(f"{'='*80}")
    for r in successful:
        print(f"{r['timeframe']:>3} | {r['threshold']*100:>5.1f}% | "
              f"Excess:{r['chained_OOS_excess_sharpe']:>+7.3f} | "
              f"OOS:{r['chained_OOS_sharpe']:>+7.3f} | "
              f"Bench:{r['chained_OOS_benchmark_sharpe']:>+7.3f} | "
              f"Deg:{r['degradation_ratio']:.3f} | "
              f"Robust:{'✓' if r['robust'] else '✗'} | "
              f"LC:{r['n_low_confidence']}/{r['n_windows']}")

    # Save results
    output = {
        'sweep_date': datetime.now().isoformat(),
        'strategy': '24_vwap_reversion.py',
        'thresholds_tested': thresholds,
        'timeframes': [tf for _, tf in available_data],
        'top_10': successful[:10],
        'all_results': successful
    }

    out_path = Path('results/vwap_sweep_results.json')
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\n✅ Results saved to {out_path}")

    # Save as CSV for easy viewing
    df_results = pd.DataFrame(successful)
    csv_path = Path('results/vwap_sweep_results.csv')
    df_results.to_csv(csv_path, index=False)
    print(f"✅ CSV saved to {csv_path}")

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    best = successful[0] if successful else None
    if best:
        print(f"Best: {best['timeframe']} threshold={best['threshold']*100:.1f}%")
        print(f"  Chained Excess Sharpe: {best['chained_OOS_excess_sharpe']:+.3f}")
        print(f"  Chained OOS Sharpe: {best['chained_OOS_sharpe']:+.3f}")
        print(f"  Chained Benchmark: {best['chained_OOS_benchmark_sharpe']:+.3f}")

        # Check if any have positive absolute performance
        positive_oos = [r for r in successful if r['chained_OOS_sharpe'] > 0]
        print(f"\nConfigurations with POSITIVE OOS Sharpe: {len(positive_oos)}")
        if positive_oos:
            for r in positive_oos[:5]:
                print(f"  {r['timeframe']} {r['threshold']*100:.1f}%: Sharpe={r['chained_OOS_sharpe']:+.3f}, "
                      f"Excess={r['chained_OOS_excess_sharpe']:+.3f}")
        else:
            print("  ❌ NONE - all strategies have negative absolute performance")

        # Check robust configs
        robust = [r for r in successful if r['robust']]
        print(f"\nRobust configurations (degradation ≥0.5, positive OOS): {len(robust)}")
        if robust:
            for r in robust[:5]:
                print(f"  {r['timeframe']} {r['threshold']*100:.1f}%: Sharpe={r['chained_OOS_sharpe']:+.3f}")


if __name__ == "__main__":
    main()