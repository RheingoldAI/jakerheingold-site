# /survivor

Live NFL Survivor Pool picker, served at [jakerheingold.ai/survivor](https://jakerheingold.ai/survivor).

- `template.html` — hand-maintained frontend source (edit this, not `index.html`)
- `build_model.py` — fetches live nflverse odds + nfelo's power-ratings CSV, computes win probabilities, solves the full-season optimal assignment, renders `index.html` from `template.html`, and writes a `history/` snapshot
- `index.html` — **generated file**, committed automatically by CI. Don't hand-edit.
- `history/` — one JSON snapshot per automated run, plus `index.json` listing them. This is what powers the "History" section on the page.
- `picks.json` — **hand-maintained**, the season's actual official picks: `{"<week>": {"picked": ["TEAM"], "recommended": ["TEAM"]}}`. Baked into every build as `DATA.logged_picks` so a logged pick shows up for anyone who opens the link, not just whoever's browser clicked "Log Pick" (browser local storage alone doesn't persist across devices/visitors). **Whenever a real pick is made, update this file and rerun the pipeline** — that's the only way it becomes visible to other people.

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
