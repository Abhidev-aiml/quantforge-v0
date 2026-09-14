"""
NY ORB Data Diagnostic
======================

Purpose
-------
Validate the real XAUUSD 5-minute dataset before debugging ORB strategy logic.

Checks:
1. Project/import path
2. Dataset existence
3. Raw columns
4. Row count
5. Duplicate timestamps
6. Timestamp parsing
7. Source timezone -> New York conversion
8. NY date range
9. First/last timestamps
10. Presence of the exact NY 09:30-10:00 ORB window
11. Number of 5M bars per NY trading day
12. Valid ORB days
13. Invalid ORB days
14. Example valid ORB days
15. Example invalid ORB days
16. ORB high/low/range examples
17. Breakout candidates
18. Final diagnosis

Run from project root:

    python scripts/explore/orb_data_diagnostic.py
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. Make project root importable
# ---------------------------------------------------------------------------

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# 2. Standard imports
# ---------------------------------------------------------------------------

from datetime import timedelta, timezone

import pandas as pd


# ---------------------------------------------------------------------------
# 3. Project imports
# ---------------------------------------------------------------------------

from strategies.orb_utils import (
    SOURCE_TZ,
    NY_TZ,
    ORB_START,
    ORB_END,
)


# ---------------------------------------------------------------------------
# 4. Configuration
# ---------------------------------------------------------------------------

DATASET_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "fiveminutes"
    / "xauusd_5m.csv"
)

EXPECTED_COLUMNS = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
]

ORB_BAR_COUNT = 6

MAX_EXAMPLE_DAYS = 10


# ---------------------------------------------------------------------------
# 5. Helpers
# ---------------------------------------------------------------------------

def print_header(title: str) -> None:
    """Print a readable diagnostic section header."""

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_subheader(title: str) -> None:
    """Print a smaller diagnostic section header."""

    print()
    print("-" * 80)
    print(title)
    print("-" * 80)


def format_ts(ts) -> str:
    """Format timestamps consistently."""

    if pd.isna(ts):
        return "NaT"

    return str(ts)


# ---------------------------------------------------------------------------
# 6. Main diagnostic
# ---------------------------------------------------------------------------

def main() -> None:

    print_header("NY ORB DATA DIAGNOSTIC")

    print(f"Project root : {PROJECT_ROOT}")
    print(f"Dataset      : {DATASET_PATH}")

    # -----------------------------------------------------------------------
    # Dataset existence
    # -----------------------------------------------------------------------

    print_subheader("1. DATASET EXISTENCE")

    if not DATASET_PATH.exists():
        print("❌ Dataset does not exist.")
        print()
        print("Expected:")
        print(DATASET_PATH)
        print()
        print("Check that the file exists at:")
        print("data/raw/fiveminutes/xauusd_5m.csv")
        return

    print("✅ Dataset exists.")

    # -----------------------------------------------------------------------
    # Load data
    # -----------------------------------------------------------------------

    print_subheader("2. LOADING DATA")

    try:
        df = pd.read_csv(DATASET_PATH)
    except Exception as exc:
        print("❌ Failed to load dataset.")
        print(f"Error: {exc}")
        return

    print("✅ Dataset loaded successfully.")

    # -----------------------------------------------------------------------
    # Basic information
    # -----------------------------------------------------------------------

    print_subheader("3. BASIC DATASET INFORMATION")

    print(f"Rows    : {len(df):,}")
    print(f"Columns : {list(df.columns)}")

    missing_columns = [
        column
        for column in EXPECTED_COLUMNS
        if column not in df.columns
    ]

    extra_columns = [
        column
        for column in df.columns
        if column not in EXPECTED_COLUMNS
    ]

    if missing_columns:
        print(f"❌ Missing expected columns: {missing_columns}")
    else:
        print("✅ All expected columns exist.")

    if extra_columns:
        print(f"ℹ️ Extra columns: {extra_columns}")

    # -----------------------------------------------------------------------
    # Timestamp parsing
    # -----------------------------------------------------------------------

    print_subheader("4. TIMESTAMP VALIDATION")

    if "date" not in df.columns:
        print("❌ 'date' column is missing.")
        return

    raw_dates = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    invalid_dates = raw_dates.isna().sum()

    print(f"Invalid timestamps : {invalid_dates:,}")

    if invalid_dates:
        print("❌ Invalid timestamps detected.")
        print()
        print(df.loc[raw_dates.isna(), ["date"]].head(10))
        return

    print("✅ All timestamps parse successfully.")

    # -----------------------------------------------------------------------
    # Duplicate timestamp check
    # -----------------------------------------------------------------------

    print_subheader("5. DUPLICATE TIMESTAMP CHECK")

    duplicate_count = raw_dates.duplicated().sum()

    print(f"Duplicate timestamps : {duplicate_count:,}")

    if duplicate_count == 0:
        print("✅ No duplicate timestamps.")
    else:
        print("⚠️ Duplicate timestamps detected.")
        print()
        print(
            df.loc[
                raw_dates.duplicated(keep=False),
                ["date"],
            ].head(20)
        )

    # -----------------------------------------------------------------------
    # Raw timestamp range
    # -----------------------------------------------------------------------

    print_subheader("6. RAW TIMESTAMP RANGE")

    raw_start = raw_dates.min()
    raw_end = raw_dates.max()

    print(f"Raw start : {format_ts(raw_start)}")
    print(f"Raw end   : {format_ts(raw_end)}")

    # -----------------------------------------------------------------------
    # Source timezone conversion
    # -----------------------------------------------------------------------

    print_subheader("7. SOURCE TIMEZONE → NEW YORK")

    print(f"Source timezone : {SOURCE_TZ}")
    print(f"New York TZ     : {NY_TZ}")

    # Convert naive source timestamps to explicit source timezone.
    #
    # IMPORTANT:
    # This assumes the dataset timestamps represent SOURCE_TZ.
    # Based on the current dataset investigation, SOURCE_TZ is UTC+3.

    source_index = pd.DatetimeIndex(raw_dates)

    if source_index.tz is None:
        source_index = source_index.tz_localize(SOURCE_TZ)
    else:
        source_index = source_index.tz_convert(SOURCE_TZ)

    ny_index = source_index.tz_convert(NY_TZ)

    print("✅ Timestamp conversion successful.")

    print()
    print("First conversion:")
    print(f"Source : {source_index[0]}")
    print(f"NY     : {ny_index[0]}")

    print()
    print("Last conversion:")
    print(f"Source : {source_index[-1]}")
    print(f"NY     : {ny_index[-1]}")

    # -----------------------------------------------------------------------
    # Create NY-aware dataframe
    # -----------------------------------------------------------------------

    work = df.copy()

    work["_source_time"] = source_index
    work["_ny_time"] = ny_index
    work["_ny_date"] = ny_index.date
    work["_ny_clock"] = ny_index.time

    # -----------------------------------------------------------------------
    # New York range
    # -----------------------------------------------------------------------

    print_subheader("8. NEW YORK TIMESTAMP RANGE")

    print(f"NY start : {format_ts(ny_index[0])}")
    print(f"NY end   : {format_ts(ny_index[-1])}")

    print()
    print(f"NY start date : {ny_index[0].date()}")
    print(f"NY end date   : {ny_index[-1].date()}")

    # -----------------------------------------------------------------------
    # First 20 NY timestamps
    # -----------------------------------------------------------------------

    print_subheader("9. FIRST 20 NEW YORK TIMESTAMPS")

    first_20 = pd.DataFrame(
        {
            "source_time": source_index[:20],
            "ny_time": ny_index[:20],
        }
    )

    print(first_20.to_string(index=False))

    # -----------------------------------------------------------------------
    # Search for exact ORB timestamps
    # -----------------------------------------------------------------------

    print_subheader("10. EXACT ORB WINDOW CHECK")

    print(
        f"Expected ORB window: "
        f"{ORB_START} <= NY time < {ORB_END}"
    )

    print(
        f"Expected number of 5M bars: "
        f"{ORB_BAR_COUNT}"
    )

    # Extract all bars inside the ORB window.

    ny_times = ny_index

    orb_mask = (
        (ny_times.strftime("%H:%M") >= ORB_START)
        & (ny_times.strftime("%H:%M") < ORB_END)
    )

    orb_rows = work.loc[orb_mask].copy()

    print()
    print(f"Bars inside ORB window: {len(orb_rows):,}")

    if orb_rows.empty:
        print()
        print("❌ ZERO bars found inside the ORB window.")
        print()
        print("This means the problem is almost certainly:")
        print("  - timezone assumption")
        print("  - timestamp interpretation")
        print("  - dataset session coverage")
        print("  - missing intraday bars")
        print()
        print("Do NOT change ORB strategy logic yet.")
    else:
        print("✅ ORB-window bars exist.")

        print()
        print("First ORB-window examples:")

        print(
            orb_rows[
                [
                    "_source_time",
                    "_ny_time",
                    "open",
                    "high",
                    "low",
                    "close",
                ]
            ]
            .head(20)
            .to_string(index=False)
        )

    # -----------------------------------------------------------------------
    # Per-day ORB counts
    # -----------------------------------------------------------------------

    print_subheader("11. ORB BARS PER NEW YORK DAY")

    if orb_rows.empty:
        print("No ORB bars available.")
        return

    orb_counts = (
        orb_rows
        .groupby("_ny_date")
        .size()
        .sort_index()
    )

    print(f"Total NY dates containing ORB bars: {len(orb_counts):,}")

    print()
    print("Distribution of ORB bar counts:")

    distribution = (
        orb_counts
        .value_counts()
        .sort_index()
        .rename_axis("ORB_bar_count")
        .reset_index(name="number_of_days")
    )

    print(distribution.to_string(index=False))

    # -----------------------------------------------------------------------
    # Valid ORB days
    # -----------------------------------------------------------------------

    print_subheader("12. VALID ORB DAYS")

    valid_days = orb_counts[orb_counts == ORB_BAR_COUNT]

    print(f"Valid ORB days : {len(valid_days):,}")

    if len(valid_days) == 0:
        print()
        print("❌ ZERO VALID ORB DAYS.")
        print()
        print(
            "The dataset does contain bars in the ORB window, "
            "but not exactly six 5M bars on any day."
        )
        print()
        print(
            "This strongly suggests a data-frequency/session problem."
        )
    else:
        print("✅ Valid ORB days exist.")

        print()
        print("First valid days:")

        print(
            valid_days
            .head(MAX_EXAMPLE_DAYS)
            .to_string()
        )

    # -----------------------------------------------------------------------
    # Invalid ORB days
    # -----------------------------------------------------------------------

    print_subheader("13. INVALID ORB DAYS")

    invalid_days = orb_counts[orb_counts != ORB_BAR_COUNT]

    print(f"Invalid ORB days : {len(invalid_days):,}")

    if len(invalid_days):
        print()
        print("Examples:")

        print(
            invalid_days
            .head(MAX_EXAMPLE_DAYS)
            .to_string()
        )

    # -----------------------------------------------------------------------
    # Inspect first valid ORB days
    # -----------------------------------------------------------------------

    print_subheader("14. SAMPLE VALID ORB WINDOWS")

    if len(valid_days) == 0:
        print("No valid ORB days to inspect.")
    else:

        sample_days = valid_days.index[:MAX_EXAMPLE_DAYS]

        for day in sample_days:

            day_mask = (
                (work["_ny_date"] == day)
                & (
                    work["_ny_time"].dt.strftime("%H:%M")
                    >= ORB_START
                )
                & (
                    work["_ny_time"].dt.strftime("%H:%M")
                    < ORB_END
                )
            )

            sample = work.loc[day_mask].copy()

            print()
            print(f"NY DATE: {day}")
            print(f"Bars   : {len(sample)}")

            print(
                sample[
                    [
                        "_source_time",
                        "_ny_time",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                    ]
                ].to_string(index=False)
            )

            orb_high = sample["high"].max()
            orb_low = sample["low"].min()
            orb_range = orb_high - orb_low

            print()
            print(f"ORB High  : {orb_high}")
            print(f"ORB Low   : {orb_low}")
            print(f"ORB Range : {orb_range}")

    # -----------------------------------------------------------------------
    # Check timestamp spacing
    # -----------------------------------------------------------------------

    print_subheader("15. TIMESTAMP SPACING CHECK")

    diffs = pd.Series(ny_index).diff().dropna()

    print("Most common timestamp intervals:")

    spacing = (
        diffs
        .value_counts()
        .head(10)
    )

    print(spacing.to_string())

    five_minute_count = (diffs == timedelta(minutes=5)).sum()

    print()
    print(
        f"5-minute intervals: "
        f"{five_minute_count:,} / {len(diffs):,}"
    )

    # -----------------------------------------------------------------------
    # Breakout candidate audit
    # -----------------------------------------------------------------------

    print_subheader("16. BREAKOUT CANDIDATE AUDIT")

    if len(valid_days) == 0:
        print("Cannot perform breakout audit because there are no valid ORBs.")
    else:

        breakout_examples = []

        for day in valid_days.index:

            day_data = work[work["_ny_date"] == day].copy()

            orb_data = day_data[
                (
                    day_data["_ny_time"].dt.strftime("%H:%M")
                    >= ORB_START
                )
                & (
                    day_data["_ny_time"].dt.strftime("%H:%M")
                    < ORB_END
                )
            ]

            if len(orb_data) != ORB_BAR_COUNT:
                continue

            orb_high = orb_data["high"].max()
            orb_low = orb_data["low"].min()

            # Bars after the ORB window.

            post_orb = day_data[
                day_data["_ny_time"].dt.strftime("%H:%M")
                >= ORB_END
            ].copy()

            if post_orb.empty:
                continue

            long_breakouts = post_orb[
                post_orb["close"] > orb_high
            ]

            short_breakouts = post_orb[
                post_orb["close"] < orb_low
            ]

            if not long_breakouts.empty:

                first = long_breakouts.iloc[0]

                breakout_examples.append(
                    {
                        "date": day,
                        "direction": "LONG",
                        "time": first["_ny_time"],
                        "close": first["close"],
                        "orb_high": orb_high,
                        "orb_low": orb_low,
                    }
                )

            if not short_breakouts.empty:

                first = short_breakouts.iloc[0]

                breakout_examples.append(
                    {
                        "date": day,
                        "direction": "SHORT",
                        "time": first["_ny_time"],
                        "close": first["close"],
                        "orb_high": orb_high,
                        "orb_low": orb_low,
                    }
                )

            if len(breakout_examples) >= 20:
                break

        breakout_df = pd.DataFrame(breakout_examples)

        print(
            f"Breakout examples found: "
            f"{len(breakout_df):,}"
        )

        if breakout_df.empty:
            print()
            print("⚠️ No breakout candidates found.")
            print()
            print(
                "If valid ORBs exist, investigate breakout "
                "logic/session cutoff next."
            )
        else:
            print()
            print(
                breakout_df
                .head(20)
                .to_string(index=False)
            )

    # -----------------------------------------------------------------------
    # Overall diagnosis
    # -----------------------------------------------------------------------

    print_header("FINAL DIAGNOSIS")

    print(f"Dataset rows                 : {len(df):,}")
    print(f"Duplicate timestamps         : {duplicate_count:,}")
    print(f"Invalid timestamps           : {invalid_dates:,}")
    print(f"ORB-window bars              : {len(orb_rows):,}")
    print(f"Days containing ORB bars     : {len(orb_counts):,}")
    print(f"Valid six-bar ORB days       : {len(valid_days):,}")
    print(f"Invalid ORB days             : {len(invalid_days):,}")

    print()

    if len(valid_days) == 0:

        print("❌ ORB DATA VALIDATION FAILED")
        print()
        print(
            "There are no valid six-bar 09:30-10:00 NY ORB windows."
        )
        print()
        print(
            "NEXT STEP:"
        )
        print(
            "Investigate timezone/session/data-frequency alignment."
        )

    elif len(valid_days) > 0:

        print("✅ ORB DATA VALIDATION PASSED")
        print()
        print(
            "The dataset contains valid six-bar NY ORB windows."
        )
        print()
        print(
            "NEXT STEP:"
        )
        print(
            "Audit actual breakout detection and signal generation."
        )

    print()
    print("=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()