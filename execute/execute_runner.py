# execute_research_runner.py
#
# Interactive QuantForge research runner.
#
# Select:
#   1. Timeframe(s)
#   2. Dataset(s)
#   3. Strategy/strategies
#
# The underlying backtest / analytics logic is kept the same.
#

from pathlib import Path

import pandas as pd

from engine.data import load_csv
from engine.core import BacktestEngine
from engine.loader import load_strategy, validate_signals
from analytics.metrics import compute_metrics


# ============================================================
# DIRECTORIES
# ============================================================

TIMEFRAME_DIRS = {
    "1": ("D", Path("data/raw/daily")),
    "2": ("4H", Path("data/raw/fourhours")),
    # "3": ("1H", Path("data/raw/onehours")),
    "3": ("5M", Path("data/raw/fiveminutes")),
}

STRATEGY_DIR = Path("strategies")


# ============================================================
# STRATEGY DISCOVERY
# ============================================================

STRATEGIES = sorted(
    [
        path
        for path in STRATEGY_DIR.glob("*.py")
        if path.stem[:2].isdigit()
    ],
    key=lambda p: p.name,
)


# ============================================================
# TIMEFRAME / ANNUALIZATION
# ============================================================

def infer_periods_per_year(df: pd.DataFrame) -> float:
    """
    Infer observation frequency from actual timestamps.

    Used for annualized volatility / Sharpe / Sortino.
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
    """
    Calculate the actual calendar duration represented
    by the dataset.
    """

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


# ============================================================
# INPUT HELPERS
# ============================================================

def parse_selection(
    value: str,
    max_value: int,
    allow_all: bool = True,
) -> list[int]:
    """
    Parse:
        1
        1,3,5
        1-4
        all

    Returns zero-based indices.
    """

    value = value.strip().lower()

    if allow_all and value in {"a", "all", "*"}:
        return list(range(max_value))

    selected = set()

    for item in value.split(","):
        item = item.strip()

        if not item:
            continue

        # Support ranges: 2-5
        if "-" in item:
            parts = item.split("-", 1)

            if len(parts) != 2:
                raise ValueError(
                    f"Invalid range: {item}"
                )

            start = int(parts[0])
            end = int(parts[1])

            if start > end:
                start, end = end, start

            for number in range(start, end + 1):
                if not 1 <= number <= max_value:
                    raise ValueError(
                        f"Selection {number} is outside 1-{max_value}"
                    )

                selected.add(number - 1)

        else:
            number = int(item)

            if not 1 <= number <= max_value:
                raise ValueError(
                    f"Selection {number} is outside 1-{max_value}"
                )

            selected.add(number - 1)

    if not selected:
        raise ValueError(
            "No valid selections were provided."
        )

    return sorted(selected)


def ask_selection(
    prompt: str,
    max_value: int,
) -> list[int]:

    while True:
        try:
            value = input(prompt)
            return parse_selection(
                value,
                max_value,
            )

        except (ValueError, TypeError) as e:
            print(f"❌ {e}")
            print(
                "Examples: 1 | 1,3,5 | 1-4 | all"
            )


# ============================================================
# DISPLAY FUNCTIONS
# ============================================================

def print_header(title: str):

    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def choose_timeframes():
    print_header("QUANTFORGE RESEARCH RUNNER")

    print("\nTIMEFRAMES")

    for key, (name, _) in TIMEFRAME_DIRS.items():
        print(f"{key}. {name}")

    print("4. all")

    while True:
        try:
            value = input(
                "\nSelect timeframe(s) "
                "(1/2/3, e.g. 1,2 or 4 for all): "
            ).strip().lower()

            if value == "4" or value in {"a", "all"}:
                return list(TIMEFRAME_DIRS.values())

            indexes = parse_selection(
                value,
                3,
            )

            selected = [
                list(TIMEFRAME_DIRS.values())[i]
                for i in indexes
            ]

            return selected

        except ValueError as e:
            print(f"❌ {e}")


def choose_strategies():
    print_header("STRATEGIES")

    if not STRATEGIES:
        raise FileNotFoundError(
            "No numbered strategy files found in strategies/"
        )

    for i, strategy in enumerate(STRATEGIES, start=1):
        print(f"{i:2}. {strategy.stem}")

    print(" A. all")

    indexes = ask_selection(
        "\nSelect strategy(s) "
        "(e.g. 1,5,11 or 1-5 or all): ",
        len(STRATEGIES),
    )

    return [
        STRATEGIES[i]
        for i in indexes
    ]


def choose_datasets(timeframe_name, data_dir):
    print_header(
        f"DATASETS — {timeframe_name}"
    )

    datasets = sorted(
        data_dir.glob("*.csv"),
        key=lambda p: p.name.lower(),
    )

    if not datasets:
        raise FileNotFoundError(
            f"No CSV files found in {data_dir}"
        )

    for i, dataset in enumerate(
        datasets,
        start=1,
    ):
        print(
            f"{i:2}. {dataset.stem}"
        )

    print(" A. all")

    indexes = ask_selection(
        "\nSelect dataset(s) "
        "(e.g. 1,5,12 or 1-4 or all): ",
        len(datasets),
    )

    return [
        datasets[i]
        for i in indexes
    ]


# ============================================================
# BACKTEST
# ============================================================

def run_one(df: pd.DataFrame, strategy_path: Path):

    try:
        fn = load_strategy(strategy_path)

        sig = validate_signals(
            fn(df),
            df,
        )

        eng = BacktestEngine(
            initial_cash=100_000,
            commission_bps=1,
            slippage_bps=5,
        )

        eq = eng.run(
            df,
            sig,
        )

        from analytics.metrics import extract_trades

        trades = extract_trades(
            eng.pf.fills
        )

        return eq, trades, None

    except Exception as e:
        return None, None, e


# ============================================================
# FORMAT RESULTS
# ============================================================

def format_results(rows):

    df_out = (
        pd.DataFrame(rows)
        .set_index("strategy")
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
        "expectancy",
    ]

    display = df_out.copy()

    for c in [
        "CAGR",
        "volatility",
        "max_drawdown",
    ]:
        if c in display.columns:
            display[c] = (
                display[c] * 100
            ).round(2).astype(str) + "%"

    for c in [
        "sharpe",
        "sortino",
        "calmar",
        "win_rate",
        "profit_factor",
        "expectancy",
    ]:
        if c in display.columns:
            display[c] = display[c].round(3)

    for c in expected:
        if c not in display.columns:
            display[c] = "—"

    return display[expected]


# ============================================================
# RUN ONE DATASET
# ============================================================

def run_dataset(
    data_path: Path,
    strategy_paths: list[Path],
    timeframe_name: str,
):

    print_header(
        f"RESULTS ON: {data_path}"
    )

    try:
        df = load_csv(data_path)

    except Exception as e:
        print(
            f"❌ Failed to load {data_path}: {e}"
        )
        return

    ppy = infer_periods_per_year(df)
    elapsed_years = infer_elapsed_years(df)

    print(
        f"{len(df):,} bars | "
        f"{df.index[0]} → {df.index[-1]}"
    )

    print(
        f"Timeframe: {timeframe_name}"
    )

    print(
        f"Annualization: "
        f"{ppy:.2f} periods/year"
    )

    print(
        f"Elapsed: "
        f"{elapsed_years:.2f} years"
    )

    rows = []

    for strategy_path in strategy_paths:

        eq, trades, error = run_one(
            df,
            strategy_path,
        )

        if error is not None:
            print(
                f"❌ {strategy_path.name}: {error}"
            )
            continue

        m = compute_metrics(
            eq,
            rf_annual=0.04,
            periods_per_year=ppy,
            elapsed_years=elapsed_years,
            trades=trades,
        )

        m["strategy"] = strategy_path.stem

        rows.append(m)

    if not rows:
        print("No successful strategy results.")
        return

    display = format_results(rows)

    print("\n" + "=" * 100)
    print(
        f"RESULTS — {data_path.name}"
    )
    print("=" * 100)
    print(display.to_string())
    print("=" * 100)


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # 1. Select timeframe(s)
    # --------------------------------------------------------

    selected_timeframes = choose_timeframes()

    # --------------------------------------------------------
    # 2. Select strategies
    # --------------------------------------------------------

    selected_strategies = choose_strategies()

    # --------------------------------------------------------
    # 3. Print strategy selection
    # --------------------------------------------------------

    print_header("SELECTED STRATEGIES")

    for strategy in selected_strategies:
        print(
            f"- {strategy.stem}"
        )

    # --------------------------------------------------------
    # 4. Run selected datasets for each timeframe
    # --------------------------------------------------------

    for timeframe_name, data_dir in selected_timeframes:

        selected_datasets = choose_datasets(
            timeframe_name,
            data_dir,
        )

        print_header(
            f"RUNNING {timeframe_name}"
        )

        print(
            f"Datasets selected: "
            f"{len(selected_datasets)}"
        )

        print(
            f"Strategies selected: "
            f"{len(selected_strategies)}"
        )

        print(
            f"Backtests: "
            f"{len(selected_datasets) * len(selected_strategies)}"
        )

        for data_path in selected_datasets:

            run_dataset(
                data_path,
                selected_strategies,
                timeframe_name,
            )


if __name__ == "__main__":
    main()
