# 16_trend_pullback_1h.py
#
# Two-sided Trend Pullback strategy for QuantForge
# Timeframe: 1H
#
# Research hypothesis:
#   Established trends provide directional edge.
#   Rather than entering after an extended move, wait for a
#   controlled pullback and momentum recovery.
#
# Long:
#   EMA 50 > EMA 200
#   ADX > 25.0
#   +DI > -DI
#   price pulls close to EMA 20
#   RSI recovers above 50
#
# Short:
#   EMA 50 < EMA 200
#   ADX > 25.0
#   -DI > +DI
#   price pulls close to EMA 20
#   RSI falls below 50
#
# Risk:
#   Initial stop = 1.5 ATR
#   Trailing stop = 2.0 ATR
#
# Execution:
#   This strategy only produces target weights:
#       +1 = long
#        0 = flat
#       -1 = short
#
#   QuantForge's BacktestEngine handles execution on the next bar.
#

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    """Exponential moving average."""
    return s.ewm(
        span=n,
        adjust=False,
        min_periods=n,
    ).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder-style RSI."""
    delta = close.diff()

    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(
        alpha=1 / n,
        adjust=False,
        min_periods=n,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / n,
        adjust=False,
        min_periods=n,
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    return (
        100.0 - 100.0 / (1.0 + rs)
    ).fillna(50.0)


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    n: int = 14,
) -> pd.Series:
    """Wilder-style Average True Range."""
    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.ewm(
        alpha=1 / n,
        adjust=False,
        min_periods=n,
    ).mean()


def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    n: int = 14,
):
    """
    Return ADX, +DI and -DI using Wilder-style smoothing.
    """

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where(
            (up_move > down_move) & (up_move > 0),
            up_move,
            0.0,
        ),
        index=high.index,
    )

    minus_dm = pd.Series(
        np.where(
            (down_move > up_move) & (down_move > 0),
            down_move,
            0.0,
        ),
        index=high.index,
    )

    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr_w = tr.ewm(
        alpha=1 / n,
        adjust=False,
        min_periods=n,
    ).mean()

    plus_w = plus_dm.ewm(
        alpha=1 / n,
        adjust=False,
        min_periods=n,
    ).mean()

    minus_w = minus_dm.ewm(
        alpha=1 / n,
        adjust=False,
        min_periods=n,
    ).mean()

    plus_di = (
        100.0
        * plus_w
        / atr_w.replace(0, np.nan)
    )

    minus_di = (
        100.0
        * minus_w
        / atr_w.replace(0, np.nan)
    )

    di_sum = (
        plus_di + minus_di
    ).replace(0, np.nan)

    dx = (
        100.0
        * (plus_di - minus_di).abs()
        / di_sum
    )

    adx_value = dx.ewm(
        alpha=1 / n,
        adjust=False,
        min_periods=n,
    ).mean()

    return adx_value, plus_di, minus_di



def generate_signals(df: pd.DataFrame) -> pd.Series:
    """
    Generate +1 / 0 / -1 target weights.

    This is a fixed baseline for research. Parameters should NOT
    be optimized until out-of-sample / walk-forward testing exists.
    """

    EMA_FAST = 50
    EMA_SLOW = 200
    EMA_PULLBACK = 20

    RSI_N = 14
    ADX_N = 14
    ADX_THRESHOLD = 25.0
    ATR_N = 14

    PULLBACK_PCT = 0.003
    STOP_ATR = 1.5
    TRAIL_ATR = 2.0

    close = df["close"]
    high = df["high"]
    low = df["low"]

    ema_fast = ema(close, EMA_FAST)
    ema_slow = ema(close, EMA_SLOW)
    ema_pullback = ema(close, EMA_PULLBACK)

    rsi_value = rsi(
        close,
        RSI_N,
    )

    atr_value = atr(
        high,
        low,
        close,
        ATR_N,
    )

    adx_value, plus_di, minus_di = adx(
        high,
        low,
        close,
        ADX_N,
    )

    # --------------------------------------------------------
    # Trend regime
    # --------------------------------------------------------

    bullish_trend = (
        (ema_fast > ema_slow)
        & (close > ema_slow)
        & (plus_di > minus_di)
        & (adx_value > ADX_THRESHOLD)
    )

    bearish_trend = (
        (ema_fast < ema_slow)
        & (close < ema_slow)
        & (minus_di > plus_di)
        & (adx_value > ADX_THRESHOLD)
    )

    # --------------------------------------------------------
    # Pullback:
    #
    # Allow price to come within PULLBACK_PCT of EMA 20.
    #
    # Example:
    #   PULLBACK_PCT = 0.005
    #   means within 0.5% of EMA 20.
    # --------------------------------------------------------

    distance_from_ema = (
        (close - ema_pullback).abs()
        / ema_pullback.replace(0, np.nan)
    )

    near_pullback_ema = (
        distance_from_ema <= PULLBACK_PCT
    )

    # Require price to be on the correct side of EMA20 when
    # momentum confirms the pullback has recovered.
    long_recovery = (
        (close > ema_pullback)
        & (rsi_value > 50.0)
        & (rsi_value.shift(1) <= 50.0)
    )

    short_recovery = (
        (close < ema_pullback)
        & (rsi_value < 50.0)
        & (rsi_value.shift(1) >= 50.0)
    )

    long_entry = (
        bullish_trend
        & near_pullback_ema
        & long_recovery
    )

    short_entry = (
        bearish_trend
        & near_pullback_ema
        & short_recovery
    )

    # --------------------------------------------------------
    # Stateful position handling.
    #
    # The strategy maintains a single position:
    #   +1 long
    #    0 flat
    #   -1 short
    #
    # Stops are evaluated using the current bar's OHLC data.
    # The actual fill still occurs through QuantForge's normal
    # next-bar execution model because the signal itself only
    # changes after the bar has completed.
    # --------------------------------------------------------

    sig = pd.Series(
        0.0,
        index=df.index,
        dtype=float,
    )

    position = 0.0
    entry_price = np.nan
    highest_since_entry = np.nan
    lowest_since_entry = np.nan

    for i in range(len(df)):

        c = close.iloc[i]
        h = high.iloc[i]
        l = low.iloc[i]
        a = atr_value.iloc[i]

        # ----------------------------------------------------
        # No valid ATR => still in indicator warm-up.
        # ----------------------------------------------------

        if pd.isna(a):
            sig.iloc[i] = position
            continue

        # ----------------------------------------------------
        # Update trailing reference.
        # ----------------------------------------------------

        if position == 1.0:

            highest_since_entry = max(
                highest_since_entry,
                h,
            )

            hard_stop = (
                entry_price
                - STOP_ATR * a
            )

            trailing_stop = (
                highest_since_entry
                - TRAIL_ATR * a
            )

            # Trend invalidation.
            trend_invalidated = (
                close.iloc[i] < ema_slow.iloc[i]
            )

            if (
                c <= hard_stop
                or c <= trailing_stop
                or trend_invalidated
            ):
                position = 0.0
                entry_price = np.nan
                highest_since_entry = np.nan

        elif position == -1.0:

            lowest_since_entry = min(
                lowest_since_entry,
                l,
            )

            hard_stop = (
                entry_price
                + STOP_ATR * a
            )

            trailing_stop = (
                lowest_since_entry
                + TRAIL_ATR * a
            )

            trend_invalidated = (
                close.iloc[i] > ema_slow.iloc[i]
            )

            if (
                c >= hard_stop
                or c >= trailing_stop
                or trend_invalidated
            ):
                position = 0.0
                entry_price = np.nan
                lowest_since_entry = np.nan

        # ----------------------------------------------------
        # Enter / reverse.
        # ----------------------------------------------------

        if position == 0.0:

            if long_entry.iloc[i]:

                position = 1.0
                entry_price = c
                highest_since_entry = h
                lowest_since_entry = np.nan

            elif short_entry.iloc[i]:

                position = -1.0
                entry_price = c
                lowest_since_entry = l
                highest_since_entry = np.nan

        sig.iloc[i] = position

    return sig
