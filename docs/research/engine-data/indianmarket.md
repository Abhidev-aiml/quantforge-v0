from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


# ============================================================
# CHANGED:
# "volume" has been removed from REQUIRED_COLUMNS.
#
# Why?
# Your master_5min.csv contains:
# start_time, open, high, low, close, end_time
#
# It does NOT contain volume.
#
# Volume is therefore optional for the data pipeline.
# ============================================================

REQUIRED_COLUMNS = ["open", "high", "low", "close"]

CACHE_DIR = Path("data/cache")


def load_csv(path: str | Path) -> pd.DataFrame:
    """
    Read a raw OHLC/OHLCV CSV, validate it, and return a clean DataFrame.

    Supports:
        - Standard date/datetime/timestamp columns
        - start_time columns used by the NIFTY 5-minute dataset
        - OHLC data without volume
        - OHLCV data with volume

    Returns:
        pd.DataFrame:
            Clean DataFrame indexed by timestamp.
    """

    df = pd.read_csv(path)

    df = _normalize_columns(df)
    df = _parse_dates(df)
    df = _sort_and_dedupe(df)
    df = _validate_ohlc(df)
    df = _clean_nans(df)

    return df


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names and convert common aliases
    into the column names used internally by QuantForge.
    """

    # Convert:
    # "Open"       -> "open"
    # "Start_Time" -> "start_time"
    # "Shares Traded" -> "shares traded"
    df.columns = [c.strip().lower() for c in df.columns]

    # ========================================================
    # CHANGED:
    # Added "start_time": "date"
    #
    # Your master_5min.csv uses:
    #
    # start_time
    # open
    # high
    # low
    # close
    # end_time
    #
    # Internally, the engine expects the timestamp column
    # to be called "date".
    # ========================================================

    aliases = {
        "date": "date",
        "datetime": "date",
        "timestamp": "date",
        "start_time": "date",

        # Existing volume aliases
        "vol": "volume",
        "shares traded": "volume",

        # Existing alias
        "adj close": "adj_close",
    }

    df = df.rename(
        columns={
            source: target
            for source, target in aliases.items()
            if source in df.columns
        }
    )

    # Check that the required OHLC columns exist.
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]

    if missing:
        raise ValueError(
            f"CSV missing required columns: {missing}. "
            f"Found: {list(df.columns)}"
        )

    return df


def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse the timestamp column and make it the DataFrame index.

    We use errors='raise' deliberately.

    A malformed timestamp is a structural data problem and
    should NOT silently be converted into NaT.
    """

    if "date" not in df.columns:
        raise ValueError(
            "CSV must have a 'date', 'datetime', 'timestamp', "
            "or 'start_time' column"
        )

    # ========================================================
    # CHANGED:
    # Added format='mixed'.
    #
    # Why?
    # Pandas can encounter different timestamp representations
    # across datasets. format='mixed' allows Pandas to parse
    # each timestamp appropriately while errors='raise' still
    # ensures malformed timestamps cause a hard failure.
    #
    # This also removes the warning we saw with the NIFTY
    # daily dataset.
    # ========================================================

    df["date"] = pd.to_datetime(
        df["date"],
        format="mixed",
        errors="raise",
    )

    # Use timestamp as the index.
    df = df.set_index("date")

    return df


def _sort_and_dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sort data chronologically and remove duplicate timestamps.

    If duplicate timestamps exist, the first occurrence is kept.
    """

    # Sort chronologically.
    df = df.sort_index()

    # Find duplicate timestamps.
    dupes = df.index.duplicated(keep="first")

    if dupes.any():
        print(
            f"⚠️  Removed {dupes.sum()} duplicate timestamps"
        )

        df = df[~dupes]

    return df


def _validate_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate basic OHLC sanity conditions.

    Invalid rows are removed.

    Conditions:

        low <= open
        low <= close
        high >= open
        high >= close
        high >= low
        close > 0

    If volume exists, it must also be >= 0.
    """

    # ========================================================
    # CHANGED:
    # Removed the unconditional:
    #
    #     (df["volume"] < 0)
    #
    # because volume is optional.
    #
    # Instead, we check volume ONLY if the dataset contains it.
    # ========================================================

    bad = (
        (df["low"] > df[["open", "close"]].min(axis=1))
        |
        (df["high"] < df[["open", "close"]].max(axis=1))
        |
        (df["high"] < df["low"])
        |
        (df["close"] <= 0)
    )

    # ========================================================
    # CHANGED:
    # Volume validation is conditional.
    #
    # This means both of these are valid:
    #
    # Dataset A:
    # open, high, low, close
    #
    # Dataset B:
    # open, high, low, close, volume
    # ========================================================

    if "volume" in df.columns:
        bad = bad | (df["volume"] < 0)

    if bad.any():
        print(
            f"⚠️  Dropped {bad.sum()} rows "
            f"that violate OHLC sanity"
        )

        df = df[~bad]

    return df


def _clean_nans(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove rows containing NaN values in required OHLC columns.

    Volume is not included because it is optional.
    """

    before = len(df)

    # REQUIRED_COLUMNS now contains only:
    #
    # open, high, low, close
    #
    # Therefore a missing volume value does not cause an OHLC
    # row to be removed.
    df = df.dropna(subset=REQUIRED_COLUMNS)

    dropped = before - len(df)

    if dropped:
        print(
            f"⚠️  Dropped {dropped} rows with NaNs"
        )

    return df


def cache(df: pd.DataFrame, source_path: str | Path) -> str:
    """
    Write the cleaned DataFrame to Parquet.

    Returns:
        A short SHA-256 hash that identifies the exact
        cleaned dataset used for reproducibility.
    """

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    out = CACHE_DIR / f"{Path(source_path).stem}.parquet"

    df.to_parquet(out)

    # Generate deterministic hash from cleaned data.
    digest = hashlib.sha256(
        df.to_csv().encode()
    ).hexdigest()[:12]

    print(
        f"✅ Cached {len(df)} bars → {out} "
        f"(data_hash={digest})"
    )

    return digest