"""
RunContext — one object per backtest run.

Creates a unique run directory, writes a manifest at start and end,
and exposes helper paths for downstream artifacts.
"""
from __future__ import annotations
import json
import platform
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.config import AppConfig, config_hash


def _git_sha() -> tuple[str, bool]:
    """Return (short_sha, is_dirty). Empty string if not a git repo."""
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            stderr=subprocess.DEVNULL,
        ).decode().strip() != ""
        return sha, dirty
    except Exception:
        return "", False


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class RunContext:
    """One run's identity and artifact directory."""

    config: AppConfig
    run_id: str = field(default="")
    run_dir: Path = field(default=Path("."))
    started_utc: str = field(default="")
    manifest: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, config: AppConfig) -> "RunContext":
        # unique run id: timestamp + short uuid
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        suffix = uuid.uuid4().hex[:6]
        run_id = config.output.run_name or f"{ts}_{suffix}"

        run_dir = Path(config.output.results_dir) / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        sha, dirty = _git_sha()
        ctx = cls(
            config=config,
            run_id=run_id,
            run_dir=run_dir,
            started_utc=_now_utc(),
            manifest={
                "run_id": run_id,
                "started_utc": _now_utc(),
                "git_sha": sha,
                "git_dirty": dirty,
                "config_hash": config_hash(config),
                "python_version": sys.version.split()[0],
                "platform": platform.platform(),
                "config": config.model_dump(),
            },
        )
        if config.output.save_manifest:
            ctx._write_manifest()
        return ctx

    # ---------------------------------------------------------- paths

    @property
    def equity_path(self) -> Path:
        return self.run_dir / "equity.csv"

    @property
    def fills_path(self) -> Path:
        return self.run_dir / "fills.csv"

    @property
    def trades_path(self) -> Path:
        return self.run_dir / "trades.csv"

    @property
    def metrics_path(self) -> Path:
        return self.run_dir / "metrics.json"

    @property
    def mc_path(self) -> Path:
        return self.run_dir / "monte_carlo.json"

    @property
    def manifest_path(self) -> Path:
        return self.run_dir / "manifest.json"

    # ---------------------------------------------------------- writing

    def set_data_hash(self, data_hash: str) -> None:
        self.manifest["data_hash"] = data_hash
        self._write_manifest()

    def add_results(self, summary: dict) -> None:
        self.manifest["finished_utc"] = _now_utc()
        self.manifest["results"] = summary
        self._write_manifest()

    def _write_manifest(self) -> None:
        if not self.config.output.save_manifest:
            return
        self.manifest_path.write_text(
            json.dumps(self.manifest, indent=2, default=str)
        )