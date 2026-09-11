from __future__ import annotations

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def compute_metrics(
    equity: pd.Series,
    rf_annual: float = 0.0,
    periods_per_year: int = TRADING_DAYS,
    trades: pd.DataFrame | None = None,
) -> dict:
    """Return a dict of every quant metric on the equity curve."""
    equity = equity.dropna().astype(float)

    if len(equity) < 2:
        raise ValueError("Need at least 2 equity observations")

    returns = equity.pct_change().dropna()

    m: dict = {}

    m.update(_return_metrics(equity, returns, periods_per_year))
    m.update(_risk_metrics(returns, periods_per_year))
    m.update(
        _risk_adjusted_metrics(
            equity,
            returns,
            rf_annual,
            periods_per_year,
        )
    )
    m.update(_tail_metrics(returns))
    m.update(_drawdown_metrics(equity))

    if trades is not None and len(trades) > 0:
        m.update(_trade_metrics(trades))

    return m


# ---- return metrics --------------------------------------------------


def _return_metrics(equity, returns, ppy):
    total = equity.iloc[-1] / equity.iloc[0] - 1.0

    years = len(returns) / ppy

    cagr = np.nan

    if years > 0 and equity.iloc[-1] > 0:
        cagr = (
            equity.iloc[-1] / equity.iloc[0]
        ) ** (1.0 / years) - 1.0

    return {
        "total_return": float(total),
        "CAGR": float(cagr),
        "n_periods": int(len(returns)),
        "years": float(years),
    }


# ---- risk metrics ----------------------------------------------------


def _risk_metrics(returns, ppy):
    vol = returns.std(ddof=1) * np.sqrt(ppy)

    downside = returns[returns < 0]

    dd = (
        downside.std(ddof=1) * np.sqrt(ppy)
        if len(downside) > 1
        else np.nan
    )

    return {
        "volatility": float(vol),
        "downside_deviation": float(dd),
    }


# ---- risk-adjusted ---------------------------------------------------


def _risk_adjusted_metrics(
    equity,
    returns,
    rf_annual,
    ppy,
):
    rf_daily = (1.0 + rf_annual) ** (1.0 / ppy) - 1.0

    excess = returns - rf_daily

    ann_excess = excess.mean() * ppy

    ann_vol = returns.std(ddof=1) * np.sqrt(ppy)

    sharpe = (
        ann_excess / ann_vol
        if ann_vol > 0
        else np.nan
    )

    downside = returns[returns < rf_daily]

    dd_vol = (
        downside.std(ddof=1) * np.sqrt(ppy)
        if len(downside) > 1
        else np.nan
    )

    sortino = (
        ann_excess / dd_vol
        if dd_vol and dd_vol > 0
        else np.nan
    )

    dd_series = equity / equity.cummax() - 1.0

    max_dd = dd_series.min()

    years = len(returns) / ppy

    cagr = np.nan

    if years > 0 and equity.iloc[-1] > 0:
        cagr = (
            equity.iloc[-1] / equity.iloc[0]
        ) ** (1.0 / years) - 1.0

    calmar = (
        cagr / abs(max_dd)
        if max_dd < 0
        else np.nan
    )

    return {
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "calmar": float(calmar),
    }


# ---- tail / distribution --------------------------------------------


def _tail_metrics(returns):
    var_95 = float(np.percentile(returns, 5))
    var_99 = float(np.percentile(returns, 1))

    tail_95 = returns[returns <= var_95]
    tail_99 = returns[returns <= var_99]

    return {
        "VaR_95": var_95,
        "CVaR_95": (
            float(tail_95.mean())
            if len(tail_95)
            else np.nan
        ),
        "VaR_99": var_99,
        "CVaR_99": (
            float(tail_99.mean())
            if len(tail_99)
            else np.nan
        ),
        "skew": float(returns.skew()),
        "kurtosis": float(returns.kurtosis()),
    }


# ---- drawdown --------------------------------------------------------


def _drawdown_metrics(equity):
    dd = equity / equity.cummax() - 1.0

    max_dd = float(dd.min())

    underwater = dd < 0

    longest = 0
    current = 0

    for flag in underwater:
        if flag:
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    avg_dd = (
        float(dd[dd < 0].mean())
        if (dd < 0).any()
        else 0.0
    )

    return {
        "max_drawdown": max_dd,
        "max_drawdown_duration_bars": int(longest),
        "avg_drawdown": avg_dd,
    }


# ---- trade-level -----------------------------------------------------


def _trade_metrics(trades: pd.DataFrame) -> dict:
    pnl = trades["pnl"]
    notional = trades["qty"] * trades["entry_price"]
    pnl_pct = pnl / notional          # return on the position

    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    win_rate = (
        len(wins) / len(pnl)
        if len(pnl)
        else np.nan
    )

    if len(losses) and losses.sum() != 0:
        profit_factor = float(
            wins.sum() / abs(losses.sum())
        )
    else:
        profit_factor = (
            float("inf")
            if wins.sum() > 0
            else 0.0
        )

    avg_win = (
        float(wins.mean())
        if len(wins)
        else 0.0
    )

    avg_loss = (
        float(losses.mean())
        if len(losses)
        else 0.0
    )

    payoff = (
        abs(avg_win / avg_loss)
        if avg_loss != 0
        else float("inf")
    )

    return {
        "num_trades": int(len(trades)),
        "win_rate": float(win_rate),
        "profit_factor": profit_factor,
        "expectancy": float(pnl.mean()),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff_ratio": payoff,
        "expectancy_pct": float(pnl_pct.mean()),       # ← new
        "avg_win_pct":   float(pnl_pct[pnl > 0].mean()) if len(wins) else 0.0,
        "avg_loss_pct":  float(pnl_pct[pnl <= 0].mean()) if len(losses) else 0.0,
    }


# ---- fills → round-trip trades --------------------------------------


def extract_trades(fills: list[dict]) -> pd.DataFrame:
    """Convert engine fills into round-trip trades.

    Handles three transition types:
      1. flat → position  : open new trade
      2. position → flat  : close trade
      3. long ↔ short     : close old, open new (sign flip)

    Same-direction scaling (adding to a position) is ignored — it's
    rolled into the existing trade. This is a simplification appropriate
    for retail strategies that trade all-in / all-out.
    """
    if not fills:
        return pd.DataFrame()

    TOL = 1e-6
    trades: list[dict] = []

    position = 0.0
    entry_qty = 0.0
    entry_price = 0.0
    entry_ts = None
    entry_commission = 0.0

    def record_trade(exit_price, exit_ts, exit_commission):
        gross = (exit_price - entry_price) * entry_qty
        total_comm = entry_commission + exit_commission
        trades.append({
            "entry_ts":    entry_ts,
            "exit_ts":     exit_ts,
            "direction":   "LONG" if entry_qty > 0 else "SHORT",
            "entry_price": entry_price,
            "exit_price":  exit_price,
            "qty":         abs(entry_qty),
            "gross_pnl":   gross,
            "commission":  total_comm,
            "pnl":         gross - total_comm,
        })

    for f in fills:
        prev = position
        position += f["qty"]

        flat_before = abs(prev) < TOL
        flat_after  = abs(position) < TOL
        flipped     = (prev > TOL and position < -TOL) or \
                      (prev < -TOL and position > TOL)

        if flat_before and not flat_after:
            # --- OPEN ---
            entry_ts         = f["timestamp"]
            entry_price      = f["price"]
            entry_qty        = f["qty"]
            entry_commission = f["commission"]

        elif not flat_before and flat_after:
            # --- CLOSE ---
            record_trade(f["price"], f["timestamp"], f["commission"])
            entry_ts         = None
            entry_qty        = 0.0
            entry_price      = 0.0
            entry_commission = 0.0

        elif flipped:
            # --- SIGN FLIP ---
            record_trade(f["price"], f["timestamp"], f["commission"] * 0.5)
            entry_ts         = f["timestamp"]
            entry_price      = f["price"]
            entry_qty        = position
            entry_commission = f["commission"] * 0.5

        # else: same-direction scale. Fold into current trade (ignore).

    return pd.DataFrame(trades)