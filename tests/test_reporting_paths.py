"""Tests for reporting.paths, reporting.build, and open behavior."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from reporting.paths import (
    infer_timeframe,
    slug,
    build_report_name,
    resolve_report_dir,
)
from reporting.open_report import open_in_browser


# ---------------------------------------------------------------- helpers

@pytest.mark.parametrize("filename,expected", [
    ("xauusd_1D_comma.csv",     "1d"),
    ("xauusd_1h_comma.csv",     "1h"),
    ("BRENTCMDUSD240_comma.csv", "4h"),
    ("EURUSD1440_comma.csv",    "1d"),
    ("randomfile.csv",          "na"),
    ("SPY_daily.csv",           "1d"),
    ("BTC_15m.csv",             "15m"),
])
def test_infer_timeframe(filename, expected):
    assert infer_timeframe(filename) == expected


def test_infer_timeframe_none():
    assert infer_timeframe(None) == "na"


@pytest.mark.parametrize("raw,expected", [
    ("Abs Momentum", "abs-momentum"),
    ("my_strategy_v2", "my-strategy-v2"),
    ("07_absolute_momentum", "07-absolute-momentum"),
    ("XAU-USD", "xau-usd"),
    ("!!!", "na"),
    ("", "na"),
])
def test_slug(raw, expected):
    assert slug(raw) == expected


def test_build_report_name_full():
    manifest = {
        "started_utc": "2026-09-13T15:46:05.328+00:00",
        "config": {
            "data": {
                "symbol": "XAUUSD",
                "path": "data/raw/daily/xauusd_1D_comma.csv",
            },
            "strategy": {"path": "strategies/07_absolute_momentum.py"},
        },
    }
    name = build_report_name(manifest)
    assert name == "xauusd-1d-07-absolute-momentum-20260913-154605"


def test_build_report_name_explicit_timeframe_wins():
    manifest = {
        "started_utc": "2026-09-13T15:46:05+00:00",
        "config": {
            "data": {
                "symbol": "XAUUSD",
                "path": "data/raw/daily/xauusd_1D_comma.csv",
                "timeframe": "4h",   # explicit override
            },
            "strategy": {"path": "strategies/x.py"},
        },
    }
    name = build_report_name(manifest)
    assert "-4h-" in name
    assert "-1d-" not in name


def test_resolve_report_dir_creates(tmp_path):
    manifest = {
        "started_utc": "2026-01-01T00:00:00+00:00",
        "config": {
            "data": {"symbol": "TEST", "path": "x_1D.csv"},
            "strategy": {"path": "s.py"},
        },
    }
    out = resolve_report_dir(tmp_path, manifest)
    assert out.exists()
    assert out.parent == tmp_path
    assert out.name.startswith("test-1d-s-")


def test_resolve_report_dir_override(tmp_path):
    manifest = {"config": {}}
    out = resolve_report_dir(tmp_path, manifest, override="my-custom")
    assert out == tmp_path / "my-custom"
    assert out.exists()


# ---------------------------------------------------------------- open

def test_open_never_does_nothing(tmp_path):
    f = tmp_path / "x.html"
    f.write_text("<html></html>")
    # mode=never should not raise and should return False
    assert open_in_browser(f, mode="never") is False


def test_open_missing_file_returns_false(tmp_path, capsys):
    out = open_in_browser(tmp_path / "nope.html", mode="always")
    assert out is False
    captured = capsys.readouterr()
    assert "not found" in captured.err
