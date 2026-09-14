"""
Regression tests for the NY ORB signal specification.

These tests protect the signal contract without testing P&L.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]

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

SOURCE_TZ = timezone(
    timedelta(hours=3)
)

NY_TZ = "America/New_York"


def load_strategy():
    spec = importlib.util.spec_from_file_location(
        "test_orb_strategy",
        STRATEGY_PATH,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Could not load ORB strategy."
        )

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    return module.generate_signals


@pytest.fixture(scope="module")
def df():

    if not DATA_PATH.exists():
        pytest.skip(
            f"XAUUSD 5M dataset not found: {DATA_PATH}"
        )

    raw = pd.read_csv(
        DATA_PATH
    )

    timestamps = pd.to_datetime(
        raw["date"],
        errors="raise",
    )

    index = pd.DatetimeIndex(
        timestamps
    ).tz_localize(
        SOURCE_TZ
    )

    raw.index = index

    return raw


@pytest.fixture(scope="module")
def signals(df):

    generate_signals = load_strategy()

    return generate_signals(
        df
    )


def test_strategy_signal_contract(
    df,
    signals,
):

    assert isinstance(
        signals,
        pd.Series,
    )

    assert len(signals) == len(df)

    assert signals.index.equals(
        df.index
    )

    assert signals.isna().sum() == 0

    assert signals.min() >= -1

    assert signals.max() <= 1


def test_strategy_has_signals(
    signals,
):

    non_zero = (
        signals != 0
    ).sum()

    assert non_zero > 0


def test_orb_strategy_is_one_bar_signal_pulse(
    signals,
):

    """
    The current ORB strategy is expected to produce a one-bar
    signal pulse rather than a persistent position.

    Therefore every non-zero signal should be followed by zero,
    unless it is the final bar.
    """

    non_zero_positions = (
        signals
        .to_numpy()
        != 0
    )

    for i in range(
        len(signals) - 1
    ):

        if non_zero_positions[i]:

            assert (
                signals.iloc[i + 1]
                == 0
            ), (
                "ORB strategy produced consecutive "
                "non-zero signal bars."
            )


def test_orb_strategy_has_at_most_one_signal_per_day(
    df,
    signals,
):

    ny_index = (
        df.index
        .tz_convert(NY_TZ)
    )

    signal_mask = (
        signals != 0
    )

    signal_dates = (
        pd.Series(
            ny_index.date,
            index=df.index,
        )
        [signal_mask]
    )

    counts = (
        signal_dates
        .value_counts()
    )

    if not counts.empty:
        assert counts.max() <= 1


def test_orb_strategy_has_both_directions(
    signals,
):

    long_count = (
        signals > 0
    ).sum()

    short_count = (
        signals < 0
    ).sum()

    assert long_count > 0

    assert short_count > 0