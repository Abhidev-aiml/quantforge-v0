"""
ORB Signal Audit
================

Independent validation of strategies/17_ny_orb_breakout.py.

Purpose
-------
Verify that the ORB strategy produces exactly the signals expected from
the research specification BEFORE implementing SL/TP/risk execution.

This audit intentionally does NOT import orb_utils.py for the reference
calculation. The expected ORB/breakout logic is reconstructed independently
so that we are not validating the strategy against its own helper functions.

Research specification
----------------------
Instrument:
    XAUUSD

Timeframe:
    5-minute

Source timestamp timezone:
    UTC+03:00

NY timezone:
    America/New_York

ORB:
    09:30 <= NY time < 10:00

Required ORB bars:
    09:30
    09:35
    09:40
    09:45
    09:50
    09:55

Breakout:
    First 5M candle AFTER 10:00 whose CLOSE is:

        LONG  -> close > ORB high
        SHORT -> close < ORB low

Entry cutoff:
    15:30 NY

Signal semantics:
    Signal is generated at breakout candle close.

Engine execution:
    Signal at bar t close -> execution at bar t+1 open.

Important:
    This script audits signal semantics only.
    It does NOT calculate P&L, stops, targets, or risk.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from datetime import timedelta, timezone

import numpy as np
import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "fiveminutes"
    / "xauusd_5m.csv"
)

STRATEGY_PATH = (
    PROJECT_ROOT
    / "strategies"
    / "17_ny_orb_breakout.py"
)


# ============================================================
# TIMEZONE DEFINITIONS
# ============================================================

SOURCE_TZ = timezone(timedelta(hours=3))
NY_TZ = "America/New_York"

ORB_START = "09:30"
ORB_END = "10:00"

ENTRY_CUTOFF = "15:30"


# ============================================================
# AUDIT SETTINGS
# ============================================================

# Number of successful signal examples to print in detail.
MAX_EXAMPLES = 20

# Number of unexpected strategy signals to print.
MAX_UNEXPECTED = 20


# ============================================================
# DISPLAY HELPERS
# ============================================================

SEPARATOR = "=" * 90
THIN_SEPARATOR = "-" * 90


def header(title: str) -> None:
    print()
    print(SEPARATOR)
    print(title)
    print(SEPARATOR)


def fmt_price(value) -> str:
    if pd.isna(value):
        return "nan"
    return f"{float(value):.4f}"


def fmt_ts(ts) -> str:
    if pd.isna(ts):
        return "N/A"

    if isinstance(ts, pd.Timestamp):
        return ts.strftime("%Y-%m-%d %H:%M:%S %Z")

    return str(ts)


# ============================================================
# PROJECT ROOT
# ============================================================

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# LOAD STRATEGY
# ============================================================

def load_strategy(path: Path):
    """
    Load generate_signals() directly from the strategy file.

    We intentionally do not use engine.loader here because this script
    is a diagnostic/reference audit and should expose failures clearly.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Strategy file not found:\n{path}"
        )

    if path.suffix != ".py":
        raise ValueError(
            f"Strategy must be a .py file:\n{path}"
        )

    spec = importlib.util.spec_from_file_location(
        "orb_strategy_under_audit",
        path,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not create import specification for:\n{path}"
        )

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise RuntimeError(
            f"Strategy import failed:\n{exc}"
        ) from exc

    if not hasattr(module, "generate_signals"):
        raise AttributeError(
            "Strategy does not define generate_signals(df)."
        )

    if not callable(module.generate_signals):
        raise TypeError(
            "Strategy generate_signals is not callable."
        )

    return module.generate_signals


# ============================================================
# LOAD DATA
# ============================================================

def load_data(path: Path) -> pd.DataFrame:
    """
    Load the raw XAUUSD 5M CSV.

    This deliberately uses pandas directly rather than engine.data.load_csv
    so the audit has an independent data-loading path.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found:\n{path}"
        )

    df = pd.read_csv(path)

    required = {
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Dataset is missing required columns: {sorted(missing)}"
        )

    # Parse timestamps.
    timestamps = pd.to_datetime(
        df["date"],
        errors="raise",
    )

    # Source data is known/assumed to represent UTC+03:00.
    source_index = pd.DatetimeIndex(
        timestamps
    ).tz_localize(SOURCE_TZ)

    # Keep the original source timestamp as the DataFrame index.
    #
    # This is important because the engine/strategy contract requires
    # signals to have exactly the same index as the input DataFrame.
    df.index = source_index

    # Numeric columns.
    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="raise",
        )

    return df


# ============================================================
# TIMEZONE CONVERSION
# ============================================================

def prepare_ny_view(
    df: pd.DataFrame,
    ) -> pd.DataFrame:
    """
    Create an NY-time view while preserving the original source index.
    """

    out = df.copy()

    out["source_timestamp"] = out.index

    ny_index = out.index.tz_convert(
        NY_TZ
    )

    out["ny_timestamp"] = ny_index

    out["ny_date"] = (
        ny_index.date
    )

    out["ny_time"] = (
        ny_index.time
    )

    return out


# ============================================================
# ORB REFERENCE CALCULATION
# ============================================================

def expected_orb_timestamps(day):
    """
    Return the six exact 5M NY timestamps expected for the ORB.
    """

    start = pd.Timestamp(
        f"{day} {ORB_START}",
        tz=NY_TZ,
    )

    return pd.date_range(
        start=start,
        periods=6,
        freq="5min",
    )


def build_reference_orb(
    day_df: pd.DataFrame,
    day,
):
    """
    Independently construct the ORB.

    Returns:
        {
            "valid": bool,
            "high": float | None,
            "low": float | None,
            "opening": DataFrame | None,
            "reason": str | None,
        }
    """

    expected = expected_orb_timestamps(day)

    ny_index = pd.DatetimeIndex(
        day_df["ny_timestamp"]
    )

    # Exact six timestamps must exist.
    #
    # We intentionally require all six expected bars.
    # We do not silently fill missing bars.
    available = set(ny_index)

    missing = [
        ts
        for ts in expected
        if ts not in available
    ]

    if missing:
        return {
            "valid": False,
            "high": None,
            "low": None,
            "opening": None,
            "reason": (
                "missing ORB bars: "
                + ", ".join(
                    ts.strftime("%H:%M")
                    for ts in missing
                )
            ),
        }

    # Select the exact six bars.
    opening = (
        day_df[
            day_df["ny_timestamp"].isin(expected)
        ]
        .sort_values("ny_timestamp")
        .copy()
    )

    if len(opening) != 6:
        return {
            "valid": False,
            "high": None,
            "low": None,
            "opening": None,
            "reason": (
                f"expected 6 ORB bars, found {len(opening)}"
            ),
        }

    actual_times = list(
        opening["ny_timestamp"]
    )

    if actual_times != list(expected):
        return {
            "valid": False,
            "high": None,
            "low": None,
            "opening": None,
            "reason": "ORB timestamps do not exactly match expected 5M grid",
        }

    orb_high = float(
        opening["high"].max()
    )

    orb_low = float(
        opening["low"].min()
    )

    if not np.isfinite(orb_high):
        return {
            "valid": False,
            "high": None,
            "low": None,
            "opening": None,
            "reason": "ORB high is not finite",
        }

    if not np.isfinite(orb_low):
        return {
            "valid": False,
            "high": None,
            "low": None,
            "opening": None,
            "reason": "ORB low is not finite",
        }

    if orb_high < orb_low:
        return {
            "valid": False,
            "high": None,
            "low": None,
            "opening": None,
            "reason": "ORB high is below ORB low",
        }

    return {
        "valid": True,
        "high": orb_high,
        "low": orb_low,
        "opening": opening,
        "reason": None,
    }


# ============================================================
# REFERENCE BREAKOUT
# ============================================================

def find_reference_breakout(
    day_df: pd.DataFrame,
    orb_high: float,
    orb_low: float,
):
    """
    Independently identify the first breakout after 10:00 NY.

    Rules:

        close > ORB high -> LONG
        close < ORB low  -> SHORT

    Breakout must occur no later than ENTRY_CUTOFF.
    """

    cutoff = pd.Timestamp(
        ENTRY_CUTOFF
    ).time()

    candidates = day_df[
        day_df["ny_time"].apply(
            lambda t: (
                t >= pd.Timestamp(ORB_END).time()
                and t <= cutoff
            )
        )
    ].copy()

    if candidates.empty:
        return None

    # IMPORTANT:
    # First qualifying close wins.
    for _, row in candidates.iterrows():

        close = float(row["close"])

        if close > orb_high:
            return {
                "direction": 1,
                "source_timestamp": row["source_timestamp"],
                "ny_timestamp": row["ny_timestamp"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": close,
            }

        if close < orb_low:
            return {
                "direction": -1,
                "source_timestamp": row["source_timestamp"],
                "ny_timestamp": row["ny_timestamp"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": close,
            }

    return None


# ============================================================
# STRATEGY SIGNAL INDEX HELPERS
# ============================================================

def signal_direction(value) -> int:
    """
    Convert strategy signal to:
        +1 long
        -1 short
         0 flat

    The current ORB strategy is expected to emit exact target values.
    """

    if pd.isna(value):
        return 0

    value = float(value)

    if value > 0:
        return 1

    if value < 0:
        return -1

    return 0


def get_strategy_signal_events(
    df: pd.DataFrame,
    signals: pd.Series,
):
    """
    Return all non-zero signal events.
    """

    if not isinstance(signals, pd.Series):
        raise TypeError(
            "generate_signals(df) must return a pandas Series."
        )

    if not signals.index.equals(df.index):
        raise ValueError(
            "Strategy signal index does not exactly match data index."
        )

    events = []

    for timestamp, value in signals.items():

        direction = signal_direction(value)

        if direction == 0:
            continue

        events.append(
            {
                "source_timestamp": timestamp,
                "direction": direction,
                "signal_value": float(value),
            }
        )

    return events


# ============================================================
# STRATEGY SIGNAL LOOKUP
# ============================================================

def build_signal_lookup(
    df: pd.DataFrame,
    signals: pd.Series,
):
    """
    Build a lookup keyed by source timestamp.
    """

    lookup = {}

    for timestamp, value in signals.items():

        direction = signal_direction(value)

        if direction == 0:
            continue

        lookup[timestamp] = {
            "direction": direction,
            "signal_value": float(value),
        }

    return lookup


# ============================================================
# EXPECTED SIGNAL GENERATION
# ============================================================

def build_reference_signals(
    df_ny: pd.DataFrame,
):
    """
    Independently generate the expected ORB breakout signals.

    Returns:
        list[dict]
    """

    expected_signals = []

    grouped = df_ny.groupby(
        "ny_date",
        sort=True,
    )

    for day, day_df in grouped:

        day_df = day_df.sort_values(
            "ny_timestamp"
        )

        orb = build_reference_orb(
            day_df,
            day,
        )

        if not orb["valid"]:
            continue

        breakout = find_reference_breakout(
            day_df,
            orb["high"],
            orb["low"],
        )

        if breakout is None:
            continue

        expected_signals.append(
            {
                "ny_date": day,
                "direction": breakout["direction"],
                "source_timestamp": breakout[
                    "source_timestamp"
                ],
                "ny_timestamp": breakout[
                    "ny_timestamp"
                ],
                "open": breakout["open"],
                "high": breakout["high"],
                "low": breakout["low"],
                "close": breakout["close"],
                "orb_high": orb["high"],
                "orb_low": orb["low"],
                "orb_range": (
                    orb["high"]
                    - orb["low"]
                ),
            }
        )

    return expected_signals


# ============================================================
# EXECUTION BAR
# ============================================================

def get_next_bar(
    df: pd.DataFrame,
    timestamp,
):
    """
    Get the next available source bar after signal timestamp.

    This mirrors the engine's basic next-bar execution concept.
    """

    try:
        position = df.index.get_loc(
            timestamp
        )
    except KeyError:
        return None

    # Exact integer position is expected for a unique DatetimeIndex.
    if not isinstance(position, (int, np.integer)):
        return None

    next_position = position + 1

    if next_position >= len(df):
        return None

    row = df.iloc[next_position]

    return {
        "source_timestamp": df.index[next_position],
        "ny_timestamp": df.index[
            next_position
        ].tz_convert(NY_TZ),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
    }


# ============================================================
# DATA QUALITY CHECK
# ============================================================

def run_data_checks(df: pd.DataFrame) -> None:

    header("1. DATA CHECKS")

    print(f"Dataset:       {DATA_PATH}")
    print(f"Rows:          {len(df):,}")
    print(f"First source:  {fmt_ts(df.index[0])}")
    print(f"Last source:   {fmt_ts(df.index[-1])}")

    print(
        f"First NY:      "
        f"{fmt_ts(df.index[0].tz_convert(NY_TZ))}"
    )

    print(
        f"Last NY:       "
        f"{fmt_ts(df.index[-1].tz_convert(NY_TZ))}"
    )

    print()

    print(
        f"Duplicate timestamps: "
        f"{df.index.duplicated().sum()}"
    )

    print(
        f"NaN OHLC rows: "
        f"{df[['open', 'high', 'low', 'close']].isna().any(axis=1).sum()}"
    )

    monotonic = df.index.is_monotonic_increasing

    print(
        f"Index increasing: "
        f"{monotonic}"
    )

    if not monotonic:
        raise AssertionError(
            "Source index is not monotonically increasing."
        )

    if df.index.has_duplicates:
        raise AssertionError(
            "Source index contains duplicates."
        )


# ============================================================
# STRATEGY CONTRACT CHECK
# ============================================================

def run_strategy_checks(
    df: pd.DataFrame,
    generate_signals,
):
    header("2. STRATEGY CONTRACT CHECK")

    signals = generate_signals(df)

    print(
        f"Strategy:       {STRATEGY_PATH}"
    )

    print(
        f"Signal type:    {type(signals).__name__}"
    )

    if not isinstance(signals, pd.Series):
        raise AssertionError(
            "Strategy did not return pandas Series."
        )

    print(
        f"Signal length:  {len(signals):,}"
    )

    print(
        f"Data length:    {len(df):,}"
    )

    if len(signals) != len(df):
        raise AssertionError(
            "Signal length does not match data length."
        )

    index_equal = signals.index.equals(
        df.index
    )

    print(
        f"Index equal:    {index_equal}"
    )

    if not index_equal:
        raise AssertionError(
            "Signal index does not exactly match data index."
        )

    numeric = pd.api.types.is_numeric_dtype(
        signals
    )

    print(
        f"Numeric dtype:  {numeric}"
    )

    if not numeric:
        raise AssertionError(
            "Signals are not numeric."
        )

    nan_count = int(
        signals.isna().sum()
    )

    print(
        f"NaN signals:    {nan_count}"
    )

    if nan_count:
        raise AssertionError(
            "Strategy produced NaN signals."
        )

    min_signal = float(
        signals.min()
    )

    max_signal = float(
        signals.max()
    )

    print(
        f"Signal range:   "
        f"[{min_signal}, {max_signal}]"
    )

    if min_signal < -1 or max_signal > 1:
        raise AssertionError(
            "Strategy produced signals outside [-1, +1]."
        )

    return signals


# ============================================================
# REFERENCE VS STRATEGY
# ============================================================

def compare_reference_to_strategy(
    df: pd.DataFrame,
    df_ny: pd.DataFrame,
    signals: pd.Series,
    expected_signals: list[dict],
):
    header("3. REFERENCE VS STRATEGY")

    strategy_lookup = build_signal_lookup(
        df,
        signals,
    )

    strategy_events = get_strategy_signal_events(
        df,
        signals,
    )

    print(
        f"Reference breakout signals: "
        f"{len(expected_signals):,}"
    )

    print(
        f"Strategy non-zero signals:   "
        f"{len(strategy_events):,}"
    )

    print()

    matched = 0
    missing = []
    direction_mismatch = []

    for expected in expected_signals:

        timestamp = expected[
            "source_timestamp"
        ]

        actual = strategy_lookup.get(
            timestamp
        )

        if actual is None:
            missing.append(
                expected
            )
            continue

        if (
            actual["direction"]
            != expected["direction"]
        ):
            direction_mismatch.append(
                {
                    "expected": expected,
                    "actual": actual,
                }
            )
            continue

        matched += 1

    # Find strategy signals that do not correspond to our independent
    # reference breakout set.
    expected_lookup = {
        x["source_timestamp"]: x
        for x in expected_signals
    }

    unexpected = []

    for event in strategy_events:

        timestamp = event[
            "source_timestamp"
        ]

        if timestamp not in expected_lookup:
            unexpected.append(
                event
            )

    print(
        f"Matched signals:             {matched:,}"
    )

    print(
        f"Missing expected signals:    {len(missing):,}"
    )

    print(
        f"Direction mismatches:         {len(direction_mismatch):,}"
    )

    print(
        f"Unexpected strategy signals:  {len(unexpected):,}"
    )

    return {
        "strategy_lookup": strategy_lookup,
        "strategy_events": strategy_events,
        "matched": matched,
        "missing": missing,
        "direction_mismatch": direction_mismatch,
        "unexpected": unexpected,
    }


# ============================================================
# DETAILED TRADE-BY-TRADE AUDIT
# ============================================================

def print_detailed_examples(
    df: pd.DataFrame,
    expected_signals: list[dict],
    comparison: dict,
):
    header("4. DETAILED SIGNAL AUDIT")

    print(
        f"Showing first {MAX_EXAMPLES} matched/reference signals."
    )

    print()

    for number, expected in enumerate(
        expected_signals[:MAX_EXAMPLES],
        start=1,
    ):

        timestamp = expected[
            "source_timestamp"
        ]

        actual = comparison[
            "strategy_lookup"
        ].get(timestamp)

        execution = get_next_bar(
            df,
            timestamp,
        )

        direction_text = (
            "LONG"
            if expected["direction"] == 1
            else "SHORT"
        )

        print(THIN_SEPARATOR)

        print(
            f"EXAMPLE #{number}"
        )

        print(
            f"NY Date:       {expected['ny_date']}"
        )

        print(
            f"Direction:     {direction_text}"
        )

        print()

        print(
            "ORB"
        )

        print(
            f"  High:         "
            f"{fmt_price(expected['orb_high'])}"
        )

        print(
            f"  Low:          "
            f"{fmt_price(expected['orb_low'])}"
        )

        print(
            f"  Range:        "
            f"{fmt_price(expected['orb_range'])}"
        )

        print()

        print(
            "REFERENCE BREAKOUT"
        )

        print(
            f"  NY time:      "
            f"{fmt_ts(expected['ny_timestamp'])}"
        )

        print(
            f"  Source time:  "
            f"{fmt_ts(expected['source_timestamp'])}"
        )

        print(
            f"  Open:         "
            f"{fmt_price(expected['open'])}"
        )

        print(
            f"  High:         "
            f"{fmt_price(expected['high'])}"
        )

        print(
            f"  Low:          "
            f"{fmt_price(expected['low'])}"
        )

        print(
            f"  Close:        "
            f"{fmt_price(expected['close'])}"
        )

        print()

        if actual is None:

            print(
                "STRATEGY SIGNAL"
            )

            print(
                "  ❌ MISSING"
            )

        else:

            actual_direction = (
                "LONG"
                if actual["direction"] == 1
                else "SHORT"
            )

            direction_ok = (
                actual["direction"]
                == expected["direction"]
            )

            print(
                "STRATEGY SIGNAL"
            )

            print(
                f"  Direction:     "
                f"{actual_direction}"
            )

            print(
                f"  Value:         "
                f"{actual['signal_value']}"
            )

            print(
                f"  Direction OK:  "
                f"{'YES' if direction_ok else 'NO'}"
            )

        print()

        print(
            "NEXT EXECUTION BAR"
        )

        if execution is None:

            print(
                "  ❌ No next bar available"
            )

        else:

            print(
                f"  NY time:       "
                f"{fmt_ts(execution['ny_timestamp'])}"
            )

            print(
                f"  Source time:   "
                f"{fmt_ts(execution['source_timestamp'])}"
            )

            print(
                f"  Open:          "
                f"{fmt_price(execution['open'])}"
            )

            print(
                f"  High:          "
                f"{fmt_price(execution['high'])}"
            )

            print(
                f"  Low:           "
                f"{fmt_price(execution['low'])}"
            )

            print(
                f"  Close:         "
                f"{fmt_price(execution['close'])}"
            )

    print(THIN_SEPARATOR)


# ============================================================
# ENTRY UNIQUENESS
# ============================================================

def audit_one_entry_per_day(
    expected_signals: list[dict],
):
    header("5. ONE-ENTRY-PER-DAY CHECK")

    if not expected_signals:
        print(
            "No reference signals."
        )
        return

    counts = {}

    for signal in expected_signals:

        day = signal["ny_date"]

        counts[day] = (
            counts.get(day, 0)
            + 1
        )

    multiple = {
        day: count
        for day, count in counts.items()
        if count > 1
    }

    print(
        f"Reference entry days: "
        f"{len(counts):,}"
    )

    print(
        f"Maximum entries/day: "
        f"{max(counts.values())}"
    )

    print(
        f"Days with >1 entry: "
        f"{len(multiple):,}"
    )

    if multiple:
        print()

        for day, count in list(
            multiple.items()
        )[:20]:

            print(
                f"  {day}: {count}"
            )

        raise AssertionError(
            "Reference logic generated multiple entries on a day."
        )

    print(
        "✅ Reference logic produces at most one breakout "
        "signal per NY day."
    )


# ============================================================
# LONG / SHORT DISTRIBUTION
# ============================================================

def audit_direction_distribution(
    expected_signals: list[dict],
):
    header("6. DIRECTION DISTRIBUTION")

    long_count = sum(
        1
        for x in expected_signals
        if x["direction"] == 1
    )

    short_count = sum(
        1
        for x in expected_signals
        if x["direction"] == -1
    )

    total = (
        long_count
        + short_count
    )

    print(
        f"Reference LONG:   {long_count:,}"
    )

    print(
        f"Reference SHORT:  {short_count:,}"
    )

    print(
        f"Reference TOTAL:  {total:,}"
    )

    if total:
        print(
            f"Long share:       "
            f"{long_count / total:.2%}"
        )

        print(
            f"Short share:      "
            f"{short_count / total:.2%}"
        )


# ============================================================
# SIGNAL TIME DISTRIBUTION
# ============================================================

def audit_signal_times(
    expected_signals: list[dict],
):
    header("7. SIGNAL TIME DISTRIBUTION")

    if not expected_signals:
        print(
            "No signals."
        )
        return

    times = pd.Series(
        [
            x["ny_timestamp"].strftime(
                "%H:%M"
            )
            for x in expected_signals
        ]
    )

    distribution = (
        times
        .value_counts()
        .sort_index()
    )

    print(
        distribution.to_string()
    )


# ============================================================
# UNEXPECTED SIGNALS
# ============================================================

def print_unexpected_signals(
    comparison: dict,
):
    header("8. UNEXPECTED STRATEGY SIGNALS")

    unexpected = comparison[
        "unexpected"
    ]

    if not unexpected:
        print(
            "✅ No unexpected strategy signals."
        )
        return

    print(
        f"Found {len(unexpected):,} unexpected "
        f"strategy signals."
    )

    print()

    for event in unexpected[
        :MAX_UNEXPECTED
    ]:

        timestamp = event[
            "source_timestamp"
        ]

        ny_timestamp = (
            timestamp
            .tz_convert(NY_TZ)
        )

        direction = (
            "LONG"
            if event["direction"] == 1
            else "SHORT"
        )

        print(
            f"{fmt_ts(timestamp)}"
            f" | {fmt_ts(ny_timestamp)}"
            f" | {direction}"
            f" | signal={event['signal_value']}"
        )


# ============================================================
# MISSING SIGNALS
# ============================================================

def print_missing_signals(
    comparison: dict,
):
    header("9. MISSING EXPECTED SIGNALS")

    missing = comparison[
        "missing"
    ]

    if not missing:
        print(
            "✅ No missing expected signals."
        )
        return

    print(
        f"Found {len(missing):,} missing "
        f"expected signals."
    )

    print()

    for expected in missing[
        :MAX_UNEXPECTED
    ]:

        direction = (
            "LONG"
            if expected["direction"] == 1
            else "SHORT"
        )

        print(
            f"{fmt_ts(expected['source_timestamp'])}"
            f" | {fmt_ts(expected['ny_timestamp'])}"
            f" | {direction}"
            f" | ORB H={fmt_price(expected['orb_high'])}"
            f" L={fmt_price(expected['orb_low'])}"
        )


# ============================================================
# DIRECTION MISMATCHES
# ============================================================

def print_direction_mismatches(
    comparison: dict,
):
    header("10. DIRECTION MISMATCHES")

    mismatches = comparison[
        "direction_mismatch"
    ]

    if not mismatches:
        print(
            "✅ No direction mismatches."
        )
        return

    print(
        f"Found {len(mismatches):,} direction mismatches."
    )

    for item in mismatches[
        :MAX_UNEXPECTED
    ]:

        expected = item[
            "expected"
        ]

        actual = item[
            "actual"
        ]

        expected_direction = (
            "LONG"
            if expected["direction"] == 1
            else "SHORT"
        )

        actual_direction = (
            "LONG"
            if actual["direction"] == 1
            else "SHORT"
        )

        print(
            f"{fmt_ts(expected['source_timestamp'])}"
            f" | expected={expected_direction}"
            f" | actual={actual_direction}"
        )


# ============================================================
# NEXT-BAR EXECUTION AUDIT
# ============================================================

def audit_execution_mapping(
    df: pd.DataFrame,
    expected_signals: list[dict],
):
    header("11. NEXT-BAR EXECUTION MAPPING")

    if not expected_signals:
        print(
            "No signals."
        )
        return

    checked = 0
    failures = []

    for expected in expected_signals:

        signal_timestamp = expected[
            "source_timestamp"
        ]

        execution = get_next_bar(
            df,
            signal_timestamp,
        )

        if execution is None:
            failures.append(
                (
                    signal_timestamp,
                    "no next bar",
                )
            )
            continue

        # Signal must occur strictly before execution.
        if not (
            execution["source_timestamp"]
            > signal_timestamp
        ):
            failures.append(
                (
                    signal_timestamp,
                    "execution timestamp is not after signal",
                )
            )
            continue

        checked += 1

    print(
        f"Signals checked:        {len(expected_signals):,}"
    )

    print(
        f"Valid next-bar mappings: {checked:,}"
    )

    print(
        f"Execution failures:     {len(failures):,}"
    )

    if failures:

        print()

        for timestamp, reason in failures[
            :MAX_UNEXPECTED
        ]:

            print(
                f"{fmt_ts(timestamp)} | {reason}"
            )

        raise AssertionError(
            "One or more signals failed next-bar execution mapping."
        )

    print(
        "✅ Every reference signal has a valid next execution bar."
    )


# ============================================================
# FINAL VERDICT
# ============================================================

def final_verdict(
    comparison: dict,
):
    header("12. FINAL VERDICT")

    matched = comparison[
        "matched"
    ]

    missing = len(
        comparison["missing"]
    )

    mismatches = len(
        comparison["direction_mismatch"]
    )

    unexpected = len(
        comparison["unexpected"]
    )

    expected_total = (
        matched
        + missing
        + mismatches
    )

    print(
        f"Reference signals:      {expected_total:,}"
    )

    print(
        f"Matched:                {matched:,}"
    )

    print(
        f"Missing:                {missing:,}"
    )

    print(
        f"Direction mismatches:   {mismatches:,}"
    )

    print(
        f"Unexpected:             {unexpected:,}"
    )

    print()

    if (
        expected_total > 0
        and matched == expected_total
        and mismatches == 0
        and unexpected == 0
    ):

        print(
            "✅ ORB SIGNAL AUDIT PASSED"
        )

        print()

        print(
            "The independent reference implementation "
            "and strategies/17_ny_orb_breakout.py agree."
        )

        print()

        print(
            "Next research step:"
        )

        print(
            "Build the TradePlan / SL-TP execution layer."
        )

        return True

    print(
        "❌ ORB SIGNAL AUDIT FAILED"
    )

    print()

    print(
        "DO NOT build the SL/TP execution layer yet."
    )

    print(
        "Resolve the signal discrepancies first."
    )

    return False


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(SEPARATOR)
    print("QUANTFORGE — NY ORB SIGNAL AUDIT")
    print(SEPARATOR)

    print()
    print(
        "This audit independently reconstructs the ORB "
        "reference logic."
    )

    print(
        "No P&L, SL, TP, or risk calculations are performed."
    )

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    df = load_data(
        DATA_PATH
    )

    run_data_checks(
        df
    )

    # --------------------------------------------------------
    # NY view
    # --------------------------------------------------------

    header("TIMEZONE / SESSION VIEW")

    df_ny = prepare_ny_view(
        df
    )

    print(
        f"Source timezone:  UTC+03:00"
    )

    print(
        f"NY timezone:      {NY_TZ}"
    )

    print(
        f"ORB:              {ORB_START} -> {ORB_END} NY"
    )

    print(
        f"Entry cutoff:     {ENTRY_CUTOFF} NY"
    )

    print()

    print(
        f"NY first bar:      "
        f"{fmt_ts(df_ny['ny_timestamp'].iloc[0])}"
    )

    print(
        f"NY last bar:       "
        f"{fmt_ts(df_ny['ny_timestamp'].iloc[-1])}"
    )

    # --------------------------------------------------------
    # Load strategy
    # --------------------------------------------------------

    generate_signals = load_strategy(
        STRATEGY_PATH
    )

    # --------------------------------------------------------
    # Strategy contract
    # --------------------------------------------------------

    signals = run_strategy_checks(
        df,
        generate_signals,
    )

    # --------------------------------------------------------
    # Independent reference signals
    # --------------------------------------------------------

    header("REFERENCE SIGNAL GENERATION")

    print(
        "Generating independent ORB reference signals..."
    )

    expected_signals = build_reference_signals(
        df_ny
    )

    print(
        f"Reference signals generated: "
        f"{len(expected_signals):,}"
    )

    # --------------------------------------------------------
    # Compare
    # --------------------------------------------------------

    comparison = compare_reference_to_strategy(
        df,
        df_ny,
        signals,
        expected_signals,
    )

    # --------------------------------------------------------
    # Detailed audit
    # --------------------------------------------------------

    print_detailed_examples(
        df,
        expected_signals,
        comparison,
    )

    # --------------------------------------------------------
    # Additional checks
    # --------------------------------------------------------

    audit_one_entry_per_day(
        expected_signals
    )

    audit_direction_distribution(
        expected_signals
    )

    audit_signal_times(
        expected_signals
    )

    print_unexpected_signals(
        comparison
    )

    print_missing_signals(
        comparison
    )

    print_direction_mismatches(
        comparison
    )

    audit_execution_mapping(
        df,
        expected_signals,
    )

    # --------------------------------------------------------
    # Verdict
    # --------------------------------------------------------

    passed = final_verdict(
        comparison
    )

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()