from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import pandas as pd


@dataclass
class Portfolio:
    cash: float
    positions: dict[str, float] = field(default_factory=dict)
    equity_curve: list[dict] = field(default_factory=list)
    fills: list[dict] = field(default_factory=list)

    def equity(self, prices: dict[str, float]) -> float:
        pos_value = sum(qty * prices[sym] for sym, qty in self.positions.items())
        return self.cash + pos_value

    def snapshot(self, ts, prices: dict[str, float]) -> None:
        self.equity_curve.append({"timestamp": ts, "equity": self.equity(prices)})


class BacktestEngine:
    """
    Realistic single-asset backtester.

    Rules:
      - Signal on bar t's close → execute at bar t+1's open
      - Slippage applied in the direction of the trade
      - Commission charged on notional traded
      - No leverage beyond [-1, +1] weight
    """

    def __init__(
        self,
        symbol: str = "ASSET",
        initial_cash: float = 100_000.0,
        commission_bps: float = 1.0,
        slippage_bps: float = 5.0,
        no_trade_band: float = 0.01,
        warmup_bars: int = 0, 
    ):
        self.symbol = symbol
        self.pf = Portfolio(cash=initial_cash)
        self.commission_bps = commission_bps
        self.slippage_bps = slippage_bps
        self.no_trade_band = no_trade_band
        self.warmup_bars = warmup_bars


    # ---- main loop ------------------------------------------------

    def run(self, df: pd.DataFrame, signals: pd.Series) -> pd.DataFrame:
        opens  = df["open"].to_dict()
        closes = df["close"].to_dict()

        pending_target: Optional[float] = None
        for i, ts in enumerate(df.index):
        # NEW: ignore signals during warmup
            if i < self.warmup_bars:
                self.pf.snapshot(ts, {self.symbol: closes[ts]})
                continue

            if pending_target is not None:
                self._rebalance_at(pending_target, opens[ts], ts)

            self.pf.snapshot(ts, {self.symbol: closes[ts]})

            if ts in signals.index:
                v = signals.loc[ts]
                if pd.notna(v):
                    pending_target = float(v)

        eq = (
        pd.DataFrame(self.pf.equity_curve)
          .set_index("timestamp")["equity"]
          .rename("equity")
        )
        return eq
    # ---- execution ------------------------------------------------

    def _rebalance_at(self, target_w: float, price: float, ts) -> None:
        sym = self.symbol
        eq_now = self.pf.equity({sym: price})
        if eq_now <= 0:
            return

        current_pos = self.pf.positions.get(sym, 0.0)
        current_value = current_pos * price
        target_value = target_w * eq_now
        delta_value = target_value - current_value

        # No-trade band
        if abs(delta_value) < self.no_trade_band * eq_now:
            return

        # Directional slippage
        slip = price * self.slippage_bps / 10_000
        exec_price = price + slip if delta_value > 0 else price - slip
        if exec_price <= 0:
            return

        # Compute the quantity to trade.
        # Special case: when going flat, sell exactly the current position.
        # Otherwise the slippage-adjusted price overshoots the target,
        # leaving a dust residual that never closes and confuses the
        # round-trip trade extractor.
        if target_w == 0.0 and abs(current_pos) > 0:
            qty = -current_pos
        else:
            qty = delta_value / exec_price

        notional = abs(qty) * exec_price
        commission = notional * self.commission_bps / 10_000

        self.pf.cash -= qty * exec_price + commission
        self.pf.positions[sym] = current_pos + qty

        # Snap floating-point dust to zero
        if abs(self.pf.positions[sym]) < 1e-9:
            self.pf.positions[sym] = 0.0

        self.pf.fills.append({
            "timestamp": ts,
            "side": "BUY" if qty > 0 else "SELL",
            "qty": qty,
            "price": exec_price,
            "commission": commission,
            "target_weight": target_w,
        })