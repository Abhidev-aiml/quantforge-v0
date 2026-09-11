from __future__ import annotations
import hashlib
from pathlib import Path
import pandas as pd

REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]
CACHE_DIR = Path("data/cache")


def load_csv(path: str | Path) -> pd.DataFrame:
    """Read a raw OHLCV CSV, validate it, return clean DataFrame."""
    df = pd.read_csv(path)
    df = _normalize_columns(df)
    df = _parse_dates(df)
    df = _sort_and_dedupe(df)
    df = _validate_ohlc(df)
    df = _clean_nans(df)
    return df


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower() for c in df.columns]

    # Accept common aliases
    aliases = {"date": "date", "datetime": "date", "timestamp": "date",
               "vol": "volume", "adj close": "adj_close"}
    
    df = df.rename(columns={k: v for k, v in aliases.items() if k in df.columns})

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}. "
                         f"Found: {list(df.columns)}")
    return df


def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    if "date" not in df.columns:
        raise ValueError("CSV must have a 'date' (or 'datetime') column")
    df["date"] = pd.to_datetime(df["date"], errors="raise")
    df = df.set_index("date")
    return df


def _sort_and_dedupe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_index()
    dupes = df.index.duplicated(keep="first")
    if dupes.any():
        print(f"⚠️  Removed {dupes.sum()} duplicate dates")
        df = df[~dupes]
    return df


def _validate_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    bad = (
        (df["low"] > df[["open", "close"]].min(axis=1)) |
        (df["high"] < df[["open", "close"]].max(axis=1)) |
        (df["high"] < df["low"]) |
        (df["close"] <= 0) |
        (df["volume"] < 0)
    )
    if bad.any():
        print(f"⚠️  Dropped {bad.sum()} rows that violate OHLC sanity")
        df = df[~bad]
    return df


def _clean_nans(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.dropna(subset=REQUIRED_COLUMNS)
    dropped = before - len(df)
    if dropped:
        print(f"⚠️  Dropped {dropped} rows with NaNs")
    return df


def cache(df: pd.DataFrame, source_path: str | Path) -> str:
    """Write df to Parquet; return a short hash for reproducibility."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = CACHE_DIR / f"{Path(source_path).stem}.parquet"
    df.to_parquet(out)

    digest = hashlib.sha256(df.to_csv().encode()).hexdigest()[:12]
    print(f"✅ Cached {len(df)} bars → {out}  (data_hash={digest})")
    return digest

#     #########################################################
#     # data.py for nifty csv
#     from __future__ import annotations

# import hashlib
# from pathlib import Path

# import pandas as pd


# # CHANGED:
# # Volume is no longer mandatory because master_5min.csv
# # contains OHLC data but does not contain volume.
# REQUIRED_COLUMNS = ["open", "high", "low", "close"]

# CACHE_DIR = Path("data/cache")


# def load_csv(path: str | Path) -> pd.DataFrame:
#     """Read a raw OHLC/OHLCV CSV, validate it, return clean DataFrame."""

#     df = pd.read_csv(path)

#     df = _normalize_columns(df)

#     df = _parse_dates(df)

#     df = _sort_and_dedupe(df)

#     df = _validate_ohlc(df)

#     df = _clean_nans(df)

#     return df


# def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:

#     df.columns = [c.strip().lower() for c in df.columns]

#     # CHANGED:
#     # Added "start_time": "date"
#     #
#     # master_5min.csv contains:
#     #
#     # start_time, open, high, low, close, end_time
#     #
#     # Internally, QuantForge uses "date" as the timestamp column.

#     aliases = {
#         "date": "date",
#         "datetime": "date",
#         "timestamp": "date",
#         "start_time": "date",

#         # Existing volume aliases.
#         # These remain useful for datasets that DO contain volume.
#         "vol": "volume",
#         "shares traded": "volume",

#         "adj close": "adj_close",
#     }

#     df = df.rename(
#         columns={
#             k: v
#             for k, v in aliases.items()
#             if k in df.columns
#         }
#     )

#     missing = [
#         c for c in REQUIRED_COLUMNS
#         if c not in df.columns
#     ]

#     if missing:
#         raise ValueError(
#             f"CSV missing required columns: {missing}. "
#             f"Found: {list(df.columns)}"
#         )

#     return df


# def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:

#     if "date" not in df.columns:
#         raise ValueError(
#             "CSV must have a 'date' (or 'datetime') column"
#         )

#     # CHANGED:
#     # Added format="mixed".
#     #
#     # This allows Pandas to handle different valid timestamp
#     # formats while errors="raise" still ensures malformed
#     # timestamps cause the loader to fail.
#     #
#     # Your master_5min.csv contains timezone-aware timestamps
#     # such as:
#     #
#     # 2015-01-09 09:15:00+05:30

#     df["date"] = pd.to_datetime(
#         df["date"],
#         format="mixed",
#         errors="raise",
#     )

#     df = df.set_index("date")

#     return df


# def _sort_and_dedupe(df: pd.DataFrame) -> pd.DataFrame:

#     df = df.sort_index()

#     dupes = df.index.duplicated(keep="first")

#     if dupes.any():

#         print(
#             f"⚠️  Removed {dupes.sum()} duplicate dates"
#         )

#         df = df[~dupes]

#     return df


# def _validate_ohlc(df: pd.DataFrame) -> pd.DataFrame:

#     # Validate the basic OHLC relationships.
#     #
#     # low must be <= open
#     # low must be <= close
#     # high must be >= open
#     # high must be >= close
#     # high must be >= low
#     # close must be positive

#     bad = (
#         (df["low"] > df[["open", "close"]].min(axis=1))
#         |
#         (df["high"] < df[["open", "close"]].max(axis=1))
#         |
#         (df["high"] < df["low"])
#         |
#         (df["close"] <= 0)
#     )

#     # CHANGED:
#     # Volume is OPTIONAL.
#     #
#     # If the dataset contains volume, validate it.
#     # If it does not contain volume, skip this check.
#     #
#     # This allows both:
#     #
#     # OHLC:
#     # open, high, low, close
#     #
#     # OHLCV:
#     # open, high, low, close, volume

#     if "volume" in df.columns:
#         bad = bad | (df["volume"] < 0)

#     if bad.any():

#         print(
#             f"⚠️  Dropped {bad.sum()} rows "
#             f"that violate OHLC sanity"
#         )

#         df = df[~bad]

#     return df


# def _clean_nans(df: pd.DataFrame) -> pd.DataFrame:

#     before = len(df)

#     # REQUIRED_COLUMNS contains only OHLC.
#     #
#     # Therefore volume is not required to be non-NaN.
#     df = df.dropna(
#         subset=REQUIRED_COLUMNS
#     )

#     dropped = before - len(df)

#     if dropped:

#         print(
#             f"⚠️  Dropped {dropped} rows with NaNs"
#         )

#     return df


# def cache(
#     df: pd.DataFrame,
#     source_path: str | Path
# ) -> str:
#     """Write df to Parquet; return a short hash for reproducibility."""

#     CACHE_DIR.mkdir(
#         parents=True,
#         exist_ok=True
#     )

#     out = CACHE_DIR / f"{Path(source_path).stem}.parquet"

#     df.to_parquet(out)

#     digest = hashlib.sha256(
#         df.to_csv().encode()
#     ).hexdigest()[:12]

#     print(
#         f"✅ Cached {len(df)} bars → {out} "
#         f"(data_hash={digest})"
#     )

#     return digest