# /angel

Angel Tab, served at [jakerheingold.ai/angel](https://jakerheingold.ai/angel) — unlisted (not linked from the homepage).

Jake, Dalton, Michael & Chad cover each other's small checks into deals. This page tracks who put in what, per deal, and each person's running total.

- `template.html` — hand-maintained frontend source (edit this, not `index.html`)
- `data.json` — **hand-maintained**, the actual ledger: people, deals, who checked in for how much, who fronted the money, status, and entry/current valuation. There's no live feed behind this (no sheet, no API) — **whenever a new check goes out, a deal's status changes, or a valuation updates, edit this file directly.**
- `build_model.py` — renders `template.html` + `data.json` into `index.html`
- `index.html` — **generated file**. Don't hand-edit.
- `assets/` — company logos, pulled from each company's own site.

## Updating

```bash
python3 angel/build_model.py
```

No automation/CI for this one — it's manual on purpose, since the data only changes when someone actually writes a check.

## Data shape

Each deal in `data.json`:

```json
{
  "company": "Name",
  "website": "https://...",
  "logo": "assets/name.png",
  "blurb": "One or two sentences on what they do.",
  "date": null,
  "status": "active",
  "entry_valuation": null,
  "current_valuation": null,
  "fronted_by": "Person who wrote the actual check",
  "checks": { "Person": amount, ... }
}
```

`entry_valuation` / `current_valuation` are `null` (shown as "TBD"/"—") until filled in. Update `current_valuation` on a liquidity event (markup, markdown, exit) and flip `status` to `"exited"` if applicable.
