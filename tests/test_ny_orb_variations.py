import pandas as pd

from strategies.orb_utils import (
    SOURCE_TZ,
    prepare_ny_index,
    orb_levels,
)


def make_day(
    date="2025-07-15",
    start_source_time="16:30",
):
    """
    Create six 5M candles with explicit UTC+3 timestamps.

    Summer:

        16:30 UTC+3
        ->
        09:30 EDT
    """

    times = pd.date_range(
        f"{date} {start_source_time}",
        periods=6,
        freq="5min",
        tz=SOURCE_TZ,
    )

    rows = []

    for i, ts in enumerate(times):

        rows.append(
            {
                "date": ts,
                "open": 3300.0 + i,
                "high": 3302.0 + i,
                "low": 3298.0 + i,
                "close": 3301.0 + i,
            }
        )

    return pd.DataFrame(rows)


def test_summer_utc3_converts_to_ny():

    df = make_day(
        date="2025-07-15",
        start_source_time="16:30",
    )

    ny = prepare_ny_index(df)

    assert (
        ny.index[0].strftime(
            "%Y-%m-%d %H:%M %Z"
        )
        ==
        "2025-07-15 09:30 EDT"
    )


def test_winter_utc3_converts_to_ny():

    df = make_day(
        date="2025-01-15",
        start_source_time="17:30",
    )

    ny = prepare_ny_index(df)

    assert (
        ny.index[0].strftime(
            "%Y-%m-%d %H:%M %Z"
        )
        ==
        "2025-01-15 09:30 EST"
    )


def test_orb_has_exactly_six_bars():

    df = make_day(
        date="2025-07-15",
        start_source_time="16:30",
    )

    df = prepare_ny_index(df)

    levels = orb_levels(df)

    assert levels is not None

    orb_high, orb_low = levels

    assert orb_high == 3307.0
    assert orb_low == 3298.0


def test_orb_is_invalid_when_bars_are_missing():

    df = make_day(
        date="2025-07-15",
        start_source_time="16:30",
    )

    df = df.drop(index=2)

    df = prepare_ny_index(df)

    levels = orb_levels(df)

    assert levels is None


def test_orb_is_invalid_when_bar_spacing_is_wrong():

    df = make_day(
        date="2025-07-15",
        start_source_time="16:30",
    )

    # Create a gap in the ORB sequence.
    df.loc[3, "date"] = pd.Timestamp(
        "2025-07-15 17:00:00",
        tz=SOURCE_TZ,
    )

    df = prepare_ny_index(df)

    levels = orb_levels(df)

    assert levels is None