"""
Batch comparison across recent runs.

Usage:
    python -m execute.batch_compare             # last 5 runs
    python -m execute.batch_compare --n 10      # last 10 runs
    python -m execute.batch_compare --pattern gold_gc
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import pandas as pd


def _load_run(run_dir: Path) -> dict | None:
    m_path = run_dir / "metrics.json"
    man_path = run_dir / "manifest.json"
    if not m_path.exists() or not man_path.exists():
        return None
    m = json.loads(m_path.read_text())
    man = json.loads(man_path.read_text())
    strat = Path(man["config"]["strategy"]["path"]).stem
    return {
        "run_id": run_dir.name,
        "strategy": strat,
        "sharpe": round(m.get("sharpe", float("nan")), 3),
        "sortino": round(m.get("sortino", float("nan")), 3),
        "CAGR": f"{m.get('CAGR', 0)*100:+.2f}%",
        "vol": f"{m.get('volatility', 0)*100:.2f}%",
        "maxDD": f"{m.get('max_drawdown', 0)*100:+.2f}%",
        "calmar": round(m.get("calmar", float("nan")), 3),
        "trades": int(m.get("num_trades", 0)) if "num_trades" in m else 0,
        "win_rate": f"{m.get('win_rate', 0)*100:.1f}%" if "win_rate" in m else "—",
        "pf": round(m.get("profit_factor", 0), 3) if "profit_factor" in m else "—",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=5,
                   help="number of most-recent runs to include")
    p.add_argument("--pattern", type=str, default=None,
                   help="filter strategy stem containing this substring")
    args = p.parse_args()

    runs_root = Path("results/runs")
    if not runs_root.exists():
        raise SystemExit(f"No runs directory: {runs_root}")

    all_runs = sorted(runs_root.glob("*/"),
                      key=lambda p: p.stat().st_mtime,
                      reverse=True)

    rows = []
    for r in all_runs:
        row = _load_run(r)
        if row is None:
            continue
        if args.pattern and args.pattern not in row["strategy"]:
            continue
        rows.append(row)
        if len(rows) >= args.n:
            break

    if not rows:
        print("No runs found.")
        return

    df = pd.DataFrame(rows)

    # Column order
    cols = ["strategy", "sharpe", "sortino", "CAGR", "vol",
            "maxDD", "calmar", "trades", "win_rate", "pf", "run_id"]
    df = df[[c for c in cols if c in df.columns]]

    print()
    print("=" * 130)
    print(f"BATCH COMPARISON — {len(rows)} most recent runs")
    if args.pattern:
        print(f"Filter: strategy stem contains '{args.pattern}'")
    print("=" * 130)
    print(df.to_string(index=False))
    print("=" * 130)
    print()
    print("Reading notes:")
    print("  trades = round-trip trades (0 if extractor found none)")
    print("  pf = profit factor = gross wins / |gross losses|")
    print("  Higher Sharpe is not automatically better; check Calmar and trades.")
    print("  Compare trades column: more trades = more cost drag.")


if __name__ == "__main__":
    main()