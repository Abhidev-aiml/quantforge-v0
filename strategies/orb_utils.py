"""Shared utilities for NY 30-minute ORB research on XAUUSD 5M data.

IMPORTANT
---------
Raw XAUUSD timestamps are interpreted as UTC+3 and converted to
America/New_York before session logic is applied.

The strategy emits a portfolio target signal:
    +1.0 = long
    -1.0 = short
     0.0 = flat/no position

The existing QuantForge engine executes a signal on the next bar open.
These strategy files therefore do NOT embed stop/target logic.
"""

from __future__ import annotations

from datetime import timezone, timedelta
from typing import Optional

import numpy as np
import pandas as pd

SOURCE_TZ = timezone(timedelta(hours=3))
NY_TZ = "America/New_York"

ORB_START = "09:30"
ORB_END = "10:00"
ENTRY_CUTOFF = "15:30"


def prepare_ny_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy of the DataFrame whose index is a timezone-aware
    America/New_York DatetimeIndex.

    Accepted input:

    1. DataFrame with a DatetimeIndex

    OR

    2. DataFrame with a 'date' column

    Naive timestamps:
        interpreted as UTC+3.

    Timezone-aware timestamps:
        converted to UTC+3 first, then America/New_York.

    Parameters
    ----------
    df:
        Input OHLC DataFrame.

    Returns
    -------
    pd.DataFrame
        Copy of df with NY timezone-aware DatetimeIndex.
    """

    out = df.copy()

    # --------------------------------------------------------
    # Obtain timestamps
    # --------------------------------------------------------

    if isinstance(out.index, pd.DatetimeIndex):

        idx = out.index

    elif "date" in out.columns:

        # pd.to_datetime(Series) returns a Series.
        # Explicitly convert it into a DatetimeIndex so the
        # rest of the function has one consistent type.
        idx = pd.DatetimeIndex(
            pd.to_datetime(out["date"])
        )

    else:

        raise ValueError(
            "DataFrame must have either a DatetimeIndex "
            "or a 'date' column."
        )

    # --------------------------------------------------------
    # Interpret raw timestamps
    # --------------------------------------------------------

    if idx.tz is None:

        # Your XAUUSD dataset is interpreted as UTC+3.
        idx = idx.tz_localize(SOURCE_TZ)

    else:

        # If timestamps already contain timezone information,
        # normalize them to UTC+3 first.
        idx = idx.tz_convert(SOURCE_TZ)

    # --------------------------------------------------------
    # Convert to New York
    # --------------------------------------------------------

    idx = idx.tz_convert(NY_TZ)

    # --------------------------------------------------------
    # Set final index
    # --------------------------------------------------------

    out.index = idx

    return out


def validate_5m_data(df: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing OHLC columns: {sorted(missing)}")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("Expected a DatetimeIndex after prepare_ny_index().")

    if df.index.tz is None:
        raise TypeError("Index must be timezone-aware.")


def _empty_signal(df: pd.DataFrame) -> pd.Series:
    return pd.Series(0.0, index=df.index, dtype=float)


def _session_rows(day: pd.DataFrame) -> pd.DataFrame:
    t = day.index
    return day[(t.time >= pd.Timestamp(ORB_START).time()) &
               (t.time < pd.Timestamp(ORB_END).time())]


def _atr(day: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = day["close"].shift(1)
    tr = pd.concat(
        [
            day["high"] - day["low"],
            (day["high"] - prev_close).abs(),
            (day["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def orb_levels(day: pd.DataFrame) -> Optional[tuple[float, float]]:
    """Return (ORB high, ORB low) only when exactly six 5M bars exist."""
    opening = _session_rows(day)

    if len(opening) != 6:
        return None

    return float(opening["high"].max()), float(opening["low"].min())


def body_ratio(row: pd.Series) -> float:
    rng = float(row["high"] - row["low"])
    if rng <= 0:
        return 0.0
    return float(abs(row["close"] - row["open"]) / rng)


def close_location(row: pd.Series) -> float:
    """0 = low of candle, 1 = high of candle."""
    rng = float(row["high"] - row["low"])
    if rng <= 0:
        return 0.5
    return float((row["close"] - row["low"]) / rng)


def rejection_strength(row: pd.Series, level: float, direction: int) -> bool:
    """Require the retest candle to interact with the level and close away.

    Long:
      low touches/penetrates ORB high and close remains above it.
    Short:
      high touches/penetrates ORB low and close remains below it.
    """
    if direction == 1:
        return float(row["low"]) <= level and float(row["close"]) > level
    if direction == -1:
        return float(row["high"]) >= level and float(row["close"]) < level
    return False


def iter_days(df: pd.DataFrame):
    """Yield (date, intraday_day_df) in NY calendar dates."""
    for day, day_df in df.groupby(df.index.date, sort=True):
        yield day, day_df


def find_breakout(day: pd.DataFrame, orb_high: float, orb_low: float):
    """Find the first qualifying breakout after 10:00 NY.

    Returns:
        (direction, breakout_position, breakout_row)
    """
    post = day[day.index.time >= pd.Timestamp(ORB_END).time()]

    for pos, (_, row) in enumerate(post.iterrows()):
        if float(row["close"]) > orb_high:
            return 1, pos, row
        if float(row["close"]) < orb_low:
            return -1, pos, row

    return None


def find_retest_confirmation(
    day: pd.DataFrame,
    orb_high: float,
    orb_low: float,
    breakout_pos: int,
    direction: int,
    require_rejection: bool = False,
    min_body_ratio: Optional[float] = None,
    min_clv: Optional[float] = None,
):
    """Find confirmation after a breakout.

    breakout_pos is the position inside the post-10:00 DataFrame.
    Retest must be the immediately following 5M candle.
    Confirmation must be the candle after the retest.
    """
    post = day[day.index.time >= pd.Timestamp(ORB_END).time()]

    if breakout_pos + 2 >= len(post):
        return None

    _, retest = next(iter(post.iloc[breakout_pos + 1:breakout_pos + 2].iterrows()))
    _, confirmation = next(
        iter(post.iloc[breakout_pos + 2:breakout_pos + 3].iterrows())
    )

    level = orb_high if direction == 1 else orb_low

    if not rejection_strength(retest, level, direction):
        return None

    if require_rejection:
        if direction == 1:
            # Lower wick must reach the boundary and candle must close in upper half.
            if close_location(retest) < 0.50:
                return None
        else:
            # Upper wick must reach boundary and candle must close in lower half.
            if close_location(retest) > 0.50:
                return None

    if direction == 1:
        if float(confirmation["close"]) <= float(breakout_row_for(post, breakout_pos)["high"]):
            return None
    else:
        if float(confirmation["close"]) >= float(breakout_row_for(post, breakout_pos)["low"]):
            return None

    if min_body_ratio is not None and body_ratio(confirmation) < min_body_ratio:
        return None

    if min_clv is not None:
        clv = close_location(confirmation)
        if direction == 1 and clv < min_clv:
            return None
        if direction == -1 and clv > 1.0 - min_clv:
            return None

    return confirmation


def breakout_row_for(post: pd.DataFrame, breakout_pos: int) -> pd.Series:
    return post.iloc[breakout_pos]


def generate_orb_signals(
    df: pd.DataFrame,
    mode: str = "breakout",
    min_body_ratio: Optional[float] = None,
    min_clv: Optional[float] = None,
    orb_atr_min: Optional[float] = None,
    orb_atr_max: Optional[float] = None,
    atr_regime_quantile: Optional[float] = None,
    entry_cutoff: Optional[str] = ENTRY_CUTOFF,
) -> pd.Series:
    """
    Generate NY ORB directional signals.

    IMPORTANT INDEX CONTRACT
    ------------------------

    The ORB logic internally operates on an
    America/New_York timezone-aware index.

    However, QuantForge requires the strategy to return
    a Series whose index is EXACTLY the same as the
    input DataFrame index.

    Therefore:

        input index
            ↓
        preserve original index
            ↓
        convert internally to NY
            ↓
        generate signals
            ↓
        map signals back to original index
            ↓
        return

    Supported modes:

        breakout
        retest
        retest_rejection
        quality
        clv
        orb_atr
        atr_regime
    """

    # ========================================================
    # PRESERVE THE ORIGINAL QUANTFORGE INDEX
    # ========================================================

    original_index = df.index.copy()

    # ========================================================
    # PREPARE NY-TIME DATA
    # ========================================================

    work = prepare_ny_index(df)

    validate_5m_data(work)

    # ========================================================
    # SORT FOR CHRONOLOGICAL PROCESSING
    # ========================================================

    work = work.sort_index()

    # ========================================================
    # SIGNAL SERIES
    #
    # This signal is temporarily indexed by NY timestamps.
    # It will be mapped back to the original index before
    # returning.
    # ========================================================

    signal = _empty_signal(work)

    # ========================================================
    # ATR
    # ========================================================

    atr = _atr(
        work,
        period=14,
    )

    # ========================================================
    # ENTRY CUTOFF
    # ========================================================

    if entry_cutoff is not None:

        cutoff_time = pd.Timestamp(
            entry_cutoff
        ).time()

    else:

        cutoff_time = None

    # ========================================================
    # PROCESS EACH NY CALENDAR DAY
    # ========================================================

    for _, day in iter_days(work):

        # ----------------------------------------------------
        # Build ORB
        # ----------------------------------------------------

        levels = orb_levels(day)

        if levels is None:
            continue

        orb_high, orb_low = levels

        orb_range = (
            orb_high - orb_low
        )

        if orb_range <= 0:
            continue

        # ----------------------------------------------------
        # Find first breakout
        # ----------------------------------------------------

        breakout = find_breakout(
            day,
            orb_high,
            orb_low,
        )

        if breakout is None:
            continue

        (
            direction,
            breakout_pos,
            breakout_row,
        ) = breakout

        # ====================================================
        # BREAKOUT ENTRY CUTOFF
        # ====================================================

        if (
            cutoff_time is not None
            and
            breakout_row.name.time()
            >
            cutoff_time
        ):
            continue

        # ====================================================
        # PURE BREAKOUT
        # ====================================================

        if mode == "breakout":

            signal.loc[
                breakout_row.name
            ] = float(direction)

            continue

        # ====================================================
        # ORB / ATR FILTER
        # ====================================================

        if mode == "orb_atr":

            # IMPORTANT:
            #
            # Do not use ATR from the breakout candle.
            #
            # Only information available BEFORE the breakout
            # candle is allowed.

            atr_before = (
                atr
                .loc[:breakout_row.name]
                .iloc[:-1]
                .dropna()
            )

            if len(atr_before) == 0:
                continue

            current_atr = float(
                atr_before.iloc[-1]
            )

            if current_atr <= 0:
                continue

            orb_atr_ratio = (
                orb_range
                /
                current_atr
            )

            # Minimum ORB / ATR
            if (
                orb_atr_min is not None
                and
                orb_atr_ratio < orb_atr_min
            ):
                continue

            # Maximum ORB / ATR
            if (
                orb_atr_max is not None
                and
                orb_atr_ratio > orb_atr_max
            ):
                continue

        # ====================================================
        # ATR REGIME FILTER
        # ====================================================

        if mode == "atr_regime":

            # Again, breakout candle is excluded.
            atr_before = (
                atr
                .loc[:breakout_row.name]
                .iloc[:-1]
                .dropna()
            )

            # Need enough observations.
            if len(atr_before) < 50:
                continue

            quantile = (
                atr_regime_quantile
                if atr_regime_quantile is not None
                else 0.50
            )

            threshold = atr_before.quantile(
                quantile
            )

            current_atr = float(
                atr_before.iloc[-1]
            )

            if current_atr < float(
                threshold
            ):
                continue

        # ====================================================
        # RETEST + CONFIRMATION
        # ====================================================

        confirmation = find_retest_confirmation(
            day=day,
            orb_high=orb_high,
            orb_low=orb_low,
            breakout_pos=breakout_pos,
            direction=direction,
            require_rejection=(
                mode == "retest_rejection"
            ),
            min_body_ratio=min_body_ratio,
            min_clv=min_clv,
        )

        if confirmation is None:
            continue

        # ====================================================
        # CONFIRMATION CUTOFF
        # ====================================================

        if (
            cutoff_time is not None
            and
            confirmation.name.time()
            >
            cutoff_time
        ):
            continue

        # ====================================================
        # GENERATE SIGNAL
        # ====================================================

        signal.loc[
            confirmation.name
        ] = float(direction)

    # ========================================================
    # NORMALIZE
    # ========================================================

    signal = (
        signal
        .fillna(0.0)
        .astype(float)
    )

    # ========================================================
    # MAP NY SIGNALS BACK TO ORIGINAL DATA INDEX
    # ========================================================
    #
    # This is the critical QuantForge integration step.
    #
    # The engine expects:
    #
    #     returned_signal.index == df.index
    #
    # We therefore reconstruct the NY representation of the
    # ORIGINAL timestamps and use it to look up the signals.
    # ========================================================

    if isinstance(
        original_index,
        pd.DatetimeIndex
    ):

        original_dates = original_index

    else:

        original_dates = pd.DatetimeIndex(
            pd.to_datetime(original_index)
        )

    # --------------------------------------------------------
    # Convert original timestamps to the same NY representation
    # --------------------------------------------------------

    if original_dates.tz is None:

        original_ny_index = (
            original_dates
            .tz_localize(SOURCE_TZ)
            .tz_convert(NY_TZ)
        )

    else:

        original_ny_index = (
            original_dates
            .tz_convert(SOURCE_TZ)
            .tz_convert(NY_TZ)
        )

    # --------------------------------------------------------
    # Reindex signal against the original timestamp order
    # --------------------------------------------------------

    final_signal = signal.reindex(
        original_ny_index,
        fill_value=0.0,
    )

    # --------------------------------------------------------
    # Restore EXACT original QuantForge index
    # --------------------------------------------------------

    final_signal.index = original_index

    # --------------------------------------------------------
    # Final safety checks
    # --------------------------------------------------------

    final_signal = (
        final_signal
        .fillna(0.0)
        .astype(float)
    )

    if not final_signal.index.equals(
        df.index
    ):
        raise RuntimeError(
            "ORB strategy failed to restore the exact "
            "original data index."
        )

    return final_signal