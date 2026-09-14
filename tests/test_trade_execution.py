import pandas as pd

from engine.trade_execution import execute_trade
from engine.trade_plan import TradePlan


def make_df(rows):
    index = pd.date_range(
        "2025-01-01 10:00",
        periods=len(rows),
        freq="5min",
    )

    return pd.DataFrame(rows, index=index)


def make_long_plan(
    entry_time,
    entry_price=100.0,
    stop_price=98.0,
    target_price=104.0,
):
    return TradePlan(
        trade_date="2025-01-01",
        direction="LONG",
        signal_time=entry_time,
        entry_time=entry_time,
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        risk_per_unit=abs(entry_price - stop_price),
    )


def make_short_plan(
    entry_time,
    entry_price=100.0,
    stop_price=102.0,
    target_price=96.0,
):
    return TradePlan(
        trade_date="2025-01-01",
        direction="SHORT",
        signal_time=entry_time,
        entry_time=entry_time,
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        risk_per_unit=abs(entry_price - stop_price),
    )


def test_long_target_is_hit():
    df = make_df(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 104, "low": 99, "close": 103},
        ]
    )

    plan = make_long_plan(df.index[0])

    result = execute_trade(df, plan)

    assert result.exit_reason == "TARGET"
    assert result.exit_price == 104
    assert result.r_multiple == 2.0


def test_long_stop_is_hit():
    df = make_df(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 101, "low": 98, "close": 99},
        ]
    )

    plan = make_long_plan(df.index[0])

    result = execute_trade(df, plan)

    assert result.exit_reason == "STOP"
    assert result.exit_price == 98
    assert result.r_multiple == -1.0


def test_short_target_is_hit():
    df = make_df(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 101, "low": 96, "close": 97},
        ]
    )

    plan = make_short_plan(df.index[0])

    result = execute_trade(df, plan)

    assert result.exit_reason == "TARGET"
    assert result.exit_price == 96
    assert result.r_multiple == 2.0


def test_short_stop_is_hit():
    df = make_df(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 102, "low": 99, "close": 101},
        ]
    )

    plan = make_short_plan(df.index[0])

    result = execute_trade(df, plan)

    assert result.exit_reason == "STOP"
    assert result.exit_price == 102
    assert result.r_multiple == -1.0


def test_both_stop_and_target_touched_stop_wins():
    df = make_df(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 105, "low": 97, "close": 101},
        ]
    )

    plan = make_long_plan(df.index[0])

    result = execute_trade(df, plan)

    assert result.exit_reason == "STOP"
    assert result.exit_price == 98
    assert result.r_multiple == -1.0


def test_long_gap_through_stop():
    df = make_df(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 96, "high": 97, "low": 95, "close": 96},
        ]
    )

    plan = make_long_plan(df.index[0])

    result = execute_trade(df, plan)

    assert result.exit_reason == "STOP"
    assert result.exit_price == 96


def test_long_gap_through_target():
    df = make_df(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 105, "high": 106, "low": 104, "close": 105},
        ]
    )

    plan = make_long_plan(df.index[0])

    result = execute_trade(df, plan)

    assert result.exit_reason == "TARGET"
    assert result.exit_price == 105


def test_short_gap_through_stop():
    df = make_df(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 103, "high": 104, "low": 103, "close": 103},
        ]
    )

    plan = make_short_plan(df.index[0])

    result = execute_trade(df, plan)

    assert result.exit_reason == "STOP"
    assert result.exit_price == 103


def test_entry_bar_is_not_used_for_stop_or_target():
    df = make_df(
        [
            {"open": 100, "high": 105, "low": 95, "close": 100},
            {"open": 100, "high": 101, "low": 99, "close": 100},
        ]
    )

    plan = make_long_plan(df.index[0])

    result = execute_trade(df, plan)

    assert result.exit_reason == "END_OF_DATA"


def test_end_of_data_exit():
    df = make_df(
        [
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 101, "low": 99, "close": 100},
        ]
    )

    plan = make_long_plan(df.index[0])

    result = execute_trade(df, plan)

    assert result.exit_reason == "END_OF_DATA"
    assert result.exit_price == 100
    assert result.bars_held == 1