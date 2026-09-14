from dataclasses import dataclass
from typing import Literal


Direction = Literal["LONG", "SHORT"]


@dataclass(frozen=True)
class TradePlan:
    trade_date: object
    direction: Direction

    signal_time: object
    entry_time: object

    entry_price: float
    stop_price: float
    target_price: float

    risk_per_unit: float

    def __post_init__(self):
        if self.direction not in {"LONG", "SHORT"}:
            raise ValueError(
                f"Invalid direction: {self.direction}"
            )

        if self.risk_per_unit <= 0:
            raise ValueError(
                "risk_per_unit must be greater than zero."
            )

        if self.direction == "LONG":
            if self.stop_price >= self.entry_price:
                raise ValueError(
                    "LONG stop must be below entry price."
                )

            if self.target_price <= self.entry_price:
                raise ValueError(
                    "LONG target must be above entry price."
                )

        else:
            if self.stop_price <= self.entry_price:
                raise ValueError(
                    "SHORT stop must be above entry price."
                )

            if self.target_price >= self.entry_price:
                raise ValueError(
                    "SHORT target must be below entry price."
                )

    @property
    def risk_points(self) -> float:
        return abs(
            self.entry_price - self.stop_price
        )

    @property
    def reward_points(self) -> float:
        return abs(
            self.target_price - self.entry_price
        )

    @property
    def planned_rr(self) -> float:
        if self.risk_points <= 0:
            return 0.0

        return (
            self.reward_points /
            self.risk_points
        )