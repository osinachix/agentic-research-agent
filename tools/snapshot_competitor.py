"""Save and retrieve dated competitor research snapshots.

Snapshot JSON schema (what --data-file must contain for `save`):
{
  "competitor_name": str, "slug": str (optional, derived from name if absent),
  "website": str, "sources": [str],
  "summary": str, "offering": str,
  "pricing": {"model": str, "tiers": [...], "notes": str},
  "positioning": str, "strengths": [str], "gaps_or_weaknesses": [str],
  "perceived_target_customer": str, "confidence_notes": str
}

Usage:
  python snapshot_competitor.py save --slug acme-co --date 2026-07-17 --data-file .tmp/acme.json
  python snapshot_competitor.py latest --slug acme-co [--before 2026-07-17]

`save` writes research/competitors/<slug>/<date>.json and updates registry.json.
Re-running with the same slug+date overwrites cleanly (idempotent).
`latest` prints the most recent snapshot JSON before the given date (default: today),
or prints {"has_prior": false} and exits 0 if none exists.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parent.parent / "research" / "competitors"
REGISTRY_PATH = RESEARCH_DIR / "registry.json"

REQUIRED_FIELDS = [
    "competitor_name", "website", "summary", "offering", "pricing",
    "positioning", "strengths", "gaps_or_weaknesses",
    "perceived_target_customer",
]


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "competitor"


def load_registry() -> dict:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {}


def save_registry(registry: dict) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def cmd_save(args: argparse.Namespace) -> int:
    data_path = Path(args.data_file)
    if not data_path.exists():
        print(f"error: data file not found: {data_path}", file=sys.stderr)
        return 1

    data = json.loads(data_path.read_text(encoding="utf-8"))
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        print(f"error: data file missing required fields: {missing}", file=sys.stderr)
        return 1

    slug = args.slug or slugify(data["competitor_name"])
    snap_date = args.date or date.today().isoformat()
    data["slug"] = slug
    data["date"] = snap_date
    data.setdefault("sources", [])
    data.setdefault("confidence_notes", "")

    out_dir = RESEARCH_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{snap_date}.json"
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    registry = load_registry()
    entry = registry.get(slug, {})
    entry["canonical_name"] = data["competitor_name"]
    entry["domain"] = data.get("website", entry.get("domain", ""))
    entry.setdefault("first_seen", snap_date)
    registry[slug] = entry
    save_registry(registry)

    print(f"saved {out_path}")
    return 0


def cmd_latest(args: argparse.Namespace) -> int:
    before = args.before or date.today().isoformat()
    comp_dir = RESEARCH_DIR / args.slug
    if not comp_dir.exists():
        print(json.dumps({"has_prior": False}))
        return 0

    candidates = sorted(
        (p.stem for p in comp_dir.glob("*.json") if p.stem < before),
        reverse=True,
    )
    if not candidates:
        print(json.dumps({"has_prior": False}))
        return 0

    snap_path = comp_dir / f"{candidates[0]}.json"
    snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    snapshot["has_prior"] = True
    print(json.dumps(snapshot, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    save_p = sub.add_parser("save", help="save a dated competitor snapshot")
    save_p.add_argument("--slug", help="stable slug; derived from competitor_name if omitted")
    save_p.add_argument("--date", help="YYYY-MM-DD; defaults to today")
    save_p.add_argument("--data-file", required=True, help="path to the snapshot JSON to save")
    save_p.set_defaults(func=cmd_save)

    latest_p = sub.add_parser("latest", help="fetch the most recent prior snapshot for a slug")
    latest_p.add_argument("--slug", required=True)
    latest_p.add_argument("--before", help="YYYY-MM-DD; defaults to today")
    latest_p.set_defaults(func=cmd_latest)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
