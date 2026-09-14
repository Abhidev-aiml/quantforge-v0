"""Tests for engine.config."""
from __future__ import annotations
from pathlib import Path

import pytest
import yaml

from engine.config import load_config, config_hash, AppConfig


@pytest.fixture
def valid_config(tmp_path, small_df):
    """Write a minimal valid config to disk."""
    csv = tmp_path / "data.csv"
    small_df.to_csv(csv, index=False)
    strat = tmp_path / "strat.py"
    strat.write_text("import pandas as pd\n"
                     "def generate_signals(df):\n"
                     "    return pd.Series(0.0, index=df.index)\n")

    cfg = {
        "data": {"path": str(csv), "symbol": "TEST"},
        "strategy": {"path": str(strat)},
    }
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return p


def test_load_valid_config(valid_config):
    cfg = load_config(valid_config)
    assert isinstance(cfg, AppConfig)
    assert cfg.engine.initial_cash == 100_000.0
    assert cfg.monte_carlo.seed == 42


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.yaml")


def test_missing_data_path_raises(tmp_path):
    strat = tmp_path / "s.py"
    strat.write_text("def generate_signals(df): return None\n")
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump({
        "data": {"path": "/does/not/exist.csv"},
        "strategy": {"path": str(strat)},
    }))
    with pytest.raises(Exception):
        load_config(cfg)


def test_deep_merge_overrides_only_specified_keys(valid_config, tmp_path):
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text(yaml.safe_dump({
        "engine": {"slippage_bps": 20.0},
    }))
    cfg = load_config(overlay, base_path=valid_config)
    # override applied
    assert cfg.engine.slippage_bps == 20.0
    # base preserved
    assert cfg.engine.commission_bps == 1.0
    assert cfg.engine.initial_cash == 100_000.0


def test_config_hash_is_deterministic(valid_config):
    h1 = config_hash(load_config(valid_config))
    h2 = config_hash(load_config(valid_config))
    assert h1 == h2


def test_config_hash_changes_when_values_change(valid_config, tmp_path):
    h1 = config_hash(load_config(valid_config))
    overlay = tmp_path / "o.yaml"
    overlay.write_text(yaml.safe_dump({
        "engine": {"slippage_bps": 99.0},
    }))
    h2 = config_hash(load_config(overlay, base_path=valid_config))
    assert h1 != h2