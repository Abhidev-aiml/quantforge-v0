"""25 — Bollinger + RSI Double Strategy (ChartArt v1.1)

Long entry:
    RSI(rsi_length) crosses above rsi_oversold (default 50)
    AND close crosses above lower Bollinger Band (bb_length, bb_mult)

Short entry:
    RSI(rsi_length) crosses below rsi_overbought (default 50)
    AND close crosses below upper Bollinger Band (bb_length, bb_mult)

Position is held until the opposite entry condition occurs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _rsi(close: pd.Series, length: int) -> pd.Series:
    """Wilder's RSI (matches Pine Script's rsi())."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.where(avg_loss != 0.0, 100.0)
    return rsi


def _crossover(a: pd.Series, b: pd.Series | float) -> pd.Series:
    """True when a crosses above b."""
    if isinstance(b, (int, float)):
        b = pd.Series(b, index=a.index)
    return (a > b) & (a.shift(1) <= b.shift(1))


def _crossunder(a: pd.Series, b: pd.Series | float) -> pd.Series:
    """True when a crosses below b."""
    if isinstance(b, (int, float)):
        b = pd.Series(b, index=a.index)
    return (a < b) & (a.shift(1) >= b.shift(1))


def generate_signals(df: pd.DataFrame, params: dict | None = None) -> pd.Series:
    """Generate Bollinger + RSI position signals.

    Returns
    -------
    pd.Series
        Position series: +1 long, -1 short, 0 flat.
    """
    params = params or {}
    rsi_length = int(params.get("rsi_length", 6))
    rsi_oversold = float(params.get("rsi_oversold", 50.0))
    rsi_overbought = float(params.get("rsi_overbought", 50.0))
    bb_length = int(params.get("bb_length", 200))
    bb_mult = float(params.get("bb_mult", 2.0))

    close = df["close"]

    # RSI
    rsi = _rsi(close, rsi_length)

    # Bollinger Bands
    basis = close.rolling(bb_length, min_periods=bb_length).mean()
    # Pine Script's stdev() is population standard deviation (ddof=0)
    dev = bb_mult * close.rolling(bb_length, min_periods=bb_length).std(ddof=0)
    upper = basis + dev
    lower = basis - dev

    # Entry conditions
    long_entry = _crossover(rsi, rsi_oversold) & _crossover(close, lower)
    short_entry = _crossunder(rsi, rsi_overbought) & _crossunder(close, upper)

    # Build position: hold until opposite signal
    position = pd.Series(0.0, index=df.index)
    position[long_entry] = 1.0
    position[short_entry] = -1.0
    position = position.replace(0.0, np.nan).ffill().fillna(0.0)

    return position