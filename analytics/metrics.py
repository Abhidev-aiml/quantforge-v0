from __future__ import annotations

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def compute_metrics(
    equity: pd.Series,
    rf_annual: float = 0.0,
    periods_per_year: float | None = TRADING_DAYS,
    trades: pd.DataFrame | None = None,
    elapsed_years: float | None = None,
) -> dict:
    """Return a dict of every quant metric on the equity curve.

    `periods_per_year` must match the observation frequency of the
    equity curve. `elapsed_years` can be supplied when the equity
    index has real timestamps; this makes CAGR independent of a
    simplistic bar-count assumption. If not supplied and the index
    is a DatetimeIndex, elapsed years are auto-detected.
    """
    equity = equity.dropna().astype(float)

    if len(equity) < 2:
        raise ValueError("Need at least 2 equity observations")

    # Defensive: allow callers to pass None, auto-infer from index
    if periods_per_year is None:
        if isinstance(equity.index, pd.DatetimeIndex) and len(equity) > 1:
            span_days = (equity.index[-1] - equity.index[0]).days
            if span_days > 0:
                periods_per_year = float(len(equity) / (span_days / 365.25))
            else:
                periods_per_year = float(TRADING_DAYS)
        else:
            periods_per_year = float(TRADING_DAYS)

    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be > 0")

    # Auto-detect elapsed years from datetime index if not provided
    if elapsed_years is None and isinstance(equity.index, pd.DatetimeIndex) and len(equity) > 1:
        elapsed_years = (equity.index[-1] - equity.index[0]).days / 365.25

    returns = equity.pct_change().dropna()

    m: dict = {}

    m.update(
        _return_metrics(
            equity,
            returns,
            periods_per_year,
            elapsed_years,
        )
    )

    m.update(
        _risk_metrics(
            returns,
            periods_per_year,
        )
    )

    m.update(
        _risk_adjusted_metrics(
            equity,
            returns,
            rf_annual,
            periods_per_year,
            elapsed_years,
        )
    )

    m.update(_tail_metrics(returns))
    m.update(_drawdown_metrics(equity))

    if trades is not None and len(trades) > 0:
        m.update(_trade_metrics(trades))

    return m


# ---- return metrics --------------------------------------------------


def _return_metrics(
    equity,
    returns,
    ppy,
    elapsed_years=None,
):
    total = equity.iloc[-1] / equity.iloc[0] - 1.0

    # Prefer actual timestamp span when available. This avoids treating,
    # for example, 70,000 hourly bars as 70,000 / 252 "years".
    if elapsed_years is not None and elapsed_years > 0:
        years = float(elapsed_years)
    else:
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
    elapsed_years=None,
):
    # Convert the annual risk-free rate to the return observation
    # period using the timeframe-specific annualization factor.
    rf_period = (1.0 + rf_annual) ** (1.0 / ppy) - 1.0

    excess = returns - rf_period

    ann_excess = excess.mean() * ppy

    ann_vol = returns.std(ddof=1) * np.sqrt(ppy)

    sharpe = (
        ann_excess / ann_vol
        if ann_vol > 0
        else np.nan
    )

    downside = returns[returns < rf_period]

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

    # Use actual elapsed timestamp years for CAGR when available.
    if elapsed_years is not None and elapsed_years > 0:
        years = float(elapsed_years)
    else:
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

    # Also report elapsed drawdown duration when the equity index
    # contains datetimes.
    max_duration_days = np.nan

    if isinstance(equity.index, pd.DatetimeIndex):
        max_duration = pd.Timedelta(0)
        peak_ts = equity.index[0]

        running_peak = equity.iloc[0]

        for ts, value in equity.items():
            if value >= running_peak:
                running_peak = value
                peak_ts = ts
            elif value < running_peak:
                duration = ts - peak_ts
                if duration > max_duration:
                    max_duration = duration

        max_duration_days = (
            max_duration.total_seconds() / 86400.0
        )

    return {
        "max_drawdown": max_dd,
        "max_drawdown_duration_bars": int(longest),
        "max_drawdown_duration_days": float(max_duration_days),
        "avg_drawdown": avg_dd,
    }


# ---- trade-level -----------------------------------------------------


def _trade_metrics(trades: pd.DataFrame) -> dict:
    pnl = trades["pnl"]

    notional = trades["qty"] * trades["entry_price"]
    pnl_pct = pnl / notional.replace(0, np.nan)

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
        "expectancy_pct": float(pnl_pct.mean()),
        "avg_win_pct": (
            float(pnl_pct[pnl > 0].mean())
            if len(wins)
            else 0.0
        ),
        "avg_loss_pct": (
            float(pnl_pct[pnl <= 0].mean())
            if len(losses)
            else 0.0
        ),
    }


# ---- fills → round-trip trades --------------------------------------


def extract_trades(fills: list[dict]) -> pd.DataFrame:
    """Convert engine fills into round-trip trades.

    Handles three transition types:

      1. flat → position  : open new trade
      2. position → flat  : close trade
      3. long ↔ short     : close old, open new (sign flip)

    Same-direction scaling (adding to a position) is rolled into the
    parent trade. The number of scale-ins per trade is recorded in the
    `scale_ins` column so callers can see when this simplification
    applies.
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
    scale_ins = 0

    def record_trade(
        exit_price,
        exit_ts,
        exit_commission,
    ):
        gross = (exit_price - entry_price) * entry_qty
        total_comm = entry_commission + exit_commission

        trades.append({
            "entry_ts": entry_ts,
            "exit_ts": exit_ts,
            "direction": (
                "LONG"
                if entry_qty > 0
                else "SHORT"
            ),
            "entry_price": entry_price,
            "exit_price": exit_price,
            "qty": abs(entry_qty),
            "gross_pnl": gross,
            "commission": total_comm,
            "pnl": gross - total_comm,
            "scale_ins": scale_ins,
        })

    for f in fills:

        prev = position
        position += f["qty"]

        flat_before = abs(prev) < TOL
        flat_after = abs(position) < TOL

        flipped = (
            (prev > TOL and position < -TOL)
            or
            (prev < -TOL and position > TOL)
        )

        if flat_before and not flat_after:
            # --- OPEN ---
            entry_ts = f["timestamp"]
            entry_price = f["price"]
            entry_qty = f["qty"]
            entry_commission = f["commission"]
            scale_ins = 0

        elif not flat_before and flat_after:
            # --- CLOSE ---
            record_trade(
                f["price"],
                f["timestamp"],
                f["commission"],
            )

            entry_ts = None
            entry_qty = 0.0
            entry_price = 0.0
            entry_commission = 0.0
            scale_ins = 0

        elif flipped:
            # --- SIGN FLIP ---
            record_trade(
                f["price"],
                f["timestamp"],
                f["commission"] * 0.5,
            )

            entry_ts = f["timestamp"]
            entry_price = f["price"]
            entry_qty = position
            entry_commission = f["commission"] * 0.5
            scale_ins = 0

        else:
            # --- SAME-DIRECTION SCALE-IN ---
            # Folded into the parent trade; just count it.
            scale_ins += 1

    return pd.DataFrame(trades)
def extract_trades_multi(fills: list[dict]) -> pd.DataFrame:
    """Group fills by symbol and extract round-trip trades per symbol.

    Requires each fill dict to have a 'symbol' field. Fills without
    a symbol are treated as belonging to 'ASSET' (single-asset
    compatibility).
    """
    if not fills:
        return pd.DataFrame()

    by_symbol: dict[str, list[dict]] = {}
    for f in fills:
        sym = f.get("symbol", "ASSET")
        by_symbol.setdefault(sym, []).append(f)

    all_trades = []
    for sym, sym_fills in by_symbol.items():
        trades = extract_trades(sym_fills)
        if len(trades):
            trades = trades.copy()
            trades["symbol"] = sym
            all_trades.append(trades)

    if not all_trades:
        return pd.DataFrame()
    return pd.concat(all_trades, ignore_index=True)


def portfolio_turnover(signals: pd.DataFrame) -> float:
    """Average per-bar turnover: sum over symbols of |Δweight|."""
    if signals.empty:
        return 0.0
    return float(signals.diff().abs().sum(axis=1).mean())


def avg_gross_exposure(signals: pd.DataFrame) -> float:
    """Average per-bar gross exposure (sum of |weights|)."""
    if signals.empty:
        return 0.0
    return float(signals.abs().sum(axis=1).mean())


def avg_net_exposure(signals: pd.DataFrame) -> float:
    """Average per-bar net exposure (signed sum of weights)."""
    if signals.empty:
        return 0.0
    return float(signals.sum(axis=1).mean())