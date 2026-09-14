"""26 — VWAP Mean Reversion (volatility-normalized)

Entry: price deviates from rolling VWAP by more than `z_threshold` standard
       "ATR units" -> fade the move (short if above, long if below)
Exit:  reversion back through VWAP, OR hard stop-loss (in ATR units),
       OR max holding period

Fixes vs. 25_vwap_refined.py:
  - Deviation threshold is no longer a flat 1.5% for every asset. Instead,
    deviation is expressed in units of rolling ATR, so a highly volatile
    asset (Silver, Brent) requires a proportionally larger move to trigger
    an entry, and a low-volatility asset (EURUSD, USDCHF) doesn't need an
    unrealistically large move either. This directly targets the failure
    mode where 25_vwap_refined over-traded Silver/Brent (1000-2200 trades)
    relative to FX pairs (~200-500 trades) on the same fixed threshold.
  - Stop-loss is also expressed in ATR units for the same reason -- a fixed
    5% stop is tiny relative to Silver's daily range and huge relative to
    USDCHF's.
"""
import numpy as np
import pandas as pd


def _atr(df, n):
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def generate_signals(df, params=None):
    """Generate volatility-normalized VWAP mean reversion signals."""
    params = params or {}
    z_threshold = params.get("z_threshold", 1.5)   # entry, in ATR units
    z_stop = params.get("z_stop", 3.0)              # stop-loss, in ATR units
    vwap_window = params.get("vwap_window", 20)     # rolling bars for VWAP
    atr_window = params.get("atr_window", 20)       # rolling bars for ATR
    max_hold = params.get("max_hold", 10)           # bars -> force exit

    # Rolling VWAP (bounded window)
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    pv = typical_price * df["volume"]
    vwap = (
        pv.rolling(vwap_window, min_periods=vwap_window).sum()
        / df["volume"].rolling(vwap_window, min_periods=vwap_window).sum()
    )

    # Deviation expressed in ATR units, not raw percent
    atr = _atr(df, atr_window)
    deviation_price = df["close"] - vwap
    deviation_atr = deviation_price / atr.replace(0, np.nan)

    close_vals = df["close"].to_numpy()
    dev_vals = deviation_atr.to_numpy()
    atr_vals = atr.to_numpy()

    out = [0.0] * len(df)

    position = 0.0
    entry_px = None
    entry_atr = None
    bars_in_trade = 0

    for i in range(len(df)):
        c = close_vals[i]
        dev = dev_vals[i]
        a = atr_vals[i]

        if position == 0.0:
            if not np.isnan(dev):
                if dev > z_threshold:
                    position, entry_px, entry_atr, bars_in_trade = -1.0, c, a, 0
                elif dev < -z_threshold:
                    position, entry_px, entry_atr, bars_in_trade = 1.0, c, a, 0
        else:
            bars_in_trade += 1
            # Adverse move measured in ATR units *at entry* (fixed risk unit
            # for the life of the trade, so volatility spikes mid-trade
            # don't silently loosen the stop)
            adverse_price = (c - entry_px) * (1 if position < 0 else -1)
            adverse_atr = adverse_price / entry_atr if entry_atr and entry_atr > 0 else 0.0
            reverted = (position > 0 and dev >= 0) or (position < 0 and dev <= 0)

            if adverse_atr >= z_stop or bars_in_trade >= max_hold or reverted:
                position, entry_px, entry_atr, bars_in_trade = 0.0, None, None, 0

        out[i] = position

    return pd.Series(out, index=df.index)