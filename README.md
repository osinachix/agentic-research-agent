# Agentic Workflow

A project built on the **WAT framework** (Workflows / Agents / Tools — see `CLAUDE.md` for how Claude Code operates in here). This repo currently has one workflow:

## Competitor Analysis (branded PDF)

Give Claude info about your business once, and it will autonomously research your competitors on the web and produce a polished, on-brand PDF report — profiles, a comparison matrix, and concrete recommendations. Full details: [`workflows/competitor_analysis.md`](workflows/competitor_analysis.md).

This is not a standalone script you run yourself — it's driven by Claude Code. You open this project in Claude Code and ask it to run the competitor analysis; Claude reads the workflow SOP and orchestrates everything (web research, calling the Python tools, generating the PDF).

### Requirements

- **Claude Code**, run inside this project folder. Competitor discovery and research use Claude Code's built-in web search/fetch — no third-party search API key needed, nothing to add to `.env` for that part.
- **Python 3.10+** (this project's `.venv` is 3.13, already created — nothing to install there).
- The packages in `requirements.txt` (jinja2, playwright, pyyaml, matplotlib) and the Playwright Chromium browser binary, installed like so:

```
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```
(Already done in this project — re-run only if the venv is rebuilt or `requirements.txt` changes.)

`.env` isn't currently needed for this workflow — it exists per the WAT framework convention in case a future workflow needs API keys, but the competitor-analysis workflow doesn't require any.

### What you need to provide

1. **Your business profile** — tell Claude about your business (what you sell, who it's for, pricing, market) and it saves it to `business/profile.yaml` for reuse on every future run.
2. **Your brand** — drop a logo image and a brand-guidelines file/image anywhere in the project; Claude extracts colors, fonts, and logo rules into `business/brand/brand.yaml` and files the source images under `business/brand/`. Already done for this project (Nuvaix Group).

Then just ask Claude to run the competitor analysis. It handles discovery, research, snapshotting, and PDF rendering itself.

### Where things land

| Path | What it is |
|---|---|
| `business/` | Your business profile + brand config (durable, hand-maintained) |
| `research/competitors/<slug>/<date>.json` | Dated competitor research snapshots (durable — used to detect what changed between reports) |
| `deliverables/` | The final branded PDF(s) |
| `.tmp/` | Disposable per-run scratch files — safe to delete |
| `tools/` | The Python scripts that do the deterministic work (snapshotting, diffing, PDF rendering) |
| `workflows/` | The SOPs Claude follows |
