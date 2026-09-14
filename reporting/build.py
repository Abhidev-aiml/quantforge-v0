"""
Report builder CLI.

Usage:
    python -m reporting.build results/runs/<run_id>
    python -m reporting.build results/runs/<run_id> --tier 1
    python -m reporting.build results/runs/<run_id> --name my-custom-name
    python -m reporting.build results/runs/<run_id> --auto-open always
    python -m reporting.build --latest
"""
from __future__ import annotations
import argparse
import json
import shutil
from pathlib import Path

from reporting.engine import ReportEngine
from reporting.paths import resolve_report_dir
from reporting.open_report import open_in_browser
from reporting.tiers.tier1_executive import build_tier1


DEFAULT_REPORTS_DIR = "reports"
DEFAULT_AUTO_OPEN = "ask"


def _latest_run(results_dir: str | Path = "results/runs") -> Path:
    """Find the most recently modified run directory."""
    runs = [p for p in Path(results_dir).glob("*") if p.is_dir()]
    if not runs:
        raise SystemExit(f"No runs found in {results_dir}")
    return max(runs, key=lambda p: p.stat().st_mtime)


def build(
    run_dir: str | Path,
    reports_root: str | Path = DEFAULT_REPORTS_DIR,
    name_override: str | None = None,
    tier: int = 1,
    auto_open: str = DEFAULT_AUTO_OPEN,
) -> Path:
    """
    Build a report from a run directory.

    Args:
        run_dir: Path to the run artifacts directory
        reports_root: Base directory for all reports
        name_override: Optional custom report folder name
        tier: Which tier(s) to build (1=executive, 2=research, 3=cross)
        auto_open: Browser auto-open behavior (ask/always/never)

    Returns:
        Path to the report directory
    """
    run_dir = Path(run_dir)
    if not run_dir.exists():
        raise SystemExit(f"Run dir not found: {run_dir}")

    # Load artifacts once so we can pull the manifest for naming
    art = ReportEngine(run_dir).load()

    # Resolve where the report should live
    report_dir = resolve_report_dir(
        reports_root, art.manifest, override=name_override
    )

    # Copy reference artifacts alongside the report
    for ref in ("manifest.json", "metrics.json"):
        src = run_dir / ref
        if src.exists():
            shutil.copy2(src, report_dir / ref)

   # Build tiers
    outputs = []
    if tier >= 1:
        out = build_tier1(run_dir, output_path=report_dir / "report_executive.html")
        outputs.append(out)
    if tier >= 2:
        from reporting.tiers.tier2_research import build_tier2
        out = build_tier2(run_dir, output_path=report_dir / "report_full.html")
        outputs.append(out)

    # Print summary
    print()
    print("=" * 72)
    print(f"  Report: {report_dir}")
    for out in outputs:
        size_kb = out.stat().st_size / 1024
        print(f"    {out.name:32s}  {size_kb:8.1f} KB")
    print("=" * 72)

    # Auto-open
    if outputs:
        open_in_browser(outputs[0], mode=auto_open)

    return report_dir


def main():
    p = argparse.ArgumentParser(
        description="Build polished reports from QuantForge backtest runs"
    )
    p.add_argument("run_dir", nargs="?", help="path to a run directory")
    p.add_argument("--latest", action="store_true",
                   help="use the most recent run in results/runs/")
    p.add_argument("--reports-dir", default=DEFAULT_REPORTS_DIR,
                   help=f"where to write reports (default: {DEFAULT_REPORTS_DIR})")
    p.add_argument("--name", default=None,
                   help="override the report folder name")
    p.add_argument("--tier", type=int, default=1,
                   help="which tier(s) to build (1=exec, 2=research, 3=cross)")
    p.add_argument("--auto-open", choices=["ask", "always", "never"],
                   default=DEFAULT_AUTO_OPEN,
                   help="browser auto-open behavior")
    args = p.parse_args()

    if args.latest:
        run_dir = _latest_run()
        print(f"Using latest run: {run_dir}")
    elif args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        raise SystemExit("Provide a run_dir or use --latest")

    build(
        run_dir=run_dir,
        reports_root=args.reports_dir,
        name_override=args.name,
        tier=args.tier,
        auto_open=args.auto_open,
    )


if __name__ == "__main__":
    main()
