"""Structurally diff a competitor's current snapshot against its most recent prior one.

Usage:
  python diff_snapshots.py --slug acme-co --current 2026-07-17 [--previous 2026-06-01]

If --previous is omitted, auto-resolves the most recent snapshot dated before --current
(same lookup as `snapshot_competitor.py latest`). Prints JSON to stdout:
  {"has_prior": false}
or
  {
    "has_prior": true, "previous_date": str,
    "pricing_changed": bool, "pricing": {"old": ..., "new": ...},
    "positioning_changed": bool, "positioning": {"old": ..., "new": ...},
    "strengths_added": [str], "strengths_removed": [str],
    "gaps_added": [str], "gaps_removed": [str],
    "summary_of_changes": [str]
  }

This is a pure structural diff -- no judgment calls. Claude turns these bullets
into narrative prose when synthesizing the report.
"""

import argparse
import json
import sys
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parent.parent / "research" / "competitors"


def find_previous(slug: str, before: str) -> dict | None:
    comp_dir = RESEARCH_DIR / slug
    if not comp_dir.exists():
        return None
    candidates = sorted(
        (p.stem for p in comp_dir.glob("*.json") if p.stem < before),
        reverse=True,
    )
    if not candidates:
        return None
    snap_path = comp_dir / f"{candidates[0]}.json"
    return json.loads(snap_path.read_text(encoding="utf-8"))


def load_snapshot(slug: str, snap_date: str) -> dict:
    snap_path = RESEARCH_DIR / slug / f"{snap_date}.json"
    if not snap_path.exists():
        raise FileNotFoundError(f"snapshot not found: {snap_path}")
    return json.loads(snap_path.read_text(encoding="utf-8"))


def diff(current: dict, previous: dict) -> dict:
    result: dict = {"has_prior": True, "previous_date": previous.get("date", "")}

    old_pricing, new_pricing = previous.get("pricing", {}), current.get("pricing", {})
    result["pricing_changed"] = old_pricing != new_pricing
    result["pricing"] = {"old": old_pricing, "new": new_pricing}

    old_pos, new_pos = previous.get("positioning", ""), current.get("positioning", "")
    result["positioning_changed"] = old_pos != new_pos
    result["positioning"] = {"old": old_pos, "new": new_pos}

    old_strengths, new_strengths = set(previous.get("strengths", [])), set(current.get("strengths", []))
    result["strengths_added"] = sorted(new_strengths - old_strengths)
    result["strengths_removed"] = sorted(old_strengths - new_strengths)

    old_gaps, new_gaps = set(previous.get("gaps_or_weaknesses", [])), set(current.get("gaps_or_weaknesses", []))
    result["gaps_added"] = sorted(new_gaps - old_gaps)
    result["gaps_removed"] = sorted(old_gaps - new_gaps)

    bullets = []
    if result["pricing_changed"]:
        bullets.append(f"Pricing changed: {old_pricing} -> {new_pricing}")
    if result["positioning_changed"]:
        bullets.append(f"Positioning changed: '{old_pos}' -> '{new_pos}'")
    for s in result["strengths_added"]:
        bullets.append(f"New strength: {s}")
    for s in result["strengths_removed"]:
        bullets.append(f"No longer observed as a strength: {s}")
    for g in result["gaps_added"]:
        bullets.append(f"New gap/weakness: {g}")
    for g in result["gaps_removed"]:
        bullets.append(f"Gap/weakness no longer observed: {g}")
    result["summary_of_changes"] = bullets

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--current", required=True, help="YYYY-MM-DD of the snapshot to diff")
    parser.add_argument("--previous", help="YYYY-MM-DD of the prior snapshot; auto-resolved if omitted")
    args = parser.parse_args()

    try:
        current = load_snapshot(args.slug, args.current)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.previous:
        try:
            previous = load_snapshot(args.slug, args.previous)
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    else:
        previous = find_previous(args.slug, args.current)

    if previous is None:
        print(json.dumps({"has_prior": False}))
        return 0

    print(json.dumps(diff(current, previous), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
