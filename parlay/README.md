# /parlay

Echo Chamber Group Parlays dashboard, served at [jakerheingold.ai/parlay](https://jakerheingold.ai/parlay).

9 friends each add one leg to a shared weekly parlay, tracked in a [Google Sheet](https://docs.google.com/spreadsheets/d/1nwJgl8U_xwxAhEWTbK1oM7Rm3GVmh-E7QUIyTzAUY8M) (link-viewable, no login needed to read it). Picks are still entered there — this page just visualizes it.

- `template.html` — hand-maintained frontend source (edit this, not `index.html`)
- `parlay_model.py` — discovers the sheet's tabs, pulls each season's data, computes every stat itself from the raw weekly grids (not the sheet's own precomputed leaderboard), and renders `index.html`
- `index.html` — **generated file**, committed automatically by CI. Don't hand-edit.

## How it finds seasons

For each year in the **Dashboard** tab's Earnings Tracker, it looks for:
1. A **`"{season} Analysis"`** tab (e.g. `2025-2026 Analysis`) — the rich per-week Play/Hit-Miss/Category grid. If found, every stat (leaderboard, MPC, category win rates, full-parlay-hit weeks) is computed from it.
2. Otherwise, a plain **`"{season}"`** tab with just picks (no grading yet) — shown as picks-logged-but-not-graded.
3. Otherwise, just the Dashboard's summary row (season earnings only) — for seasons like 2024-2025 that predate detailed tracking.

Tab-name matching tolerates the sheet's inconsistent spacing (`"2025 - 2026"` vs `"2026-2027"`).

**When the 2026-2027 season needs detailed stats**, create a `"2026-2027 Analysis"` tab in the same layout as `2025-2026 Analysis` (person blocks of Play/Hit-Miss/Category columns, one row per week) — the pipeline picks it up automatically on the next run, no code change needed.

## Automation

`.github/workflows/parlay-update.yml` re-pulls the sheet and redeploys every Tuesday morning (once Monday Night Football results are in). Run manually:

```bash
pip install -r parlay/requirements.txt
python parlay/parlay_model.py
```

## Source of truth

Also published as a standalone public repo for portfolio purposes: [RheingoldAI/echo-chamber-parlays](https://github.com/RheingoldAI/echo-chamber-parlays) — just a README pointing back here, since this folder is what actually runs.

## Known maintenance risk

The sheet must stay link-viewable ("Anyone with the link — Viewer") for the automation to read it with no auth. `discover_tabs()` scrapes tab names/gids from the public `htmlview` page's bootstrap JS — if Google changes that page's format, tab discovery breaks loudly (raises rather than silently finding nothing).
