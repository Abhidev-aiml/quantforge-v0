# # run_all.py

# import json
# from pathlib import Path
# import pandas as pd

# from engine.data import load_csv
# from engine.core import BacktestEngine
# from engine.loader import load_strategy, validate_signals
# from analytics.metrics import compute_metrics, extract_trades


# # ============================================================
# # CHANGED: Automatically find all strategy files
# # ============================================================
# #
# # Only numbered .py files are considered strategies.
# #
# # This includes:
# #   01_goldencross.py
# #   02_emacross.py
# #   ...
# #   10_roc_momentum.py
# #
# # It automatically ignores helper files such as:
# #   indicators.py
# #
# STRATEGIES = sorted(
#     [
#         str(path)
#         for path in Path("strategies").glob("*.py")
#         if path.stem[:2].isdigit()
#     ]
# )


# def run_one(df, path):

#     try:

#         fn = load_strategy(path)

#         sig = validate_signals(
#             fn(df),
#             df
#         )

#         eng = BacktestEngine(
#             initial_cash=100_000,
#             commission_bps=1,
#             slippage_bps=5
#         )

#         eq = eng.run(
#             df,
#             sig
#         )

#         trades = extract_trades(
#             eng.pf.fills
#         )

#         m = compute_metrics(
#             eq,
#             rf_annual=0.04,
#             trades=trades
#         )

#         return m

#     except Exception as e:

#         print(
#             f"❌ {path}: {e}"
#         )

#         return None


# # ============================================================
# # CHANGED:
# # main() now automatically finds ALL CSV files in
# # data/raw/daily/
# # ============================================================

# def main():

#     data_dir = Path("data/raw/onehours")

#     data_files = sorted(
#         data_dir.glob("*.csv")
#     )

#     if not data_files:

#         raise FileNotFoundError(
#             f"No CSV files found in {data_dir}"
#         )

#     print(
#         f"\nFound {len(data_files)} datasets."
#     )

#     print(
#         f"Found {len(STRATEGIES)} strategies."
#     )

#     print(
#         f"Running "
#         f"{len(data_files) * len(STRATEGIES)} "
#         f"strategy/dataset combinations..."
#     )


#     # ========================================================
#     # CHANGED:
#     # Run every strategy on every dataset
#     # ========================================================

#     for data_path in data_files:

#         df = load_csv(
#             data_path
#         )

#         rows = []

#         for path in STRATEGIES:

#             m = run_one(
#                 df,
#                 path
#             )

#             if m is None:
#                 continue

#             m["strategy"] = Path(
#                 path
#             ).stem

#             rows.append(m)


#         # Add buy-and-hold as a benchmark
#         bh = run_one(
#             df,
#             "strategies/00_buy_hold.py"
#         )


#         df_out = (
#             pd.DataFrame(rows)
#             .set_index("strategy")
#         )


#         cols = [
#             "CAGR",
#             "volatility",
#             "sharpe",
#             "sortino",
#             "calmar",
#             "max_drawdown",
#             "max_drawdown_duration_bars",
#             "num_trades",
#             "win_rate",
#             "profit_factor",
#             "expectancy"
#         ]


#         display = df_out.copy()


#         # Format percentages safely

#         for c in [
#             "CAGR",
#             "volatility",
#             "max_drawdown"
#         ]:

#             if c in display.columns:

#                 display[c] = (
#                     display[c] * 100
#                 ).round(2).astype(str) + "%"


#         # Round floats safely

#         for c in [
#             "sharpe",
#             "sortino",
#             "calmar",
#             "win_rate",
#             "profit_factor",
#             "expectancy"
#         ]:

#             if c in display.columns:

#                 display[c] = (
#                     display[c].round(3)
#                 )


#         # Optional:
#         # if a column is entirely missing, show it as "—"

#         expected = [
#             "CAGR",
#             "volatility",
#             "sharpe",
#             "sortino",
#             "calmar",
#             "max_drawdown",
#             "max_drawdown_duration_bars",
#             "num_trades",
#             "win_rate",
#             "profit_factor",
#             "expectancy"
#         ]


#         for c in expected:

#             if c not in display.columns:

#                 display[c] = "—"


#         display = display[
#             expected
#         ]


#         print(
#             "\n" + "=" * 100
#         )

#         print(
#             f"RESULTS ON: {data_path} "
#             f"({len(df)} bars, "
#             f"{df.index[0].date()} → "
#             f"{df.index[-1].date()})"
#         )

#         print(
#             "=" * 100
#         )

#         print(
#             display.to_string()
#         )

#         print(
#             "=" * 100
#         )


# if __name__ == "__main__":

#     main()

#modified
# run_all.py

import json
from pathlib import Path

import pandas as pd

from engine.data import load_csv
from engine.core import BacktestEngine
from engine.loader import load_strategy, validate_signals
from analytics.metrics import compute_metrics, extract_trades


STRATEGIES = sorted(
    [
        str(path)
        for path in Path("strategies").glob("*.py")
        if path.stem[:2].isdigit()
    ]
)


def run_one(df, path):

    try:

        fn = load_strategy(path)

        sig = validate_signals(
            fn(df),
            df
        )

        eng = BacktestEngine(
            initial_cash=100_000,
            commission_bps=1,
            slippage_bps=5
        )

        eq = eng.run(
            df,
            sig
        )

        trades = extract_trades(
            eng.pf.fills
        )

        return eq, trades

    except Exception as e:

        print(
            f"❌ {path}: {e}"
        )

        return None, None


# ============================================================
# CHANGED:
# Infer the observation frequency from the actual timestamps.
#
# This avoids assuming that "1H" or "4H" means 24/6/252 for
# every instrument. The actual dataset determines the average
# number of observations represented by a calendar year.
#
# The result is used for annualized volatility and Sharpe.
# CAGR itself uses actual timestamp span below.
# ============================================================

def infer_periods_per_year(df: pd.DataFrame) -> float:

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(
            "DataFrame index must be a DatetimeIndex "
            "to infer periods_per_year."
        )

    if len(df.index) < 2:
        raise ValueError(
            "Need at least 2 timestamps to infer frequency."
        )

    elapsed_seconds = (
        df.index[-1] - df.index[0]
    ).total_seconds()

    if elapsed_seconds <= 0:
        raise ValueError(
            "Data timestamps must be increasing."
        )

    # Actual observations per calendar year.
    #
    # Example:
    # 5,000 hourly observations over ~16 years
    # gives the empirical observations/year for that dataset.
    years = elapsed_seconds / (365.2425 * 24 * 60 * 60)

    return (len(df) - 1) / years


# ============================================================
# CHANGED:
# Calculate actual elapsed years from the timestamps.
#
# This is more correct for CAGR than len(returns) / ppy,
# especially when the dataset has weekends, holidays,
# session gaps, or irregular market hours.
# ============================================================

def infer_elapsed_years(df: pd.DataFrame) -> float:

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(
            "DataFrame index must be a DatetimeIndex."
        )

    elapsed_seconds = (
        df.index[-1] - df.index[0]
    ).total_seconds()

    return elapsed_seconds / (
        365.2425 * 24 * 60 * 60
    )


def main():

    # ========================================================
    # CHANGED:
    # Run all supported timeframe directories.
    # ========================================================

    data_directories = [
        Path("data/raw/daily"),
        Path("data/raw/fourhours"),
        Path("data/raw/onehours"),
    ]

    data_files = []

    for data_dir in data_directories:

        data_files.extend(
            sorted(
                data_dir.glob("*.csv")
            )
        )

    if not data_files:

        raise FileNotFoundError(
            "No CSV files found in "
            "data/raw/daily, "
            "data/raw/fourhours, "
            "or data/raw/onehours"
        )

    print(
        f"\nFound {len(data_files)} datasets."
    )

    print(
        f"Found {len(STRATEGIES)} strategies."
    )

    print(
        f"Running "
        f"{len(data_files) * len(STRATEGIES)} "
        f"strategy/dataset combinations..."
    )


    for data_path in data_files:

        df = load_csv(
            data_path
        )

        # ====================================================
        # CHANGED:
        # Determine annualization from actual dataset
        # timestamps.
        # ====================================================

        ppy = infer_periods_per_year(
            df
        )

        elapsed_years = infer_elapsed_years(
            df
        )

        rows = []


        for path in STRATEGIES:

            result = run_one(
                df,
                path
            )

            if result[0] is None:
                continue

            eq, trades = result

            # =================================================
            # CHANGED:
            # Pass timeframe-aware annualization and actual
            # calendar duration into metrics.
            # =================================================

            m = compute_metrics(
                eq,
                rf_annual=0.04,
                periods_per_year=ppy,
                elapsed_years=elapsed_years,
                trades=trades
            )

            m["strategy"] = (
                Path(path).stem
            )

            rows.append(m)


        # Add buy-and-hold as a benchmark
        # Kept from the original code.

        bh = run_one(
            df,
            "strategies/00_buy_hold.py"
        )


        df_out = (
            pd.DataFrame(rows)
            .set_index("strategy")
        )


        cols = [
            "CAGR",
            "volatility",
            "sharpe",
            "sortino",
            "calmar",
            "max_drawdown",
            "max_drawdown_duration_bars",
            "num_trades",
            "win_rate",
            "profit_factor",
            "expectancy"
        ]


        display = df_out.copy()


        # Format percentages safely

        for c in [
            "CAGR",
            "volatility",
            "max_drawdown"
        ]:

            if c in display.columns:

                display[c] = (
                    display[c] * 100
                ).round(2).astype(str) + "%"


        # Round floats safely

        for c in [
            "sharpe",
            "sortino",
            "calmar",
            "win_rate",
            "profit_factor",
            "expectancy"
        ]:

            if c in display.columns:

                display[c] = (
                    display[c].round(3)
                )


        expected = [
            "CAGR",
            "volatility",
            "sharpe",
            "sortino",
            "calmar",
            "max_drawdown",
            "max_drawdown_duration_bars",
            "num_trades",
            "win_rate",
            "profit_factor",
            "expectancy"
        ]


        for c in expected:

            if c not in display.columns:

                display[c] = "—"


        display = display[
            expected
        ]


        print(
            "\n" + "=" * 100
        )

        print(
            f"RESULTS ON: {data_path} "
            f"({len(df)} bars, "
            f"{df.index[0]} → "
            f"{df.index[-1]})"
        )

        # ====================================================
        # CHANGED:
        # Show the annualization factor so the result is
        # auditable.
        # ====================================================

        print(
            f"Annualization: "
            f"{ppy:.2f} periods/year | "
            f"Elapsed: {elapsed_years:.2f} years"
        )

        print(
            "=" * 100
        )

        print(
            display.to_string()
        )

        print(
            "=" * 100
        )


if __name__ == "__main__":

    main()
