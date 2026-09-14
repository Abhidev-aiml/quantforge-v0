from pathlib import Path

import pandas as pd


def check_dataset(path: Path, expected_minutes: int) -> None:

    print("\n" + "=" * 90)
    print(f"DATASET: {path}")
    print("=" * 90)

    # ---------------------------------------------------------
    # Load
    # ---------------------------------------------------------

    df = pd.read_csv(path)

    # ---------------------------------------------------------
    # Basic structure
    # ---------------------------------------------------------

    required = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    missing = [
        c for c in required
        if c not in df.columns
    ]

    if missing:
        print(f"❌ Missing columns: {missing}")
        return

    print(f"Rows: {len(df):,}")

    # ---------------------------------------------------------
    # Parse timestamps
    # ---------------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"],
        errors="raise"
    )

    print(
        f"Start: {df['date'].iloc[0]}"
    )

    print(
        f"End:   {df['date'].iloc[-1]}"
    )

    # ---------------------------------------------------------
    # Duplicate timestamps
    # ---------------------------------------------------------

    duplicates = df["date"].duplicated().sum()

    print(
        f"Duplicate timestamps: {duplicates}"
    )

    # ---------------------------------------------------------
    # Ordering
    # ---------------------------------------------------------

    out_of_order = (
        ~df["date"].is_monotonic_increasing
    )

    print(
        f"Out of order: {out_of_order}"
    )

    # ---------------------------------------------------------
    # Numeric types
    # ---------------------------------------------------------

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    for col in numeric_columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    print("\nNaNs:")

    print(
        df[numeric_columns]
        .isna()
        .sum()
        .to_string()
    )

    # ---------------------------------------------------------
    # OHLC sanity
    # ---------------------------------------------------------

    bad_ohlc = (
        (df["low"] > df["open"])
        | (df["low"] > df["close"])
        | (df["high"] < df["open"])
        | (df["high"] < df["close"])
        | (df["high"] < df["low"])
        | (df["close"] <= 0)
        | (df["volume"] < 0)
    )

    print(
        f"\nBad OHLC rows: {bad_ohlc.sum()}"
    )

    # ---------------------------------------------------------
    # Timestamp spacing
    # ---------------------------------------------------------

    delta = df["date"].diff().dropna()

    print("\nTimestamp spacing:")

    print(
        delta.value_counts()
        .head(10)
        .to_string()
    )

    expected = pd.Timedelta(
        minutes=expected_minutes
    )

    exact_spacing = (
        delta == expected
    ).sum()

    print(
        f"\nExpected interval: {expected}"
    )

    print(
        f"Exact interval bars: "
        f"{exact_spacing:,}/{len(delta):,}"
    )

    # ---------------------------------------------------------
    # Unexpected short intervals
    # ---------------------------------------------------------

    short = delta[
        delta < expected
    ]

    print(
        f"Intervals shorter than expected: "
        f"{len(short):,}"
    )

    # ---------------------------------------------------------
    # Large gaps
    # ---------------------------------------------------------

    large_gaps = delta[
        delta > expected
    ]

    print(
        f"Intervals longer than expected: "
        f"{len(large_gaps):,}"
    )

    print("\nLargest gaps:")

    print(
        delta.sort_values(
            ascending=False
        )
        .head(10)
        .to_string()
    )


def main():

    fourhour_files = sorted(
        Path("data/raw/fourhours")
        .glob("*_comma.csv")
    )

    onehour_files = sorted(
        Path("data/raw/onehours")
        .glob("*_comma.csv")
    )

    print(
        f"4H datasets: {len(fourhour_files)}"
    )

    print(
        f"1H datasets: {len(onehour_files)}"
    )

    for path in fourhour_files:
        check_dataset(
            path,
            expected_minutes=240
        )

    for path in onehour_files:
        check_dataset(
            path,
            expected_minutes=60
        )


if __name__ == "__main__":
    main()