from __future__ import annotations
import importlib.util
from pathlib import Path
from typing import Callable
import pandas as pd
import inspect


class StrategyError(Exception):
    """Raised when a strategy file violates the contract."""
    pass


def load_strategy(path: str | Path) -> Callable[[pd.DataFrame], pd.Series]:
    """Import a .py file and return its generate_signals function."""
    path = Path(path)

    if not path.exists():
        raise StrategyError(f"Strategy file not found: {path}")
    if path.suffix != ".py":
        raise StrategyError(f"Strategy must be a .py file, got: {path.suffix}")

    spec = importlib.util.spec_from_file_location("user_strategy", path)
    if spec is None or spec.loader is None:
        raise StrategyError(f"Could not build import spec for {path}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise StrategyError(f"Error importing {path.name}: {e}") from e

    if not hasattr(module, "generate_signals"):
        found = [n for n in dir(module) if not n.startswith("_")]
        raise StrategyError(
            f"{path.name} must define a function 'generate_signals(df)'. "
            f"Found top-level names: {found}"
        )

    fn = module.generate_signals
    if not callable(fn):
        raise StrategyError(
            f"generate_signals must be a function, got {type(fn).__name__}"
        )
    return fn


def validate_signals(
    signals, df: pd.DataFrame, name: str = "signals"
) -> pd.Series:
    """Return a clean, aligned, NaN-free Series or raise StrategyError."""
    if not isinstance(signals, pd.Series):
        raise StrategyError(
            f"{name}: expected pandas Series, got {type(signals).__name__}. "
            f"Hint: return a Series, not a list/array/DataFrame."
        )

    if len(signals) != len(df):
        raise StrategyError(
            f"{name}: length {len(signals)} does not match data length {len(df)}"
        )

    if not signals.index.equals(df.index):
        raise StrategyError(
            f"{name}: index does not match data index. "
            f"Don't reset_index() or shift the index."
        )

    s = signals.dropna()
    if len(s) == 0:
        raise StrategyError(f"{name}: all values are NaN")

    if not pd.api.types.is_numeric_dtype(s):
        raise StrategyError(
            f"{name}: must be numeric, got dtype {s.dtype}"
        )

    out_of_range = s[(s < -1.0) | (s > 1.0)]
    if len(out_of_range):
        raise StrategyError(
            f"{name}: weights must be in [-1, 1]. "
            f"Found {len(out_of_range)} violations, e.g. "
            f"{out_of_range.head(3).round(3).to_dict()}"
        )

    return signals.astype(float).fillna(0.0)

def call_strategy(fn, df, params: dict | None = None) -> pd.Series:
    """Invoke a strategy function, passing params if the signature accepts it.

    Backward-compatible: strategies that only accept (df) still work.
    Strategies that accept (df, params) get the params dict.
    """
    sig = inspect.signature(fn)
    accepts_params = (
        "params" in sig.parameters
        or any(p.kind == inspect.Parameter.VAR_KEYWORD
               for p in sig.parameters.values())
    )
    if accepts_params:
        return fn(df, params=params or {})
    return fn(df)
