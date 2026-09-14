"""
ReportEngine — loads run artifacts into a typed object.

One loader, used by every tier (executive, research, cross-asset).
Handles missing files gracefully.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ---- artifact bundle -------------------------------------------------

@dataclass
class RunArtifacts:
    run_id: str
    run_dir: Path
    manifest: dict[str, Any]
    equity: pd.Series
    trades: pd.DataFrame | None
    fills: pd.DataFrame | None
    metrics: dict[str, Any]
    monte_carlo: dict[str, Any] | None = None
    walk_forward: dict[str, Any] | None = None
    walk_forward_windows: pd.DataFrame | None = None
    whites_rc: dict[str, Any] | None = None
    benchmark: pd.Series | None = None
    price_data: pd.DataFrame | None = None

    # ---- derived ----------------------------------------------------

    @property
    def returns(self) -> pd.Series:
        return self.equity.pct_change().dropna()

    @property
    def benchmark_returns(self) -> pd.Series | None:
        if self.benchmark is None:
            return None
        return self.benchmark.pct_change().dropna()

    @property
    def drawdown(self) -> pd.Series:
        return self.equity / self.equity.cummax() - 1.0


# ---- loader ----------------------------------------------------------

class ReportEngine:
    """Load a canonical run directory into RunArtifacts."""

    def __init__(self, run_dir: str | Path, load_benchmark: bool = True):
        self.run_dir = Path(run_dir)
        if not self.run_dir.exists():
            raise FileNotFoundError(f"run dir not found: {self.run_dir}")
        self.load_benchmark = load_benchmark

    def load(self) -> RunArtifacts:
        manifest = self._load_json("manifest.json")
        equity = self._load_equity("equity.csv")

        # metrics.json is preferred, but we can compute on the fly from
        # the equity curve if the run didn't save it.
        metrics_path = self._path("metrics.json")
        if metrics_path.exists():
            metrics = self._load_json("metrics.json")
        else:
            from analytics.metrics import compute_metrics
            ppy = self._infer_ppy(equity.index)
            metrics = compute_metrics(equity, periods_per_year=ppy)

        trades = self._maybe_load_csv("trades.csv")
        fills = self._maybe_load_csv("fills.csv")

        mc = self._maybe_json("monte_carlo.json")
        wf = self._maybe_json("walk_forward_aggregate.json")
        wf_windows = self._maybe_load_csv("walk_forward_windows.csv")
        rc = self._maybe_json("whites_rc.json")

        # Benchmark: prefer saved benchmark.csv; fall back to reconstructing
        # from the underlying asset in the manifest config.
        benchmark = self._maybe_load_equity_file("benchmark.csv")
        price_data = None
        if benchmark is None and self.load_benchmark:
            try:
                price_data, benchmark = self._build_buy_and_hold_benchmark(
                    manifest, equity
                )
            except Exception:
                price_data, benchmark = None, None

        return RunArtifacts(
            run_id=manifest.get("run_id", self.run_dir.name),
            run_dir=self.run_dir,
            manifest=manifest,
            equity=equity,
            trades=trades,
            fills=fills,
            metrics=metrics,
            monte_carlo=mc,
            walk_forward=wf,
            walk_forward_windows=wf_windows,
            whites_rc=rc,
            benchmark=benchmark,
            price_data=price_data,
        )

    # ---- loading helpers --------------------------------------------

    def _path(self, name: str) -> Path:
        return self.run_dir / name

    def _load_json(self, name: str) -> dict:
        path = self._path(name)
        if not path.exists():
            raise FileNotFoundError(f"missing required artifact: {path}")
        return json.loads(path.read_text())

    def _maybe_json(self, name: str) -> dict | None:
        path = self._path(name)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return None

    def _maybe_load_csv(self, name: str) -> pd.DataFrame | None:
        path = self._path(name)
        if not path.exists():
            return None
        try:
            return pd.read_csv(path)
        except Exception:
            return None

    def _load_equity(self, name: str) -> pd.Series:
        path = self._path(name)
        if not path.exists():
            raise FileNotFoundError(f"missing required artifact: {path}")
        df = pd.read_csv(path)
        # detect timestamp column
        for col in ("timestamp", "date", "index"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
                df = df.set_index(col)
                break
        else:
            df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0])
            df = df.set_index(df.columns[0])
        # first numeric column is equity
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            raise ValueError(f"no numeric column in {path}")
        return df[numeric_cols[0]].astype(float).sort_index()

    # ---- benchmark construction -------------------------------------

    @staticmethod
    def _build_buy_and_hold_benchmark(
        manifest: dict, equity: pd.Series
    ) -> tuple[pd.DataFrame | None, pd.Series | None]:
        """Return (price_df, benchmark_equity).

        Benchmark = passive long the underlying asset, scaled to the
        same starting capital as the strategy equity.
        """
        cfg = manifest.get("config", {})
        data_cfg = cfg.get("data", {})
        path = data_cfg.get("path")
        if not path:
            return None, None
        path = Path(path)
        if not path.exists():
            return None, None

        df = pd.read_csv(path)
        for col in ("date", "datetime", "timestamp"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
                df = df.set_index(col)
                break
        df = df.sort_index()
        df = df.reindex(equity.index).ffill()
        if "close" not in df.columns:
            return None, None

        start_capital = float(equity.iloc[0])
        bench = start_capital * (df["close"] / df["close"].iloc[0])
        return df, bench

    def _maybe_load_equity_file(self, name: str) -> pd.Series | None:
        """Load a standalone equity curve CSV (timestamp, equity), if present."""
        path = self._path(name)
        if not path.exists():
            return None
        try:
            return self._load_equity(name)
        except Exception:
            return None

    @staticmethod
    def _infer_ppy(index) -> float:
        if not isinstance(index, pd.DatetimeIndex) or len(index) < 3:
            return 252.0
        days = (index[-1] - index[0]).days
        if days <= 0:
            return 252.0
        return float(len(index) / (days / 365.25))