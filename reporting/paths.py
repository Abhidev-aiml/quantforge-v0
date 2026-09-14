"""
Report path scheme and naming conventions.

Reports live in a dedicated directory (default: reports/) organized by
<symbol>-<timeframe>-<strategy>-<YYYYMMDD>-<HHMMSS>.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from pathlib import Path


# ---- inference helpers ----------------------------------------------

_TIMEFRAME_PATTERNS = [
    # Multi-bar timeframes — longest tokens first
    (re.compile(r"_?1?440(?:_|$)",   re.I), "1d"),   # 1440 min = daily
    (re.compile(r"_?1d(?:_|$)",      re.I), "1d"),
    (re.compile(r"_?daily(?:_|$)",   re.I), "1d"),
    (re.compile(r"_?240(?:_|$)",     re.I), "4h"),   # 240 min = 4h
    (re.compile(r"_?4h(?:_|$)",      re.I), "4h"),
    (re.compile(r"_?60(?:_|$)",      re.I), "1h"),   # 60 min = 1h
    (re.compile(r"_?1h(?:_|$)",      re.I), "1h"),
    (re.compile(r"_?30m?(?:_|$)",    re.I), "30m"),
    (re.compile(r"_?15m?(?:_|$)",    re.I), "15m"),
    (re.compile(r"_?5m?(?:_|$)",     re.I), "5m"),
    (re.compile(r"_?1m(?:_|$)",      re.I), "1m"),
]


def infer_timeframe(data_path: str | Path | None) -> str:
    """Infer timeframe from a CSV filename. Returns 'na' if ntch.

    Recognises both numeric-only ('1440', '240', '60') and unit-suffixed
    ('1d', '4h', '1h', '15m', '5m') forms. Only strips our own data
    suffix ('_comma', '_data') — never strips a token that might be the
    timeframe signal itself.
    """
    if data_path is None:
        return "na"
    stem = Path(data_path).stem
    # Only strip OUR suffixes, never a possible timeframe signal
    for suffix in ("_comma", "_data"):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    for pattern, tf in _TIMEFRAME_PATTERNS:
        if pattern.search(stem):
            return tf
    return "na"


def slug(s: str) -> str:
    """Lowercase, keep alnum and hyphens, collapse repeats."""
    s = s.lower()
    s = s.replace("_", "-").replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "na"


def build_report_name(manifest: dict, timestamp: datetime | None = None) -> str:
    """
    Produce a human-readable report folder name from a run manifest.

    Format: <symbol>-<timeframe>-<strategy>-<YYYYMMDD>-<HHMMSS>
    """
    config = manifest.get("config", {})
    data_cfg = config.get("data", {}) or {}
    strategy_cfg = config.get("strategy", {}) or {}

    symbol = slug(data_cfg.get("symbol", "asset"))

    # Prefer explicit timeframe in config; else infer from data path
    tf = data_cfg.get("timeframe") or infer_timeframe(data_cfg.get("path"))
    timeframe = slug(tf)

    strategy_path = strategy_cfg.get("path", "strategy")
    strategy = slug(Path(strategy_path).stem)

    if timestamp is None:
        ts_raw = manifest.get("started_utc") or datetime.now(timezone.utc).isoformat()
        try:
            timestamp = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            timestamp = datetime.now(timezone.utc)

    stamp = timestamp.strftime("%Y%m%d-%H%M%S")
    return f"{symbol}-{timeframe}-{strategy}-{stamp}"


# ---- path resolution ------------------------------------------------

def resolve_report_dir(
    reports_root: str | Path,
    manifest: dict,
    override: str | Path | None = None,
) -> Path:
    """
    Return (and create) the report directory for this run.

    If `override` is provided, use it verbatim. Otherwise build the name
    from the manifest.
    """
    root = Path(reports_root)
    if override:
        out = Path(override)
        if not out.is_absolute():
            out = root / out
    else:
        out = root / build_report_name(manifest)
    out.mkdir(parents=True, exist_ok=True)
    return out
