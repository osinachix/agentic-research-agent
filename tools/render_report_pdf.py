"""Render synthesized competitor-analysis content into a branded PDF.

Usage:
  python render_report_pdf.py --content .tmp/run_2026-07-17/report_content.json \\
      --brand business/brand/brand.yaml --out deliverables/competitor_analysis_2026-07-17.pdf

--content JSON shape (produced by Claude during the workflow's synthesis step).
Competitors are grouped by business division, since a multi-division company
researches and compares competitors separately per division:
{
  "report_date": "2026-07-17",
  "business_name": str, "business_summary": str,
  "executive_summary": str,
  "divisions": [
    {
      "name": str, "summary": str,       # "summary" is optional context for the division
      "competitors": [
        {
          "name": str, "website": str, "summary": str, "offering": str,
          "pricing": {"model": str, "tiers": [...], "notes": str},
          "positioning": str, "strengths": [str], "gaps_or_weaknesses": [str],
          "perceived_target_customer": str, "confidence_notes": str,
          "changes_since_last_report": [str]   # omit or [] if no prior snapshot
        }
      ],
      "comparison_matrix": {"columns": [str], "rows": [{"label": str, "cells": [str]}]},  # optional
      "charts": [{"title": str, "path": str}]    # optional, paths to PNGs on disk
    }
  ],
  "swot": {"strengths": [str], "weaknesses": [str], "opportunities": [str], "threats": [str]},  # optional
  "growth_opportunities": [str],    # optional, high-growth / new revenue stream ideas
  "brand_assessment": {             # optional
    "current_perception": str,
    "messaging_recommendations": [str], "website_recommendations": [str], "marketing_recommendations": [str]
  },
  "action_plan": [{"initiative": str, "timeframe": str, "impact": str, "rationale": str}],  # optional
  "recommendations": [str],   # cross-cutting, group-level recommendations
  "charts": [{"title": str, "path": str}]   # optional, group-level charts (e.g. an opportunity map)
}

Requires `playwright install chromium` to have been run once in this project's
venv beforehand -- pip installing the `playwright` package alone does not fetch
the browser binary. Fails fast (non-zero exit, message on stderr) on missing
content fields, an unreadable/missing logo, or an invalid hex color, before any
browser is launched.
"""

import argparse
import base64
import json
import re
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

REQUIRED_CONTENT_FIELDS = ["report_date", "business_name", "executive_summary", "divisions"]


def resolve_path(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else PROJECT_ROOT / path


def to_data_uri(path: Path) -> str:
    ext = path.suffix.lstrip(".").lower()
    mime = "image/png" if ext == "png" else "image/svg+xml" if ext == "svg" else f"image/{ext}"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def validate_hex(name: str, value: str) -> None:
    if not HEX_RE.match(value or ""):
        raise ValueError(f"brand color '{name}' is not a valid hex code: {value!r}")


def load_content(content_path: Path) -> dict:
    content = json.loads(content_path.read_text(encoding="utf-8"))
    missing = [f for f in REQUIRED_CONTENT_FIELDS if f not in content]
    if missing:
        raise ValueError(f"content file missing required fields: {missing}")
    return content


def load_brand(brand_path: Path) -> dict:
    brand = yaml.safe_load(brand_path.read_text(encoding="utf-8"))
    colors = brand.get("colors", {})
    for role in ("primary", "secondary", "accent", "text", "background"):
        validate_hex(role, colors.get(role, ""))

    logo_path = resolve_path(brand["logo"]["path"])
    if not logo_path.exists():
        raise FileNotFoundError(f"logo file not found: {logo_path}")

    brand["_logo_data_uri"] = to_data_uri(logo_path)
    return brand


def embed_charts(content: dict) -> None:
    chart_lists = [content.get("charts", [])]
    chart_lists += [division.get("charts", []) for division in content.get("divisions", [])]
    for charts in chart_lists:
        for chart in charts:
            chart_path = resolve_path(chart["path"])
            if not chart_path.exists():
                raise FileNotFoundError(f"chart image not found: {chart_path}")
            chart["_data_uri"] = to_data_uri(chart_path)


def render_html(content: dict, brand: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("report.html.j2")
    has_changes_section = any(
        c.get("changes_since_last_report")
        for division in content["divisions"]
        for c in division.get("competitors", [])
    )
    return template.render(content=content, brand=brand, has_changes_section=has_changes_section)


def render_pdf(html: str, out_path: Path, page_size: str, footer_text: str) -> None:
    from playwright.sync_api import sync_playwright

    footer_template = f"""
    <div style="font-size:8px; width:100%; text-align:center; color:#888888; font-family:Arial,Helvetica,sans-serif; padding:0 16mm;">
      {footer_text} &nbsp;&mdash;&nbsp; <span class="pageNumber"></span> / <span class="totalPages"></span>
    </div>
    """

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="load")
        page.pdf(
            path=str(out_path),
            format=page_size,
            print_background=True,
            display_header_footer=True,
            header_template="<div></div>",
            footer_template=footer_template,
            margin={"top": "18mm", "bottom": "20mm", "left": "16mm", "right": "16mm"},
        )
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--content", required=True)
    parser.add_argument("--brand", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    try:
        content = load_content(resolve_path(args.content))
        brand = load_brand(resolve_path(args.brand))
        embed_charts(content)
    except (ValueError, FileNotFoundError, KeyError, yaml.YAMLError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    try:
        html = render_html(content, brand)
    except Exception as e:  # jinja2 template errors, malformed content shapes, etc.
        print(f"error rendering template: {e}", file=sys.stderr)
        return 1

    out_path = resolve_path(args.out)
    report_defaults = brand.get("report_defaults", {})
    page_size = report_defaults.get("page_size", "A4")
    footer_text = report_defaults.get("footer_text", "")
    try:
        render_pdf(html, out_path, page_size, footer_text)
    except Exception as e:
        print(f"error rendering PDF (has `playwright install chromium` been run?): {e}", file=sys.stderr)
        return 1

    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
