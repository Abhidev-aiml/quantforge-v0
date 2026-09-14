import pytest

from engine.trade_plan import TradePlan


def test_long_trade_plan():
    plan = TradePlan(
        trade_date="2025-01-01",
        direction="LONG",
        signal_time="10:00",
        entry_time="10:05",
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        risk_per_unit=2.0,
    )

    assert plan.risk_points == 2.0
    assert plan.reward_points == 4.0
    assert plan.planned_rr == 2.0


def test_short_trade_plan():
    plan = TradePlan(
        trade_date="2025-01-01",
        direction="SHORT",
        signal_time="10:00",
        entry_time="10:05",
        entry_price=100.0,
        stop_price=102.0,
        target_price=96.0,
        risk_per_unit=2.0,
    )

    assert plan.risk_points == 2.0
    assert plan.reward_points == 4.0
    assert plan.planned_rr == 2.0


def test_long_stop_must_be_below_entry():
    with pytest.raises(
        ValueError,
        match="LONG stop must be below entry price",
    ):
        TradePlan(
            trade_date="2025-01-01",
            direction="LONG",
            signal_time="10:00",
            entry_time="10:05",
            entry_price=100.0,
            stop_price=101.0,
            target_price=104.0,
            risk_per_unit=1.0,
        )


def test_long_target_must_be_above_entry():
    with pytest.raises(
        ValueError,
        match="LONG target must be above entry price",
    ):
        TradePlan(
            trade_date="2025-01-01",
            direction="LONG",
            signal_time="10:00",
            entry_time="10:05",
            entry_price=100.0,
            stop_price=98.0,
            target_price=99.0,
            risk_per_unit=2.0,
        )


def test_short_stop_must_be_above_entry():
    with pytest.raises(
        ValueError,
        match="SHORT stop must be above entry price",
    ):
        TradePlan(
            trade_date="2025-01-01",
            direction="SHORT",
            signal_time="10:00",
            entry_time="10:05",
            entry_price=100.0,
            stop_price=99.0,
            target_price=96.0,
            risk_per_unit=1.0,
        )


def test_short_target_must_be_below_entry():
    with pytest.raises(
        ValueError,
        match="SHORT target must be below entry price",
    ):
        TradePlan(
            trade_date="2025-01-01",
            direction="SHORT",
            signal_time="10:00",
            entry_time="10:05",
            entry_price=100.0,
            stop_price=102.0,
            target_price=101.0,
            risk_per_unit=2.0,
        )


def test_risk_must_be_positive():
    with pytest.raises(
        ValueError,
        match="risk_per_unit must be greater than zero",
    ):
        TradePlan(
            trade_date="2025-01-01",
            direction="LONG",
            signal_time="10:00",
            entry_time="10:05",
            entry_price=100.0,
            stop_price=98.0,
            target_price=104.0,
            risk_per_unit=0.0,
        )


def test_invalid_direction():
    with pytest.raises(
        ValueError,
        match="Invalid direction",
    ):
        TradePlan(
            trade_date="2025-01-01",
            direction="INVALID",
            signal_time="10:00",
            entry_time="10:05",
            entry_price=100.0,
            stop_price=98.0,
            target_price=104.0,
            risk_per_unit=2.0,
        )
