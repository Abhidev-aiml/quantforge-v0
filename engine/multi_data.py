"""
Multi-symbol data loading and alignment.

Loads one CSV per symbol and aligns them to a common DatetimeIndex.
Missing bars are forward-filled for pricing but not for trading.
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterable

import pandas as pd
import hashlib
from engine.data import load_csv


def load_multi_csv(
    symbol_paths: dict[str, str | Path],
    start: str | None = None,
    end: str | None = None,
) -> dict[str, pd.DataFrame]:
    """Load multiple CSVs, keyed by symbol.

    Args:
        symbol_paths: {symbol: csv_path}
        start, end:   optional date bounds (inclusive), YYYY-MM-DD

    Returns:
        dict[symbol, DataFrame] with OHLCV columns and DatetimeIndex.
    """
    out: dict[str, pd.DataFrame] = {}
    for sym, path in symbol_paths.items():
        df = load_csv(path)
        if start is not None:
            df = df[df.index >= pd.Timestamp(start)]
        if end is not None:
            df = df[df.index <= pd.Timestamp(end)]
        if len(df) < 2:
            raise ValueError(f"{sym}: fewer than 2 bars after date filter")
        out[sym] = df
    return out


def common_index(data: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    """Union of all symbols' dates, sorted.

    Union (not intersection) so that a symbol listed on different
    holidays doesn't shrink the whole backtest. Missing values get
    handled per-bar by the engine.
    """
    idx: pd.DatetimeIndex | None = None
    for df in data.values():
        idx = df.index if idx is None else idx.union(df.index)
    if idx is None:
        raise ValueError("empty data dict")
    return idx.sort_values()


def align_to_index(
    data: dict[str, pd.DataFrame],
    index: pd.DatetimeIndex,
) -> dict[str, pd.DataFrame]:
    """Reindex each symbol to the common index.

    Price columns are forward-filled (last known price persists), volume
    is filled with zero, and any leading NaN rows are dropped per symbol.
    """
    out: dict[str, pd.DataFrame] = {}
    for sym, df in data.items():
        aligned = df.reindex(index)
        aligned["open"] = aligned["open"].ffill()
        aligned["high"] = aligned["high"].ffill()
        aligned["low"] = aligned["low"].ffill()
        aligned["close"] = aligned["close"].ffill()
        aligned["volume"] = aligned["volume"].fillna(0.0)
        out[sym] = aligned
    return out


def prepare_multi_data(
    symbol_paths: dict[str, str | Path],
    start: str | None = None,
    end: str | None = None,
) -> tuple[dict[str, pd.DataFrame], pd.DatetimeIndex]:
    """One-call loader: load, align, return (data, common_index)."""
    raw = load_multi_csv(symbol_paths, start=start, end=end)
    idx = common_index(raw)
    aligned = align_to_index(raw, idx)
    return aligned, idx

def discover_symbols(
    directory: str | Path,
    pattern: str = "*.csv",
    exclude: list[str] | None = None,
) -> dict[str, str]:
    """Return {symbol: path} for every CSV in directory matching pattern.

    Symbol is the filename stem. Files in `exclude` (by stem or name)
    are skipped.
    """
    directory = Path(directory)
    exclude = set(exclude or [])
    out: dict[str, str] = {}
    for p in sorted(directory.glob(pattern)):
        if p.stem in exclude or p.name in exclude:
            continue
        out[p.stem] = str(p)
    if not out:
        raise ValueError(f"no CSVs found in {directory} matching {pattern}")
    return out
def compute_universe_hash(data: dict[str, pd.DataFrame]) -> str:
    """Deterministic SHA-256 hash of a multi-symbol data universe.

    Sorted by symbol name so the hash is independent of dict insertion
    order. Each symbol's OHLCV content contributes to the digest.
    """
    parts = []
    for sym in sorted(data.keys()):
        df = data[sym]
        # Use a stable content fingerprint: index + all OHLCV columns
        payload = df[["open", "high", "low", "close", "volume"]].to_csv()
        idx_payload = pd.Series(df.index.astype(str)).to_csv(index=False)
        sym_hash = hashlib.sha256(
            (idx_payload + payload).encode()
        ).hexdigest()
        parts.append(f"{sym}:{sym_hash}")
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]