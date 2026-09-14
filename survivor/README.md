# /survivor

Live NFL Survivor Pool picker, served at [jakerheingold.ai/survivor](https://jakerheingold.ai/survivor).

- `template.html` — hand-maintained frontend source (edit this, not `index.html`)
- `build_model.py` — fetches live nflverse odds + scrapes nfelo power ratings, computes win probabilities, solves the full-season optimal assignment, renders `index.html` from `template.html`, and writes a `history/` snapshot
- `index.html` — **generated file**, committed automatically by CI. Don't hand-edit.
- `history/` — one JSON snapshot per automated run, plus `index.json` listing them. This is what powers the "History" section on the page.

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

The nfelo scrape in `build_model.py` (`fetch_nfelo_ratings`) parses their power-ratings HTML table by structure, since they have no public API. If nfeloapp.com redesigns that page, the scrape will start failing loudly (it raises rather than silently returning bad data) and will need a quick update to match their new markup.
