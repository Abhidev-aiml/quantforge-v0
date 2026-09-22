"""
Report builder CLI.

Usage:
    python -m reporting.build results/runs/<run_id>
    python -m reporting.build results/runs/<run_id> --tier 1
    python -m reporting.build results/runs/<run_id> --tier 2
    python -m reporting.build results/runs/<run_id> --tier 2 --pdf
    python -m reporting.build --latest --tier 2 --pdf --pdf-format A4
    python -m reporting.build results/runs/<run_id> --name my-custom-name
    python -m reporting.build results/runs/<run_id> --auto-open always
"""
from __future__ import annotations
import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from reporting.engine import ReportEngine
from reporting.paths import resolve_report_dir
from reporting.open_report import open_in_browser
from reporting.tiers.tier1_executive import build_tier1


DEFAULT_REPORTS_DIR = "reports"
DEFAULT_AUTO_OPEN = "ask"
DEFAULT_PDF_FORMAT = "Letter"


def _latest_run(results_dir: str | Path = "results/runs") -> Path:
    """Find the most recently modified run directory."""
    runs = [p for p in Path(results_dir).glob("*") if p.is_dir()]
    if not runs:
        raise SystemExit(f"No runs found in {results_dir}")
    return max(runs, key=lambda p: p.stat().st_mtime)


def _ensure_mc_paths(run_dir: Path, n_sims: int = 2000, seed: int = 42) -> None:
    """
    If the run's monte_carlo.json is missing the `paths` section,
    simulate equity paths now and rewrite the file.

    This makes the fan chart, terminal-wealth, and drawdown panels
    work for runs produced by any runner — including run_from_config
    which doesn't do path simulation by default.
    """
    mc_path = run_dir / "monte_carlo.json"
    if not mc_path.exists():
        return

    try:
        mc = json.loads(mc_path.read_text())
    except Exception:
        return

    if "paths" in mc:
        return

    eq_path = run_dir / "equity.csv"
    if not eq_path.exists():
        return

    try:
        from validation.monte_carlo import simulate_equity_paths

        df = pd.read_csv(eq_path)
        for col in ("timestamp", "date", "index"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
                df = df.set_index(col)
                break
        num_cols = df.select_dtypes(include=[np.number]).columns
        if not len(num_cols):
            return
        equity = df[num_cols[0]].astype(float).sort_index()

        print(f"    (simulating MC paths for {run_dir.name} ...)")
        mc["paths"] = simulate_equity_paths(
            equity,
            n_sims=n_sims,
            block_size=20,
            n_paths_saved=200,
            max_bars=400,
            seed=seed,
        )
        mc_path.write_text(json.dumps(mc, indent=2, default=str))
    except Exception as e:
        print(f"    ⚠️  could not simulate paths: {e}")


def _load_run_artifacts(run_dir: Path):
    """Load ReportEngine after ensuring MC paths exist."""
    _ensure_mc_paths(run_dir)
    return ReportEngine(run_dir).load()


def build(
    run_dir: str | Path,
    reports_root: str | Path = DEFAULT_REPORTS_DIR,
    name_override: str | None = None,
    tier: int = 1,
    auto_open: str = DEFAULT_AUTO_OPEN,
    pdf: bool = False,
    pdf_format: str = DEFAULT_PDF_FORMAT,
) -> Path:
    """
    Build a report from a run directory.

    Args:
        run_dir: Path to the run artifacts directory
        reports_root: Base directory for all reports
        name_override: Optional custom report folder name
        tier: Which tier(s) to build (1=executive, 2=research, 3=cross)
        auto_open: Browser auto-open behavior (ask/always/never)
        pdf: Whether to also render PDF versions
        pdf_format: Page size for PDF export (Letter, A4, Legal, Tabloid)

    Returns:
        Path to the report directory
    """
    run_dir = Path(run_dir)
    if not run_dir.exists():
        raise SystemExit(f"Run dir not found: {run_dir}")

    # Ensure MC paths exist, then load artifacts
    art = _load_run_artifacts(run_dir)

    # Resolve where the report should live
    report_dir = resolve_report_dir(
        reports_root, art.manifest, override=name_override
    )

    # Copy reference artifacts alongside the report
    for ref in ("manifest.json", "metrics.json"):
        src = run_dir / ref
        if src.exists():
            shutil.copy2(src, report_dir / ref)

    # Build HTML tiers
    html_outputs: list[Path] = []
    if tier >= 1:
        out = build_tier1(run_dir, output_path=report_dir / "report_executive.html")
        html_outputs.append(out)
    if tier >= 2:
        from reporting.tiers.tier2_research import build_tier2
        out = build_tier2(run_dir, output_path=report_dir / "report_full.html")
        html_outputs.append(out)

    # Optional PDF rendering
    pdf_outputs: list[Path] = []
    if pdf:
        from reporting.export.pdf import render_pdfs, is_available
        if not is_available():
            print()
            print("⚠️  Playwright is not available. To enable PDF export:")
            print("      pip install playwright")
            print("      python -m playwright install chromium")
        else:
            print()
            print(f"Rendering PDFs ({pdf_format})...")
            jobs = [(html, html.with_suffix(".pdf")) for html in html_outputs]
            pdf_outputs = render_pdfs(jobs, pdf_format=pdf_format)

    # Print summary
    print()
    print("=" * 72)
    print(f"  Report: {report_dir}")
    for out in html_outputs:
        size_kb = out.stat().st_size / 1024
        print(f"    {out.name:32s}  {size_kb:8.1f} KB")
    for out in pdf_outputs:
        size_kb = out.stat().st_size / 1024
        print(f"    {out.name:32s}  {size_kb:8.1f} KB")
    print("=" * 72)

    # Auto-open the first HTML output
    if html_outputs:
        open_in_browser(html_outputs[0], mode=auto_open)

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
    p.add_argument("--pdf", action="store_true",
                   help="also render PDF versions of the reports")
    p.add_argument("--pdf-format", default=DEFAULT_PDF_FORMAT,
                   choices=["Letter", "A4", "Legal", "Tabloid"],
                   help=f"page size for PDF export (default: {DEFAULT_PDF_FORMAT})")
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
        pdf=args.pdf,
        pdf_format=args.pdf_format,
    )


if __name__ == "__main__":
    main()