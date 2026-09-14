"""Tests for engine.run_context."""
from __future__ import annotations
import json
from pathlib import Path

import pytest
import yaml

from engine.config import load_config
from engine.run_context import RunContext


@pytest.fixture
def cfg_file(tmp_path, small_df):
    csv = tmp_path / "d.csv"
    small_df.to_csv(csv, index=False)
    strat = tmp_path / "s.py"
    strat.write_text("def generate_signals(df):\n    return None\n")
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump({
        "data": {"path": str(csv), "symbol": "T"},
        "strategy": {"path": str(strat)},
        "output": {"results_dir": str(tmp_path / "results")},
    }))
    return p


def test_create_writes_manifest(cfg_file):
    cfg = load_config(cfg_file)
    ctx = RunContext.create(cfg)

    assert ctx.run_dir.exists()
    assert ctx.manifest_path.exists()

    manifest = json.loads(ctx.manifest_path.read_text())
    assert manifest["run_id"] == ctx.run_id
    assert "config_hash" in manifest
    assert manifest["config"]["data"]["symbol"] == "T"


def test_data_hash_update_persists(cfg_file):
    cfg = load_config(cfg_file)
    ctx = RunContext.create(cfg)
    ctx.set_data_hash("abc123")

    manifest = json.loads(ctx.manifest_path.read_text())
    assert manifest["data_hash"] == "abc123"


def test_add_results_persists(cfg_file):
    cfg = load_config(cfg_file)
    ctx = RunContext.create(cfg)
    ctx.add_results({"sharpe": 0.5, "n_trades": 42})

    manifest = json.loads(ctx.manifest_path.read_text())
    assert manifest["results"]["sharpe"] == 0.5
    assert manifest["results"]["n_trades"] == 42
    assert "finished_utc" in manifest


def test_run_ids_are_unique(cfg_file):
    cfg = load_config(cfg_file)
    ctx1 = RunContext.create(cfg)
    ctx2 = RunContext.create(cfg)
    assert ctx1.run_id != ctx2.run_id
    assert ctx1.run_dir != ctx2.run_dir