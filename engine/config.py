"""
Typed, validated configuration for QuantForge.

Loads a YAML config, merges with a base config, validates with Pydantic,
and exposes a stable hash for reproducibility.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


# ------------------------------------------------------------------ schema

class DataConfig(BaseModel):
    path: str
    symbol: str = "ASSET"
    start: str | None = None
    end: str | None = None

    @field_validator("path")
    @classmethod
    def path_exists(cls, v: str) -> str:
        p = Path(v)
        if not p.exists():
            raise ValueError(f"data path does not exist: {v}")
        return v


class EngineConfig(BaseModel):
    initial_cash: float = Field(default=100_000.0, gt=0)
    commission_bps: float = Field(default=1.0, ge=0)
    slippage_bps: float = Field(default=5.0, ge=0)
    no_trade_band: float = Field(default=0.01, ge=0, le=1)
    warmup_bars: int = Field(default=0, ge=0) 


class StrategyConfig(BaseModel):
    path: str
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("path")
    @classmethod
    def path_exists(cls, v: str) -> str:
        p = Path(v)
        if not p.exists():
            raise ValueError(f"strategy path does not exist: {v}")
        return v


class MonteCarloConfig(BaseModel):
    enabled: bool = True
    n_sims: int = Field(default=5000, ge=100)
    n_perm: int = Field(default=500, ge=50)
    block_sizes: list[int] = Field(default_factory=lambda: [2, 5, 20, 40, 80, 160])
    seed: int = 42


class OutputConfig(BaseModel):
    results_dir: str = "results"
    reports_dir: str = "reports"
    auto_open: str = "ask"  # ask | always | never
    pdf_enabled: bool = False
    pdf_format: str = "Letter"  # "Letter" | "A4" | "Legal" | "Tabloid"
    run_name: str | None = None
    save_manifest: bool = True


class AppConfig(BaseModel):
    data: DataConfig
    engine: EngineConfig = Field(default_factory=EngineConfig)
    strategy: StrategyConfig
    monte_carlo: MonteCarloConfig = Field(default_factory=MonteCarloConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


# ------------------------------------------------------------------ loading

def load_config(path: str | Path, base_path: str | Path | None = None) -> AppConfig:
    """Load a config, optionally merged over a base config.

    Precedence: `path` overrides `base_path` overrides built-in defaults.
    """
    if base_path is not None:
        base = _read_yaml(base_path)
        overlay = _read_yaml(path)
        merged = _deep_merge(base, overlay)
    else:
        merged = _read_yaml(path)
    return AppConfig.model_validate(merged)


def _read_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config not found: {p}")
    with p.open("r") as f:
        return yaml.safe_load(f) or {}


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Overlay's values win. Recurses into nested dicts."""
    out = dict(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# ------------------------------------------------------------------ hashing

def config_hash(cfg: AppConfig) -> str:
    """Stable SHA256 over the config's JSON representation."""
    payload = cfg.model_dump_json()
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


# ------------------------------------------------------------------ display

def summarize(cfg: AppConfig) -> str:
    lines = [
        f"Config summary (hash={config_hash(cfg)})",
        f"  data       : {cfg.data.path}  symbol={cfg.data.symbol}",
        f"  strategy   : {cfg.strategy.path}",
        f"  engine     : cash={cfg.engine.initial_cash:.0f}  "
        f"comm={cfg.engine.commission_bps}bps  slip={cfg.engine.slippage_bps}bps",
        f"  monte carlo: {'on' if cfg.monte_carlo.enabled else 'off'}  "
        f"sims={cfg.monte_carlo.n_sims}  seed={cfg.monte_carlo.seed}",
        f"  output     : {cfg.output.results_dir}",
    ]
    return "\n".join(lines)

# ====================================================================
# Multi-asset config — separate from AppConfig to keep the single-asset
# pipeline untouched.
# ====================================================================


class MultiDataConfig(BaseModel):
    directory: str
    pattern: str = "*.csv"
    exclude: list[str] = Field(default_factory=list)
    start: str | None = None
    end: str | None = None

    @field_validator("directory")
    @classmethod
    def directory_exists(cls, v: str) -> str:
        p = Path(v)
        if not p.exists() or not p.is_dir():
            raise ValueError(f"data directory does not exist: {v}")
        return v


class XSMomentumConfig(BaseModel):
    lookback: int = Field(default=252, ge=5)
    skip: int = Field(default=21, ge=0)
    top_k: int = Field(default=3, ge=1)
    bottom_k: int = Field(default=3, ge=0)
    rebalance_freq: str = "MS"
    long_short: bool = True
    gross_exposure: float = Field(default=1.0, gt=0, le=3)


class MultiAssetAppConfig(BaseModel):
    data: MultiDataConfig
    engine: EngineConfig = Field(default_factory=EngineConfig)
    strategy: XSMomentumConfig = Field(default_factory=XSMomentumConfig)
    monte_carlo: MonteCarloConfig = Field(default_factory=MonteCarloConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


def load_multi_config(path: str | Path, base_path: str | Path | None = None) -> MultiAssetAppConfig:
    """Load a multi-asset config, optionally merged over a base."""
    if base_path is not None:
        base = _read_yaml(base_path)
        overlay = _read_yaml(path)
        merged = _deep_merge(base, overlay)
    else:
        merged = _read_yaml(path)
    return MultiAssetAppConfig.model_validate(merged)


def multi_config_hash(cfg: MultiAssetAppConfig) -> str:
    payload = cfg.model_dump_json()
    return hashlib.sha256(payload.encode()).hexdigest()[:12]