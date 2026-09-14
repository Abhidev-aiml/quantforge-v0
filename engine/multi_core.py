"""
Multi-asset backtest engine.

Semantics identical to single-asset BacktestEngine:
  - Signal on bar t's close executes at bar t+1's open
  - Directional slippage
  - Commission on notional
  - Flat target → exact zero position (no dust)
  - Warmup bars are treated as flat

The portfolio tracks positions per symbol and shared cash.
Signals is a DataFrame: index=dates, columns=symbols, values=weights.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class MultiAssetPortfolio:
    cash: float
    positions: dict[str, float] = field(default_factory=dict)
    equity_curve: list[dict] = field(default_factory=list)
    fills: list[dict] = field(default_factory=list)

    def equity(self, prices: dict[str, float]) -> float:
        pos_value = 0.0
        for sym, qty in self.positions.items():
            px = prices.get(sym)
            if px is not None and not np.isnan(px):
                pos_value += qty * px
        return self.cash + pos_value

    def snapshot(self, ts, prices: dict[str, float]) -> None:
        self.equity_curve.append({
            "timestamp": ts,
            "equity": self.equity(prices),
        })


class MultiAssetBacktestEngine:
    """Event-driven, multi-symbol backtester."""

    def __init__(
        self,
        symbols: list[str],
        initial_cash: float = 100_000.0,
        commission_bps: float = 1.0,
        slippage_bps: float = 5.0,
        no_trade_band: float = 0.01,
        warmup_bars: int = 0,
        allow_short: bool = True,
    ):
        self.symbols = list(symbols)
        self.pf = MultiAssetPortfolio(cash=initial_cash)
        self.commission_bps = commission_bps
        self.slippage_bps = slippage_bps
        self.no_trade_band = no_trade_band
        self.warmup_bars = warmup_bars
        self.allow_short = allow_short

    # ---------------------------------------------------------------- run

    def run(
        self,
        data: dict[str, pd.DataFrame],
        signals: pd.DataFrame,
    ) -> pd.Series:
        """Execute the backtest.

        Args:
            data:    {symbol: OHLCV DataFrame}, all on the same index
            signals: DataFrame index=dates, columns=symbols, values=weights

        Returns:
            equity Series indexed by date
        """
        index = self._resolve_index(data)

        opens  = {sym: df["open"].to_dict()  for sym, df in data.items()}
        closes = {sym: df["close"].to_dict() for sym, df in data.items()}

        pending: dict[str, Optional[float]] = {sym: None for sym in self.symbols}
        last_close: dict[str, float] = {}

        for i, ts in enumerate(index):
            # ------------------ warmup -----------------
            if i < self.warmup_bars:
                self._update_last_close(last_close, closes, ts)
                self.pf.snapshot(ts, last_close)
                continue

            # ------------------ execute pending at this bar's open
            for sym in self.symbols:
                target = pending[sym]
                if target is None:
                    continue
                exec_price = opens[sym].get(ts)
                if exec_price is None or np.isnan(exec_price) or exec_price <= 0:
                    continue
                self._rebalance_symbol(sym, target, exec_price, ts, last_close)

            # ------------------ mark to market at close
            self._update_last_close(last_close, closes, ts)
            self.pf.snapshot(ts, last_close)

            # ------------------ read new signals, queue for next bar
            if ts in signals.index:
                row = signals.loc[ts]
                for sym in self.symbols:
                    if sym not in row.index:
                        continue
                    v = row[sym]
                    if pd.notna(v):
                        pending[sym] = float(v)

        eq = (
            pd.DataFrame(self.pf.equity_curve)
              .set_index("timestamp")["equity"]
              .rename("equity")
        )
        return eq

    # ---------------------------------------------------------------- helpers

    def _resolve_index(self, data: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
        if not data:
            raise ValueError("empty data")
        idx = None
        for df in data.values():
            idx = df.index if idx is None else idx.union(df.index)
        return idx.sort_values()

    def _update_last_close(self, last_close, closes, ts):
        for sym in self.symbols:
            px = closes[sym].get(ts)
            if px is not None and not np.isnan(px):
                last_close[sym] = float(px)

    def _rebalance_symbol(
        self,
        sym: str,
        target_w: float,
        price: float,
        ts,
        last_close: dict[str, float],
    ) -> None:
        # Portfolio valuation: exec price for this symbol, last close for others
        prices_now = dict(last_close)
        prices_now[sym] = price
        eq_now = self.pf.equity(prices_now)
        if eq_now <= 0:
            return

        current_pos = self.pf.positions.get(sym, 0.0)
        current_value = current_pos * price
        target_value = target_w * eq_now
        delta_value = target_value - current_value

        if abs(delta_value) < self.no_trade_band * eq_now:
            return

        # Directional slippage
        slip = price * self.slippage_bps / 10_000
        exec_price = price + slip if delta_value > 0 else price - slip
        if exec_price <= 0:
            return

        # Qty: exact-current-pos when flat, value/price otherwise
        if target_w == 0.0 and abs(current_pos) > 0:
            qty = -current_pos
        else:
            qty = delta_value / exec_price

        if not self.allow_short and (current_pos + qty) < 0:
            # Clamp to flat; prevents accidental shorts
            qty = -current_pos

        notional = abs(qty) * exec_price
        commission = notional * self.commission_bps / 10_000

        self.pf.cash -= qty * exec_price + commission
        self.pf.positions[sym] = current_pos + qty

        if abs(self.pf.positions[sym]) < 1e-9:
            self.pf.positions[sym] = 0.0

        self.pf.fills.append({
            "timestamp": ts,
            "symbol": sym,
            "side": "BUY" if qty > 0 else "SELL",
            "qty": qty,
            "price": exec_price,
            "commission": commission,
            "target_weight": target_w,
        })