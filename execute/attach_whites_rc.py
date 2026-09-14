"""
Attach an existing White's RC result to run directories.

Usage:
    python -m execute.attach_whites_rc results/whites_rc/20260913_202834
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def _latest_run_for_strategy(strategy_stem: str) -> Path | None:
    """Find the most recent run dir for a strategy stem."""
    candidates = []
    for r in Path("results/runs").glob("*/"):
        m = r / "manifest.json"
        if not m.exists():
            continue
        try:
            man = json.loads(m.read_text())
            sp = man.get("config", {}).get("strategy", {}).get("path", "")
            if Path(sp).stem == strategy_stem:
                candidates.append((r.stat().st_mtime, r))
        except Exception:
            continue
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[0])[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("rc_dir", help="path to results/whites_rc/<timestamp>/")
    args = p.parse_args()

    rc_dir = Path(args.rc_dir)
    rc_path = rc_dir / "whites_rc.json"
    if not rc_path.exists():
        raise SystemExit(f"No whites_rc.json in {rc_dir}")

    rc = json.loads(rc_path.read_text())

    # Extract the strategy stems that participated in the RC test
    strategies = set()
    for c in rc.get("top_5_combos", []):
        label = c.get("label", "")
        if " × " in label:
            strategies.add(label.split(" × ")[0])
    # Also try the broader combo list if present
    if not strategies:
        for label in rc.get("combo_labels", []) or []:
            if " × " in label:
                strategies.add(label.split(" × ")[0])

    print(f"RC result: {rc_dir}")
    print(f"  p-value:      {rc.get('p_value')}")
    print(f"  best combo:   {rc.get('best_combo')}")
    print(f"  strategies:   {sorted(strategies)}")
    print()

    attached = 0
    for stem in sorted(strategies):
        run_dir = _latest_run_for_strategy(stem)
        if run_dir is None:
            print(f"  ⚠️  no run found for {stem}")
            continue
        (run_dir / "whites_rc.json").write_text(
            json.dumps(rc, indent=2, default=str)
        )
        print(f"  ✅ {stem} → {run_dir.name}")
        attached += 1

    print(f"\nAttached to {attached} run directories.")


if __name__ == "__main__":
    main()