# golden_cross_sweep_fast.py
#
# FAST Golden Cross research sweep for QuantForge.
#
# Purpose:
#   Explore many Golden Cross variations without running the full
#   BacktestEngine thousands of times.
#
# Workflow:
#
#   Stage 1  -> vectorized screening
#   Stage 2  -> full BacktestEngine validation for top candidates
#
# This leaves the existing engine/core.py and baseline strategy untouched.
#
# Run:
#
#   python -m execute.golden_cross_sweep_fast
#
# Recommended location:
#
#   execute/golden_cross_sweep_fast.py
#

from __future__ import annotations

from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd

from engine.data import load_csv
from engine.core import BacktestEngine
from engine.loader import validate_signals
from analytics.metrics import compute_metrics, extract_trades


# ============================================================
# CONFIGURATION
# ============================================================

DATA_DIRS = {
    # "daily": Path("data/raw/daily"),
    "fourhours": Path("data/raw/fourhours"),
    # "onehours": Path("data/raw/onehours"),
}

RESULTS_DIR = Path("results")

# Keep these moderate for the first fast screen.
FAST_PERIODS = [5, 10, 20, 30, 40, 50, 60, 75, 100]
SLOW_PERIODS = [50, 75, 100, 150, 200, 250, 300, 400, 500]

MODES = [
    "long_only",
    "long_short",
]

FILTERS = [
    "none",
    "price_slow",
    "slow_slope",
    "fast_slope",
    "combined",
]

BUFFERS = [
    0.0,
    0.001,   # 0.10%
    0.0025,  # 0.25%
    0.005,   # 0.50%
]

# Only these candidates go through the slower full engine.
TOP_N_FOR_ENGINE = 10

# Reject extremely small samples from the first-stage ranking.
MIN_SCREEN_TRADES = 10


# ============================================================
# TIMEFRAME-AWARE ANALYTICS
# ============================================================

def infer_periods_per_year(df: pd.DataFrame) -> float:
    """Estimate observations/year from actual timestamps."""

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
    """Return actual calendar duration represented by the dataset."""

    elapsed_seconds = (
        df.index[-1] - df.index[0]
    ).total_seconds()

    return elapsed_seconds / (
        365.2425 * 24 * 60 * 60
    )


# ============================================================
# PARAMETER GENERATION
# ============================================================

def parameter_grid():
    """
    Generate valid Golden Cross combinations.

    Returns tuples:
        (fast, slow, mode, filter, buffer)
    """

    for fast, slow, mode, filter_name, buffer in product(
        FAST_PERIODS,
        SLOW_PERIODS,
        MODES,
        FILTERS,
        BUFFERS,
    ):
        if fast >= slow:
            continue

        yield (
            fast,
            slow,
            mode,
            filter_name,
            buffer,
        )


# ============================================================
# PRECOMPUTE INDICATORS
# ============================================================

def precompute_smas(
    close: pd.Series,
) -> dict[int, pd.Series]:
    """
    Calculate each requested SMA exactly once.

    This is one of the major speed improvements over the original
    sweep, where every parameter combination recalculated the SMA.
    """

    periods = sorted(
        set(FAST_PERIODS + SLOW_PERIODS)
    )

    return {
        n: close.rolling(
            n,
            min_periods=n,
        ).mean()
        for n in periods
    }


# ============================================================
# VECTORISED SIGNAL
# ============================================================

def build_signal(
    df: pd.DataFrame,
    smas: dict[int, pd.Series],
    fast: int,
    slow: int,
    mode: str,
    filter_name: str,
    buffer: float,
) -> pd.Series:

    close = df["close"]

    fast_sma = smas[fast]
    slow_sma = smas[slow]

    fast_slope = fast_sma.diff()
    slow_slope = slow_sma.diff()

    # --------------------------------------------------------
    # Crossover state with optional buffer.
    # --------------------------------------------------------

    long_condition = (
        fast_sma
        > slow_sma * (1.0 + buffer)
    )

    short_condition = (
        fast_sma
        < slow_sma * (1.0 - buffer)
    )

    # --------------------------------------------------------
    # Filters.
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

        long_filter = close > slow_sma
        short_filter = close < slow_sma

    elif filter_name == "slow_slope":

        long_filter = slow_slope > 0
        short_filter = slow_slope < 0

    elif filter_name == "fast_slope":

        long_filter = fast_slope > 0
        short_filter = fast_slope < 0

    elif filter_name == "combined":

        long_filter = (
            (close > slow_sma)
            & (slow_slope > 0)
            & (fast_slope > 0)
        )

        short_filter = (
            (close < slow_sma)
            & (slow_slope < 0)
            & (fast_slope < 0)
        )

    else:
        raise ValueError(
            f"Unknown filter: {filter_name}"
        )

    sig = pd.Series(
        0.0,
        index=df.index,
        dtype=float,
    )

    if mode == "long_only":

        sig[long_condition & long_filter] = 1.0

    elif mode == "long_short":

        sig[long_condition & long_filter] = 1.0
        sig[short_condition & short_filter] = -1.0

    else:
        raise ValueError(
            f"Unknown mode: {mode}"
        )

    warmup = slow

    sig.iloc[:warmup] = 0.0

    return sig


# ============================================================
# FAST SCREEN
# ============================================================

def fast_screen_one(
    df: pd.DataFrame,
    timeframe: str,
    asset: str,
    smas: dict[int, pd.Series],
    params: tuple,
    ppy: float,
    elapsed_years: float,
) -> dict | None:
    """
    Fast first-stage screen.

    Instead of running BacktestEngine, approximate portfolio returns
    directly from target weights and next-bar close-to-close returns.

    IMPORTANT:
      This is a SCREENING MODEL ONLY.

    It is deliberately used to select candidates for Stage 2.
    Final results always come from the real BacktestEngine.
    """

    fast, slow, mode, filter_name, buffer = params

    try:

        sig = build_signal(
            df,
            smas,
            fast,
            slow,
            mode,
            filter_name,
            buffer,
        )

        # ----------------------------------------------------
        # Next-bar execution approximation.
        #
        # Signal at t affects return t+1.
        #
        # We use close-to-close return here only for screening.
        # Slippage and commission are approximated by turnover.
        # ----------------------------------------------------

        close = df["close"]

        asset_return = (
            close.pct_change()
            .fillna(0.0)
        )

        position = sig.shift(1).fillna(0.0)

        gross_returns = (
            position * asset_return
        )

        # Position changes create turnover.
        turnover = (
            position.diff()
            .abs()
            .fillna(position.abs())
        )

        # Approximate round-trip implementation costs.
        #
        # 1 bp commission + 5 bp slippage per unit of absolute
        # weight change.
        estimated_cost = (
            turnover * 0.0006
        )

        net_returns = (
            gross_returns
            - estimated_cost
        )

        equity = (
            100_000
            * (1.0 + net_returns)
            .cumprod()
        )

        # ----------------------------------------------------
        # Metrics used only for screening.
        # ----------------------------------------------------

        valid_returns = net_returns.replace(
            [np.inf, -np.inf],
            np.nan,
        ).dropna()

        if len(valid_returns) < 2:
            return None

        total_return = (
            equity.iloc[-1]
            / equity.iloc[0]
            - 1.0
        )

        years = elapsed_years

        cagr = (
            (equity.iloc[-1] / equity.iloc[0])
            ** (1.0 / years)
            - 1.0
            if years > 0 and equity.iloc[-1] > 0
            else np.nan
        )

        volatility = (
            valid_returns.std(ddof=1)
            * np.sqrt(ppy)
        )

        if volatility > 0:
            sharpe = (
                valid_returns.mean()
                * ppy
                / volatility
            )
        else:
            sharpe = np.nan

        running_max = equity.cummax()

        drawdown = (
            equity / running_max
            - 1.0
        )

        max_dd = drawdown.min()

        if max_dd < 0:
            calmar = cagr / abs(max_dd)
        else:
            calmar = np.nan

        # Count position transitions as an approximate number of
        # completed trading events for sample-size screening.
        transitions = (
            (position != position.shift(1))
            & position.notna()
        )

        approx_trades = int(
            transitions.sum()
        )

        return {
            "asset": asset,
            "timeframe": timeframe,
            "fast": fast,
            "slow": slow,
            "mode": mode,
            "filter": filter_name,
            "buffer": buffer,
            "CAGR_screen": float(cagr),
            "sharpe_screen": float(sharpe),
            "calmar_screen": float(calmar),
            "max_drawdown_screen": float(max_dd),
            "total_return_screen": float(total_return),
            "approx_trades": approx_trades,
        }

    except Exception:
        return None


# ============================================================
# STAGE 2 — REAL ENGINE VALIDATION
# ============================================================

def full_engine_validate(
    df: pd.DataFrame,
    row: dict,
) -> dict | None:

    fast = int(row["fast"])
    slow = int(row["slow"])
    mode = row["mode"]
    filter_name = row["filter"]
    buffer = float(row["buffer"])

    try:

        close = df["close"]

        # We recalculate only the two SMAs required for this
        # candidate. Stage 1 already did the cheap screening.
        smas = {
            fast: close.rolling(
                fast,
                min_periods=fast,
            ).mean(),
            slow: close.rolling(
                slow,
                min_periods=slow,
            ).mean(),
        }

        signals = build_signal(
            df,
            smas,
            fast,
            slow,
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

        ppy = infer_periods_per_year(df)
        elapsed_years = infer_elapsed_years(df)

        metrics = compute_metrics(
            equity,
            rf_annual=0.04,
            periods_per_year=ppy,
            elapsed_years=elapsed_years,
            trades=trades,
        )

        validated = dict(row)

        validated.update(
            {
                "CAGR": metrics.get("CAGR"),
                "volatility": metrics.get("volatility"),
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
        )

        return validated

    except Exception as e:

        print(
            f"❌ Full validation failed: "
            f"{row['asset']} | "
            f"{row['timeframe']} | "
            f"{row['fast']}/{row['slow']} | "
            f"{row['mode']} | "
            f"{row['filter']} | "
            f"{row['buffer']}: {e}"
        )

        return None


# ============================================================
# RANK SCREEN
# ============================================================

def rank_screen(
    df: pd.DataFrame,
) -> pd.DataFrame:

    data = df.copy()

    # Only rank candidates with enough approximate events.
    data = data[
        data["approx_trades"]
        >= MIN_SCREEN_TRADES
    ].copy()

    if data.empty:
        return data

    # --------------------------------------------------------
    # Rank each metric.
    #
    # Percentile ranks prevent one metric from dominating
    # purely because of its numerical scale.
    # --------------------------------------------------------

    data["rank_sharpe"] = data[
        "sharpe_screen"
    ].rank(
        pct=True,
        ascending=True,
        method="average",
    )

    data["rank_calmar"] = data[
        "calmar_screen"
    ].rank(
        pct=True,
        ascending=True,
        method="average",
    )

    data["rank_cagr"] = data[
        "CAGR_screen"
    ].rank(
        pct=True,
        ascending=True,
        method="average",
    )

    data["rank_drawdown"] = (
        -data["max_drawdown_screen"]
    ).rank(
        pct=True,
        ascending=True,
        method="average",
    )

    # --------------------------------------------------------
    # Screen score.
    # --------------------------------------------------------

    data["screen_score"] = (
        0.40 * data["rank_sharpe"]
        + 0.25 * data["rank_calmar"]
        + 0.20 * data["rank_cagr"]
        + 0.15 * data["rank_drawdown"]
    )

    return data.sort_values(
        [
            "screen_score",
            "sharpe_screen",
            "CAGR_screen",
        ],
        ascending=False,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    params = list(
        parameter_grid()
    )

    print("=" * 90)
    print("QUANTFORGE FAST GOLDEN CROSS SWEEP")
    print("=" * 90)

    print(
        f"Parameter combinations: "
        f"{len(params):,}"
    )

    print(
        f"Top candidates sent to full engine per dataset: "
        f"{TOP_N_FOR_ENGINE}"
    )

    print("=" * 90)

    master_rows = []

    for timeframe, data_dir in DATA_DIRS.items():

        data_files = sorted(
            data_dir.glob("*.csv")
        )

        for data_path in data_files:

            print(
                f"\n[{timeframe}] {data_path.name}"
            )

            try:
                df = load_csv(
                    data_path
                )
            except Exception as e:
                print(
                    f"❌ Load failed: {e}"
                )
                continue

            ppy = infer_periods_per_year(
                df
            )

            elapsed_years = infer_elapsed_years(
                df
            )

            # ------------------------------------------------
            # Precompute all SMAs exactly once.
            # ------------------------------------------------

            smas = precompute_smas(
                df["close"]
            )

            # ------------------------------------------------
            # Stage 1
            # ------------------------------------------------

            screen_rows = []

            for p in params:

                row = fast_screen_one(
                    df,
                    timeframe,
                    data_path.stem,
                    smas,
                    p,
                    ppy,
                    elapsed_years,
                )

                if row is not None:
                    screen_rows.append(row)

            if not screen_rows:
                print(
                    "❌ No screen results."
                )
                continue

            screen_df = pd.DataFrame(
                screen_rows
            )

            ranked = rank_screen(
                screen_df
            )

            if ranked.empty:
                print(
                    "❌ No candidates met "
                    f"MIN_SCREEN_TRADES={MIN_SCREEN_TRADES}"
                )
                continue

            # ------------------------------------------------
            # Stage 2
            # ------------------------------------------------

            candidates = ranked.head(
                TOP_N_FOR_ENGINE
            )

            validated_rows = []

            print(
                f"Stage 1 complete: "
                f"{len(screen_df):,} variants"
            )

            print(
                f"Stage 2: validating top "
                f"{len(candidates)} candidates with BacktestEngine..."
            )

            for _, candidate in candidates.iterrows():

                result = full_engine_validate(
                    df,
                    candidate.to_dict(),
                )

                if result is not None:

                    result[
                        "screen_rank"
                    ] = int(
                        candidate.name + 1
                        if isinstance(candidate.name, int)
                        else 0
                    )

                    validated_rows.append(
                        result
                    )

            # ------------------------------------------------
            # Save per-dataset results.
            # ------------------------------------------------

            if validated_rows:

                validated_df = pd.DataFrame(
                    validated_rows
                )

                validated_df = validated_df.sort_values(
                    [
                        "sharpe",
                        "CAGR",
                    ],
                    ascending=False,
                )

                dataset_output = (
                    RESULTS_DIR
                    / (
                        f"golden_cross_fast_"
                        f"{timeframe}_"
                        f"{data_path.stem}.csv"
                    )
                )

                validated_df.to_csv(
                    dataset_output,
                    index=False,
                )

                master_rows.extend(
                    validated_rows
                )

                print(
                    f"✅ Saved validated results → "
                    f"{dataset_output}"
                )

                print(
                    "\nTop validated candidates:"
                )

                print(
                    validated_df[
                        [
                            "fast",
                            "slow",
                            "mode",
                            "filter",
                            "buffer",
                            "CAGR",
                            "sharpe",
                            "sortino",
                            "calmar",
                            "max_drawdown",
                            "num_trades",
                            "win_rate",
                            "profit_factor",
                        ]
                    ]
                    .head(5)
                    .to_string(index=False)
                )

    # ========================================================
    # MASTER RESULTS
    # ========================================================

    if not master_rows:

        print(
            "\n❌ No validated results."
        )
        return

    master = pd.DataFrame(
        master_rows
    )

    master_output = (
        RESULTS_DIR
        / "golden_cross_sweep_fast.csv"
    )

    master.to_csv(
        master_output,
        index=False,
    )

    print("\n" + "=" * 90)
    print("FAST GOLDEN CROSS SWEEP COMPLETE")
    print("=" * 90)

    print(
        f"Validated backtests: "
        f"{len(master):,}"
    )

    print(
        f"Master results: "
        f"{master_output}"
    )

    # --------------------------------------------------------
    # Overall best candidates by timeframe.
    # --------------------------------------------------------

    for timeframe in DATA_DIRS:

        subset = master[
            master["timeframe"]
            == timeframe
        ]

        if subset.empty:
            continue

        print(
            f"\nTOP {timeframe.upper()} VALIDATED CANDIDATES"
        )

        print(
            subset[
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
            ]
            .sort_values(
                [
                    "sharpe",
                    "CAGR",
                ],
                ascending=False,
            )
            .head(15)
            .to_string(index=False)
        )


if __name__ == "__main__":
    main()
