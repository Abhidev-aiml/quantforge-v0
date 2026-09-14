"""24 — VWAP Mean Reversion

Entry: price closes > 1.5% above VWAP → short
       price closes > 1.5% below VWAP → long
Exit: mean reversion back to VWAP
"""
import pandas as pd

def generate_signals(df, params=None):
    """Generate VWAP mean reversion signals."""
    params = params or {}
    threshold = params.get("threshold", 0.015)  # 1.5%

    # Calculate VWAP
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    vwap = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()

    # Calculate deviation from VWAP
    deviation = (df["close"] - vwap) / vwap

    # Generate signals
    signals = pd.Series(0.0, index=df.index)
    signals[deviation > threshold] = -1.0   # Short when above VWAP
    signals[deviation < -threshold] = 1.0   # Long when below VWAP

    return signals