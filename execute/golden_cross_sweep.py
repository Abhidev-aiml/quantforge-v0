# golden_cross_sweep.py
#
# QuantForge research-only Golden Cross parameter sweep.
#
# IMPORTANT:
#   - Existing strategies/01_goldencross.py remains untouched.
#   - This script is for research/experimentation.
#   - It tests a structured first-stage grid rather than brute-force
#     optimization across thousands of combinations.
#
# Run from the project root:
#
#   python -m execute.golden_cross_sweep
#
# Recommended location:
#
#   execute/golden_cross_sweep.py
#
# Output:
#
#   results/golden_cross_sweep.csv
#

from __future__ import annotations

from pathlib import Path

import pandas as pd

from engine.data import load_csv
from engine.core import BacktestEngine
from engine.loader import validate_signals
from analytics.metrics import compute_metrics, extract_trades


# ============================================================
# CONFIGURATION
# ============================================================

DATA_DIRS = {
    "daily": Path("data/raw/daily"),
    "fourhours": Path("data/raw/fourhours"),
    "onehours": Path("data/raw/onehours"),
}

RESULTS_DIR = Path("results")


# First-stage structured parameter grid.
FAST_PERIODS = [
    5,
    10,
    20,
    30,
    40,
    50,
    60,
    75,
    100,
]

SLOW_PERIODS = [
    50,
    75,
    100,
    150,
    200,
    250,
    300,
    400,
    500,
]

# Test both directions.
MODES = [
    "long_only",
    "long_short",
]

# Confirmation filters.
FILTERS = [
    "none",
    "price_slow",
    "slow_slope",
    "fast_slope",
    "combined",
]

# Small crossover buffer/hysteresis.
BUFFERS = [
    0.0,
    0.001,   # 0.10%
    0.0025,  # 0.25%
    0.005,   # 0.50%
]


# ============================================================
# TIMEFRAME-AWARE ANALYTICS
# ============================================================

def infer_periods_per_year(df: pd.DataFrame) -> float:
    """
    Estimate observations/year from the actual timestamp span.

    Used for annualized volatility, Sharpe and Sortino.
    """

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(
            "DataFrame index must be a DatetimeIndex."
        )

    if len(df.index) < 2:
        raise ValueError(
            "Need at least 2 timestamps."
        )

    elapsed_seconds = (
        df.index[-1] - df.index[0]
    ).total_seconds()

    if elapsed_seconds <= 0:
        raise ValueError(
            "Data timestamps must be increasing."
        )

    years = elapsed_seconds / (
        365.2425 * 24 * 60 * 60
    )

    return (len(df) - 1) / years


def infer_elapsed_years(df: pd.DataFrame) -> float:
    """Return actual calendar years represented by the dataset."""

    elapsed_seconds = (
        df.index[-1] - df.index[0]
    ).total_seconds()

    return elapsed_seconds / (
        365.2425 * 24 * 60 * 60
    )


# ============================================================
# GOLDEN CROSS SIGNAL
# ============================================================

def generate_signals(
    df: pd.DataFrame,
    fast_n: int,
    slow_n: int,
    mode: str,
    filter_name: str,
    buffer: float,
) -> pd.Series:
    """
    Generate +1 / 0 / -1 Golden Cross target weights.

    Baseline:
        fast SMA > slow SMA -> long

    Long/short:
        fast SMA > slow SMA -> long
        fast SMA < slow SMA -> short

    Buffer:
        A small percentage gap can reduce churning around
        the crossover.

    Important:
        The strategy only generates target weights.
        BacktestEngine handles next-bar execution.
    """

    if fast_n >= slow_n:
        raise ValueError(
            f"fast_n ({fast_n}) must be < slow_n ({slow_n})"
        )

    close = df["close"]

    fast = close.rolling(
        fast_n,
        min_periods=fast_n,
    ).mean()

    slow = close.rolling(
        slow_n,
        min_periods=slow_n,
    ).mean()

    fast_slope = fast.diff()
    slow_slope = slow.diff()

    # --------------------------------------------------------
    # Directional crossover with optional buffer.
    # --------------------------------------------------------

    long_condition = (
        fast > slow * (1.0 + buffer)
    )

    short_condition = (
        fast < slow * (1.0 - buffer)
    )

    # --------------------------------------------------------
    # Confirmation filters.
    # --------------------------------------------------------

    if filter_name == "none":

        long_filter = pd.Series(
            True,
            index=df.index,
        )

        short_filter = pd.Series(
            True,
            index=df.index,
        )

    elif filter_name == "price_slow":

        long_filter = (
            close > slow
        )

        short_filter = (
            close < slow
        )

    elif filter_name == "slow_slope":

        long_filter = (
            slow_slope > 0
        )

        short_filter = (
            slow_slope < 0
        )

    elif filter_name == "fast_slope":

        long_filter = (
            fast_slope > 0
        )

        short_filter = (
            fast_slope < 0
        )

    elif filter_name == "combined":

        long_filter = (
            (close > slow)
            & (slow_slope > 0)
            & (fast_slope > 0)
        )

        short_filter = (
            (close < slow)
            & (slow_slope < 0)
            & (fast_slope < 0)
        )

    else:
        raise ValueError(
            f"Unknown filter: {filter_name}"
        )

    long_signal = (
        long_condition
        & long_filter
    )

    short_signal = (
        short_condition
        & short_filter
    )

    sig = pd.Series(
        0.0,
        index=df.index,
        dtype=float,
    )

    if mode == "long_only":

        sig[long_signal] = 1.0

    elif mode == "long_short":

        sig[long_signal] = 1.0
        sig[short_signal] = -1.0

    else:
        raise ValueError(
            f"Unknown mode: {mode}"
        )

    # --------------------------------------------------------
    # Warm-up bars remain flat until both SMAs are available.
    # --------------------------------------------------------

    warmup = max(
        fast_n,
        slow_n,
    )

    sig.iloc[:warmup] = 0.0

    return sig


# ============================================================
# ONE BACKTEST
# ============================================================

def run_one(
    df: pd.DataFrame,
    timeframe: str,
    asset: str,
    fast_n: int,
    slow_n: int,
    mode: str,
    filter_name: str,
    buffer: float,
) -> dict | None:

    try:

        signals = generate_signals(
            df,
            fast_n,
            slow_n,
            mode,
            filter_name,
            buffer,
        )

        signals = validate_signals(
            signals,
            df,
        )

        engine = BacktestEngine(
            initial_cash=100_000,
            commission_bps=1,
            slippage_bps=5,
        )

        equity = engine.run(
            df,
            signals,
        )

        trades = extract_trades(
            engine.pf.fills
        )

        ppy = infer_periods_per_year(
            df
        )

        elapsed_years = infer_elapsed_years(
            df
        )

        metrics = compute_metrics(
            equity,
            rf_annual=0.04,
            periods_per_year=ppy,
            elapsed_years=elapsed_years,
            trades=trades,
        )

        return {
            "asset": asset,
            "timeframe": timeframe,
            "fast": fast_n,
            "slow": slow_n,
            "mode": mode,
            "filter": filter_name,
            "buffer": buffer,
            "CAGR": metrics.get("CAGR"),
            "sharpe": metrics.get("sharpe"),
            "sortino": metrics.get("sortino"),
            "calmar": metrics.get("calmar"),
            "max_drawdown": metrics.get(
                "max_drawdown"
            ),
            "num_trades": metrics.get(
                "num_trades",
                0,
            ),
            "win_rate": metrics.get(
                "win_rate"
            ),
            "profit_factor": metrics.get(
                "profit_factor"
            ),
            "expectancy": metrics.get(
                "expectancy"
            ),
        }

    except Exception as e:

        print(
            f"❌ {asset} | {timeframe} | "
            f"{fast_n}/{slow_n} | "
            f"{mode} | {filter_name} | "
            f"{buffer:.4f}: {e}"
        )

        return None


# ============================================================
# RANKING
# ============================================================

def rank_results(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a simple research score.

    This is NOT a performance truth score. It is only a way
    to surface candidates for deeper investigation.

    Weighting deliberately favors risk-adjusted metrics:
        Sharpe  40%
        Calmar  25%
        CAGR    20%
        PF      15%

    Candidates with fewer than 20 trades are marked low-sample.
    """

    result = df.copy()

    # Normalize only within this sweep output.
    def safe_rank(series, ascending=True):
        return series.rank(
            pct=True,
            ascending=ascending,
            method="average",
        )

    result["sharpe_rank"] = safe_rank(
        result["sharpe"],
        ascending=True,
    )

    result["calmar_rank"] = safe_rank(
        result["calmar"],
        ascending=True,
    )

    result["cagr_rank"] = safe_rank(
        result["CAGR"],
        ascending=True,
    )

    result["pf_rank"] = safe_rank(
        result["profit_factor"],
        ascending=True,
    )

    result["research_score"] = (
        0.40 * result["sharpe_rank"]
        + 0.25 * result["calmar_rank"]
        + 0.20 * result["cagr_rank"]
        + 0.15 * result["pf_rank"]
    )

    result["low_sample"] = (
        result["num_trades"] < 20
    )

    return result.sort_values(
        [
            "research_score",
            "sharpe",
            "CAGR",
        ],
        ascending=False,
    )


# ============================================================
# MAIN SWEEP
# ============================================================

def main():

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_rows = []

    total_parameter_sets = 0

    for fast in FAST_PERIODS:
        for slow in SLOW_PERIODS:
            if fast >= slow:
                continue

            for mode in MODES:
                for filter_name in FILTERS:
                    for buffer in BUFFERS:
                        total_parameter_sets += 1

    print("=" * 80)
    print("QUANTFORGE GOLDEN CROSS RESEARCH SWEEP")
    print("=" * 80)

    print(
        f"Parameter variants per dataset: "
        f"{total_parameter_sets}"
    )

    print(
        f"Timeframes: {len(DATA_DIRS)}"
    )

    print(
        "This is a research sweep; "
        "existing strategies are unchanged."
    )

    print("=" * 80)

    for timeframe, data_dir in DATA_DIRS.items():

        data_files = sorted(
            data_dir.glob("*.csv")
        )

        print(
            f"\n{timeframe.upper()}: "
            f"{len(data_files)} datasets"
        )

        for data_path in data_files:

            try:
                df = load_csv(
                    data_path
                )
            except Exception as e:
                print(
                    f"❌ Could not load "
                    f"{data_path}: {e}"
                )
                continue

            asset = data_path.stem

            print(
                f"\nRunning {asset} "
                f"({len(df):,} bars)"
            )

            dataset_rows = []

            for fast in FAST_PERIODS:

                for slow in SLOW_PERIODS:

                    if fast >= slow:
                        continue

                    for mode in MODES:

                        for filter_name in FILTERS:

                            for buffer in BUFFERS:

                                row = run_one(
                                    df,
                                    timeframe,
                                    asset,
                                    fast,
                                    slow,
                                    mode,
                                    filter_name,
                                    buffer,
                                )

                                if row is not None:
                                    dataset_rows.append(row)

            if not dataset_rows:
                continue

            dataset_df = pd.DataFrame(
                dataset_rows
            )

            ranked = rank_results(
                dataset_df
            )

            # Save each dataset separately.
            dataset_output = (
                RESULTS_DIR
                / f"golden_cross_{timeframe}_{asset}.csv"
            )

            ranked.to_csv(
                dataset_output,
                index=False,
            )

            print(
                f"✅ Saved {len(ranked):,} results → "
                f"{dataset_output}"
            )

            print(
                "\nTop 5 candidates:"
            )

            preview_cols = [
                "fast",
                "slow",
                "mode",
                "filter",
                "buffer",
                "CAGR",
                "sharpe",
                "calmar",
                "max_drawdown",
                "num_trades",
                "profit_factor",
                "research_score",
            ]

            print(
                ranked[
                    preview_cols
                ]
                .head(5)
                .to_string(index=False)
            )

            all_rows.extend(
                ranked.to_dict(
                    orient="records"
                )
            )

    # ========================================================
    # MASTER OUTPUT
    # ========================================================

    if not all_rows:
        print(
            "\n❌ No successful backtests."
        )
        return

    master = pd.DataFrame(
        all_rows
    )

    master_path = (
        RESULTS_DIR
        / "golden_cross_sweep.csv"
    )

    master.to_csv(
        master_path,
        index=False,
    )

    print("\n" + "=" * 80)
    print("SWEEP COMPLETE")
    print("=" * 80)

    print(
        f"Total successful backtests: "
        f"{len(master):,}"
    )

    print(
        f"Master results: {master_path}"
    )

    # --------------------------------------------------------
    # Overall candidates by timeframe
    # --------------------------------------------------------

    for timeframe in DATA_DIRS:

        subset = master[
            master["timeframe"]
            == timeframe
        ]

        if subset.empty:
            continue

        top = (
            subset[
                ~subset["low_sample"]
            ]
            .sort_values(
                "research_score",
                ascending=False,
            )
            .head(10)
        )

        print(
            f"\nTOP {timeframe.upper()} "
            "CANDIDATES (20+ trades):"
        )

        print(
            top[
                [
                    "asset",
                    "fast",
                    "slow",
                    "mode",
                    "filter",
                    "buffer",
                    "CAGR",
                    "sharpe",
                    "calmar",
                    "max_drawdown",
                    "num_trades",
                    "profit_factor",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
