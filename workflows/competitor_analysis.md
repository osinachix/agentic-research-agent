# Workflow: Competitor Analysis (Branded PDF)

## Objective

On demand, produce a branded, multi-section PDF that profiles the user's competitors, compares them against the user's business, and recommends improvements — saved to `deliverables/competitor_analysis_<YYYY-MM-DD>.pdf`.

## Inputs

- `business/profile.yaml` — the user's business profile. If missing, create it by asking the user for the missing fields (see schema below). If present, briefly confirm it's still accurate before a run that will inform recommendations.
- `business/brand/brand.yaml` + `business/brand/logo.png` — the brand config. If `brand.yaml` doesn't exist yet:
  - Check for raw brand images anywhere in the project (a logo image, a brand-guidelines sheet/export).
  - If found, read them directly (native image understanding — no OCR tool needed), extract hex colors, font names, and logo usage rules, and write `business/brand/brand.yaml`. Copy the source logo to `business/brand/logo.png` and any guideline sheet(s) to `business/brand/source/`.
  - If nothing is found, ask the user for hex colors, font names, and a logo file rather than fabricating any of it.
- Optional: a starter list of known competitors (`business/profile.yaml: known_competitors`). Not required — discovery is autonomous by default.

## Steps

Agent = Claude, using built-in reasoning/WebSearch/WebFetch/dataviz skill. Tool = a Python script in `tools/`.

1. **Agent** — Load `business/profile.yaml`. If missing, ask the user for: company name, website, industry, offering summary + core products/services, target customer description + segments, pricing model + tiers, positioning statement + USPs, geographic market. Write the file. If present, use as-is unless the user flags a change.
2. **Agent** — Load `business/brand/brand.yaml`. If missing, run the brand-extraction sub-step described in Inputs above. Validate: all hex codes are well-formed (`#RRGGBB`), `logo.path` exists on disk. If extraction is ambiguous (e.g. a font name isn't clearly stated in the source image), ask rather than guess.
3. **Agent** — Discover competitors via WebSearch, seeded by the business profile's offering, target customer, and positioning (plus `known_competitors` if present). Aim for 4-6 relevant competitors. If the market is large/ambiguous, propose the shortlist to the user before spending research effort on it.
4. **Agent** — For each competitor, research via WebSearch/WebFetch: what they offer, pricing model, positioning/messaging, perceived target customer, notable strengths, notable gaps/weaknesses, and cite sources. Populate the per-competitor schema (see `tools/snapshot_competitor.py` docstring for the exact fields).
5. **Tool** — `python tools/snapshot_competitor.py save --slug <slug> --date <YYYY-MM-DD> --data-file <path-to-json>` for each competitor. This writes `research/competitors/<slug>/<date>.json` and updates `research/competitors/registry.json`. Re-running for the same slug+date overwrites cleanly (idempotent).
6. **Tool** — `python tools/diff_snapshots.py --slug <slug> --current <date>` for each competitor. Returns `{"has_prior": false}` when there's nothing to compare yet (not an error), or a structured diff (pricing/positioning/strengths changes) when a prior snapshot exists.
7. **Agent** — Synthesize the full report content as JSON (see `tools/render_report_pdf.py` docstring for the current shape): executive summary, competitors grouped per business division (each with its own comparison matrix), gaps/opportunities and concrete recommendations, and — only if at least one competitor had `has_prior: true` — a "changes since last report" note per competitor written from the diff output. For a multi-division/strategy-level request, also include: a group-level SWOT, growth opportunities, a brand positioning assessment, and a prioritized action plan (see the same docstring). Save to `.tmp/run_<date>/report_content.json`.
8. **Agent**, via the **dataviz** skill — when there are 3+ competitors, optionally generate a positioning-matrix and/or pricing-comparison chart as PNGs in `.tmp/run_<date>/charts/`, styled with the brand's colors. Reference the file paths in `report_content.json`. Skip this step if it wouldn't add clarity.
9. **Tool** — `python tools/render_report_pdf.py --content .tmp/run_<date>/report_content.json --brand business/brand/brand.yaml --out deliverables/competitor_analysis_<date>.pdf`. If a PDF already exists at that path, confirm with the user before overwriting.
10. **Agent** — Confirm the PDF was created, report its path, and give a short verbal summary of key findings and (if applicable) what changed since the last report.

## Outputs

- `deliverables/competitor_analysis_<YYYY-MM-DD>.pdf` — the deliverable.
- `research/competitors/<slug>/<YYYY-MM-DD>.json` per competitor — durable, used for future diffing. Never delete these.
- `business/profile.yaml` — created or updated if it didn't exist or changed.
- `.tmp/run_<date>/*` — disposable; safe to delete/regenerate.

## Edge cases and known quirks

- **No prior snapshot for a competitor** — omit them from the "changes since last report" section entirely; don't claim "no changes" when there's simply nothing to compare.
- **Brand extraction is ambiguous or incomplete** (e.g. a required color role has no clear hex, or a font name isn't stated) — ask the user; never invent a brand value.
- **Logo has no transparent version** — keep its supplied background as-is (this project's logo ships on a solid black square) and design report sections/backgrounds around that rather than compositing a fake cutout.
- **Unreachable or blocked competitor site** (robots.txt, paywall, heavy JS) — note it in `confidence_notes` for that competitor; don't fabricate figures to fill a gap.
- **Too many plausible competitors** — confirm the shortlist with the user before researching all of them.
- **Same-day rerun** — `snapshot_competitor.py` overwrites the same date file cleanly; re-rendering an existing dated PDF should prompt confirmation first (don't silently overwrite a deliverable).
- **`playwright install chromium` not yet run** — `render_report_pdf.py` will fail with a clear error telling you to run it; this is a one-time setup step separate from `pip install -r requirements.txt` (see the tool's docstring).
- **Recurring/scheduled runs** — out of scope for now. Each run is self-contained (reads whatever exists, writes date-keyed files), so a scheduler can be layered on top later without redesigning this workflow.
