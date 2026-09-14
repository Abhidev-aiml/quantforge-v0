from dataclasses import dataclass
from typing import Literal

import pandas as pd

from engine.trade_plan import TradePlan


ExitReason = Literal[
    "STOP",
    "TARGET",
    "END_OF_DATA",
]


@dataclass(frozen=True)
class ExecutionResult:
    trade_date: object
    direction: str

    signal_time: object
    entry_time: object
    entry_price: float

    exit_time: object
    exit_price: float
    exit_reason: ExitReason

    stop_price: float
    target_price: float
    risk_per_unit: float

    bars_held: int

    @property
    def gross_points(self) -> float:
        if self.direction == "LONG":
            return self.exit_price - self.entry_price

        return self.entry_price - self.exit_price

    @property
    def r_multiple(self) -> float:
        if self.risk_per_unit <= 0:
            return 0.0

        return self.gross_points / self.risk_per_unit


def execute_trade(
    df: pd.DataFrame,
    trade_plan: TradePlan,
) -> ExecutionResult:
    """
    Execute one TradePlan against OHLC data.

    Execution assumptions
    ---------------------
    1. TradePlan entry occurs at the specified entry bar.
    2. The entry price is the TradePlan entry price.
    3. Stop/target are evaluated from the bars after entry.
    4. If both stop and target are touched in the same bar,
       stop is assumed to occur first.
    5. If the market gaps through the stop or target,
       execution occurs at the bar open.
    6. If neither stop nor target is reached before data ends,
       the trade exits at the final available close.
    """

    if df.empty:
        raise ValueError("Execution data cannot be empty.")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("Execution data must have a DatetimeIndex.")

    if trade_plan.entry_time not in df.index:
        raise ValueError(
            f"Entry time {trade_plan.entry_time} "
            "is not present in execution data."
        )

    entry_loc = df.index.get_loc(trade_plan.entry_time)

    if isinstance(entry_loc, slice):
        raise ValueError("Duplicate entry timestamps are not supported.")

    if isinstance(entry_loc, (list, tuple)):
        raise ValueError("Duplicate entry timestamps are not supported.")

    entry_loc = int(entry_loc)

    direction = trade_plan.direction

    if direction not in {"LONG", "SHORT"}:
        raise ValueError(
            f"Unsupported direction: {direction}"
        )

    entry_price = float(trade_plan.entry_price)
    stop_price = float(trade_plan.stop_price)
    target_price = float(trade_plan.target_price)

    # Validate directional geometry at execution time as well.
    if direction == "LONG":
        if stop_price >= entry_price:
            raise ValueError(
                "LONG stop must be below entry price."
            )

        if target_price <= entry_price:
            raise ValueError(
                "LONG target must be above entry price."
            )

    else:
        if stop_price <= entry_price:
            raise ValueError(
                "SHORT stop must be above entry price."
            )

        if target_price >= entry_price:
            raise ValueError(
                "SHORT target must be below entry price."
            )

    # No subsequent bar exists.
    if entry_loc >= len(df) - 1:
        return ExecutionResult(
            trade_date=trade_plan.trade_date,
            direction=direction,
            signal_time=trade_plan.signal_time,
            entry_time=trade_plan.entry_time,
            entry_price=entry_price,
            exit_time=trade_plan.entry_time,
            exit_price=entry_price,
            exit_reason="END_OF_DATA",
            stop_price=stop_price,
            target_price=target_price,
            risk_per_unit=trade_plan.risk_per_unit,
            bars_held=0,
        )

    # Evaluate bars AFTER the entry bar.
    for loc in range(entry_loc + 1, len(df)):

        bar = df.iloc[loc]

        timestamp = df.index[loc]

        open_price = float(bar["open"])
        high_price = float(bar["high"])
        low_price = float(bar["low"])

        bars_held = loc - entry_loc

        if direction == "LONG":

            # Gap through stop.
            if open_price <= stop_price:
                return ExecutionResult(
                    trade_date=trade_plan.trade_date,
                    direction=direction,
                    signal_time=trade_plan.signal_time,
                    entry_time=trade_plan.entry_time,
                    entry_price=entry_price,
                    exit_time=timestamp,
                    exit_price=open_price,
                    exit_reason="STOP",
                    stop_price=stop_price,
                    target_price=target_price,
                    risk_per_unit=trade_plan.risk_per_unit,
                    bars_held=bars_held,
                )

            # Gap through target.
            if open_price >= target_price:
                return ExecutionResult(
                    trade_date=trade_plan.trade_date,
                    direction=direction,
                    signal_time=trade_plan.signal_time,
                    entry_time=trade_plan.entry_time,
                    entry_price=entry_price,
                    exit_time=timestamp,
                    exit_price=open_price,
                    exit_reason="TARGET",
                    stop_price=stop_price,
                    target_price=target_price,
                    risk_per_unit=trade_plan.risk_per_unit,
                    bars_held=bars_held,
                )

            stop_hit = low_price <= stop_price
            target_hit = high_price >= target_price

            # Conservative ambiguity rule:
            # STOP wins if both are touched.
            if stop_hit:
                return ExecutionResult(
                    trade_date=trade_plan.trade_date,
                    direction=direction,
                    signal_time=trade_plan.signal_time,
                    entry_time=trade_plan.entry_time,
                    entry_price=entry_price,
                    exit_time=timestamp,
                    exit_price=stop_price,
                    exit_reason="STOP",
                    stop_price=stop_price,
                    target_price=target_price,
                    risk_per_unit=trade_plan.risk_per_unit,
                    bars_held=bars_held,
                )

            if target_hit:
                return ExecutionResult(
                    trade_date=trade_plan.trade_date,
                    direction=direction,
                    signal_time=trade_plan.signal_time,
                    entry_time=trade_plan.entry_time,
                    entry_price=entry_price,
                    exit_time=timestamp,
                    exit_price=target_price,
                    exit_reason="TARGET",
                    stop_price=stop_price,
                    target_price=target_price,
                    risk_per_unit=trade_plan.risk_per_unit,
                    bars_held=bars_held,
                )

        else:

            # Gap through stop.
            if open_price >= stop_price:
                return ExecutionResult(
                    trade_date=trade_plan.trade_date,
                    direction=direction,
                    signal_time=trade_plan.signal_time,
                    entry_time=trade_plan.entry_time,
                    entry_price=entry_price,
                    exit_time=timestamp,
                    exit_price=open_price,
                    exit_reason="STOP",
                    stop_price=stop_price,
                    target_price=target_price,
                    risk_per_unit=trade_plan.risk_per_unit,
                    bars_held=bars_held,
                )

            # Gap through target.
            if open_price <= target_price:
                return ExecutionResult(
                    trade_date=trade_plan.trade_date,
                    direction=direction,
                    signal_time=trade_plan.signal_time,
                    entry_time=trade_plan.entry_time,
                    entry_price=entry_price,
                    exit_time=timestamp,
                    exit_price=open_price,
                    exit_reason="TARGET",
                    stop_price=stop_price,
                    target_price=target_price,
                    risk_per_unit=trade_plan.risk_per_unit,
                    bars_held=bars_held,
                )

            stop_hit = high_price >= stop_price
            target_hit = low_price <= target_price

            # Conservative ambiguity rule:
            # STOP wins if both are touched.
            if stop_hit:
                return ExecutionResult(
                    trade_date=trade_plan.trade_date,
                    direction=direction,
                    signal_time=trade_plan.signal_time,
                    entry_time=trade_plan.entry_time,
                    entry_price=entry_price,
                    exit_time=timestamp,
                    exit_price=stop_price,
                    exit_reason="STOP",
                    stop_price=stop_price,
                    target_price=target_price,
                    risk_per_unit=trade_plan.risk_per_unit,
                    bars_held=bars_held,
                )

            if target_hit:
                return ExecutionResult(
                    trade_date=trade_plan.trade_date,
                    direction=direction,
                    signal_time=trade_plan.signal_time,
                    entry_time=trade_plan.entry_time,
                    entry_price=entry_price,
                    exit_time=timestamp,
                    exit_price=target_price,
                    exit_reason="TARGET",
                    stop_price=stop_price,
                    target_price=target_price,
                    risk_per_unit=trade_plan.risk_per_unit,
                    bars_held=bars_held,
                )

    # Neither SL nor TP was reached.
    final_timestamp = df.index[-1]
    final_close = float(df.iloc[-1]["close"])

    return ExecutionResult(
        trade_date=trade_plan.trade_date,
        direction=direction,
        signal_time=trade_plan.signal_time,
        entry_time=trade_plan.entry_time,
        entry_price=entry_price,
        exit_time=final_timestamp,
        exit_price=final_close,
        exit_reason="END_OF_DATA",
        stop_price=stop_price,
        target_price=target_price,
        risk_per_unit=trade_plan.risk_per_unit,
        bars_held=len(df) - 1 - entry_loc,
    )