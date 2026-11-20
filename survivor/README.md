# /survivor

Live NFL Survivor Pool picker, served at [jakerheingold.ai/survivor](https://jakerheingold.ai/survivor).

- `template.html` — hand-maintained frontend source (edit this, not `index.html`)
- `build_model.py` — fetches live nflverse odds + nfelo's power-ratings CSV, computes win probabilities, solves the full-season optimal assignment, renders `index.html` from `template.html`, and writes a `history/` snapshot
- `index.html` — **generated file**, committed automatically by CI. Don't hand-edit.
- `history/` — one JSON snapshot per automated run, plus `index.json` listing them. This is what powers the "History" section on the page.
- `picks.json` — the **seed / fallback** copy of the season's official picks: `{"<week>": {"picked": ["TEAM"], "recommended": ["TEAM"]}}`. The live copy lives in the shared store below; this file is only used before the first save and if that store can't be reached.

## Shared picks (cross-device)

Official picks are stored in Vercel Blob behind `api/survivor-picks.js` (at the repo root, so it serves at `/api/survivor-picks`):

- `GET /api/survivor-picks` → `{picks, updatedAt, source}`. Public, never cached. The page calls it on every load, so every device and visitor sees the same picks.
- `POST /api/survivor-picks` with `{picks}` and header `x-survivor-passcode` → saves for everyone. The page's Log Pick / Undo / Erase buttons do this; the page asks for the passcode once per device.
- The passcode is the `SURVIVOR_EDIT_PASSCODE` environment variable in the Vercel project. Without it, the endpoint is read-only.
- Each save is a new blob; the last 50 versions are kept, so a bad save can be rolled back from the Vercel Blob dashboard by deleting the newest version.
- `build_model.py` reads the same endpoint, so the Thursday/Saturday runs and history snapshots reflect the real picks.

Picks are no longer kept in browser local storage at all — that's what used to make picks differ between devices and "reset" on reload.

## Automation

`.github/workflows/survivor-update.yml` runs this pipeline automatically Thursday and Saturday mornings (see the workflow file for exact cron times) and pushes the result straight to `main`, which Vercel then redeploys.

To run it manually (e.g. after editing `template.html` or `build_model.py`):

```bash
pip install -r survivor/requirements.txt
python survivor/build_model.py
```

Or trigger the GitHub Actions workflow manually from the Actions tab (`workflow_dispatch`).

## Source of truth

The full project (concept writeup, same source files) is also published as a standalone public repo: [RheingoldAI/survivor-pool](https://github.com/RheingoldAI/survivor-pool). That repo is for portfolio/documentation purposes — this folder is what actually runs.

## Known maintenance risk

`fetch_nfelo_ratings()` in `build_model.py` pulls nfelo's own automated CSV output (`github.com/greerreNFL/nfelo`) rather than scraping their website, and validates the `season` column matches `SEASON` before using it — if their feed ever falls behind (as their public site did at the start of the 2026 season) or the CSV format changes, it fails loudly instead of silently computing on stale or malformed data.
