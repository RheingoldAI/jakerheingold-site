"""
Echo Chamber Group Parlays — dashboard pipeline.

Reads the group's Google Sheet (link-viewable, no API key needed), computes
every stat itself from the raw weekly Play/Hit-Miss/Category grids (rather
than trusting the sheet's own precomputed leaderboard), and renders the
static dashboard.

Run manually:  python3 parlay_model.py
Run by CI:     invoked on a schedule by .github/workflows/parlay-update.yml
"""
import csv
import io
import json
import os
import re
import sys
from datetime import datetime, timezone

import requests

SHEET_ID = "1nwJgl8U_xwxAhEWTbK1oM7Rm3GVmh-E7QUIyTzAUY8M"
UA = "Mozilla/5.0 (compatible; parlay-dashboard/1.0; +https://jakerheingold.ai/parlay)"

CANONICAL_PEOPLE = ["Smith", "Ben", "Kaiser", "Orlan", "Tuaty", "Tony", "Dilts", "Snake", "Rheingold"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def discover_tabs():
    """Tab name -> gid, scraped from the public htmlview page's bootstrap JS.
    No Sheets API key needed since the sheet is link-viewable."""
    resp = requests.get(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/htmlview",
                         headers={"User-Agent": UA}, timeout=30)
    resp.raise_for_status()
    tabs = {}
    for m in re.finditer(r'name:\s*"([^"]*)",\s*pageUrl:\s*"[^"]*",\s*gid:\s*"(\d+)"', resp.text):
        tabs[m.group(1)] = m.group(2)
    if not tabs:
        raise RuntimeError("Could not find any tabs on the sheet's htmlview page — layout may have changed.")
    return tabs


def fetch_tab_rows(gid):
    resp = requests.get(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}",
                         headers={"User-Agent": UA}, timeout=30)
    resp.raise_for_status()
    return list(csv.reader(io.StringIO(resp.text)))


def normalize_name(raw):
    cleaned = re.sub(r"\$[\d,.]+", "", raw).strip()
    for p in CANONICAL_PEOPLE:
        if cleaned.lower() == p.lower():
            return p
    return cleaned.title()


def parse_dashboard(rows):
    """Earnings/Winnings/All-time-win% tracker tab."""
    earnings_by_year = {}
    winnings_by_year = {}
    win_pct_by_year = {}
    section = None
    people_header = None
    for row in rows:
        first = (row[0] if row else "").strip()
        if first == "Earnings Tracker":
            section = "earnings"; continue
        if first == "Winnings Tracker":
            section = "winnings"; continue
        if first == "All Time Winning %":
            section = "winpct"; continue
        if not first:
            continue
        if section == "earnings" and first == "Year":
            continue
        if section == "earnings" and re.match(r"^\d{4}-\d{4}$", first):
            pct = row[1].strip()
            earn = row[2].strip().replace("$", "").replace(",", "")
            earnings_by_year[first] = {
                "all_time_pct": None if pct in ("-", "") else float(pct.replace("%", "")) / 100,
                "earnings": float(earn) if earn else 0.0,
            }
        if section == "winnings" and first == "Year":
            continue
        if section == "winnings" and re.match(r"^\d{4}-\d{4}$", first):
            def num(v, cast=float):
                v = v.strip().replace("$", "").replace(",", "")
                return cast(v) if v else None
            winnings_by_year[first] = {
                "wager_per": num(row[1]), "bettors": num(row[2], int),
                "risk_per_week": num(row[3]), "weeks": num(row[4], int),
                "total_risk": num(row[5]), "full_hits": num(row[6], int),
                "winnings": num(row[7]) or 0.0,
            }
        if section == "winpct" and first == "Year":
            people_header = [c.strip() for c in row[1:] if c.strip()]
            continue
        if section == "winpct" and people_header and (re.match(r"^\d{4}-\d{4}$", first) or first == "All-Time"):
            vals = {}
            for i, person in enumerate(people_header):
                v = row[1 + i].strip() if 1 + i < len(row) else ""
                if v:
                    vals[person] = float(v.replace("%", "")) / 100
            win_pct_by_year[first] = vals
    return {"earnings_by_year": earnings_by_year, "winnings_by_year": winnings_by_year, "win_pct_by_year": win_pct_by_year}


def parse_analysis_tab(rows):
    """Full per-week Play/Hit-Miss/Category grid -> compute every stat ourselves."""
    header = rows[0]
    people = []
    col_start = {}
    i = 1
    while i < len(header):
        name = header[i].strip()
        if name:
            people.append(name)
            col_start[name] = i
        i += 3

    weekly = []
    for row in rows[2:]:
        first = (row[0] if row else "").strip()
        m = re.match(r"^Week\s+(\d+)$", first, re.I)
        if not m:
            if weekly:
                break
            continue
        week = int(m.group(1))
        picks = []
        for person in people:
            c = col_start[person]
            play = row[c].strip() if c < len(row) else ""
            result = row[c + 1].strip().upper() if c + 1 < len(row) else ""
            category = row[c + 2].strip() if c + 2 < len(row) else ""
            if result not in ("H", "M"):
                continue
            picks.append({"person": person, "play": play, "result": result,
                           "category": category if category and category != "N/A" else None})
        graded = [p for p in picks if p["result"] in ("H", "M")]
        all_hit = len(graded) == len(people) and all(p["result"] == "H" for p in graded)
        weekly.append({"week": week, "picks": picks, "all_hit": all_hit, "fully_graded": len(graded) == len(people)})

    person_stats = {}
    category_stats = {}
    for person in people:
        wins = losses = 0
        cats = {}
        for wk in weekly:
            for p in wk["picks"]:
                if p["person"] != person:
                    continue
                if p["result"] == "H":
                    wins += 1
                else:
                    losses += 1
                if p["category"]:
                    c = cats.setdefault(p["category"], {"wins": 0, "losses": 0})
                    c["wins" if p["result"] == "H" else "losses"] += 1
        total = wins + losses
        mpc = None
        if cats:
            mpc = max(cats.items(), key=lambda kv: kv[1]["wins"] + kv[1]["losses"])[0]
        person_stats[person] = {
            "wins": wins, "losses": losses, "total": total,
            "win_pct": (wins / total) if total else None,
            "categories": cats,
            "mpc": mpc,
            "mpc_count": (cats[mpc]["wins"] + cats[mpc]["losses"]) if mpc else 0,
            "mpc_wins": cats[mpc]["wins"] if mpc else 0,
            "mpc_pct": (cats[mpc]["wins"] / (cats[mpc]["wins"] + cats[mpc]["losses"])) if mpc else None,
        }
        for cat, rec in cats.items():
            agg = category_stats.setdefault(cat, {"wins": 0, "losses": 0})
            agg["wins"] += rec["wins"]
            agg["losses"] += rec["losses"]

    for cat, rec in category_stats.items():
        total = rec["wins"] + rec["losses"]
        rec["total"] = total
        rec["win_pct"] = rec["wins"] / total if total else None

    total_wins = sum(p["wins"] for p in person_stats.values())
    total_losses = sum(p["losses"] for p in person_stats.values())
    full_hit_weeks = sum(1 for wk in weekly if wk["fully_graded"] and wk["all_hit"])
    graded_weeks = sum(1 for wk in weekly if wk["fully_graded"])

    return {
        "people": people, "weekly": weekly, "person_stats": person_stats,
        "category_stats": category_stats,
        "totals": {"wins": total_wins, "losses": total_losses,
                   "win_pct": total_wins / (total_wins + total_losses) if (total_wins + total_losses) else None,
                   "full_hit_weeks": full_hit_weeks, "graded_weeks": graded_weeks},
    }


def parse_raw_picks_tab(rows):
    """Picks-only tab (no grading yet) — week -> who-pays + each person's pick text."""
    week_labels = [c.strip() for c in rows[0][1:] if c.strip().lower().startswith("week")]
    n_weeks = len(week_labels)
    who_pays_row = next((r for r in rows if r and r[0].strip().lower().startswith("who pays")), None)
    who_pays = {}
    if who_pays_row:
        for i in range(n_weeks):
            v = who_pays_row[1 + i].strip() if 1 + i < len(who_pays_row) else ""
            if v:
                who_pays[i + 1] = normalize_name(v)

    picks_start = None
    for idx, row in enumerate(rows):
        if row and row[0].strip().lower() == "picks":
            picks_start = idx + 1
            break

    weekly = [{"week": w, "who_pays": who_pays.get(w), "picks": []} for w in range(1, n_weeks + 1)]
    if picks_start:
        for row in rows[picks_start:]:
            if not row or not row[0].strip():
                continue
            person = normalize_name(row[0])
            if person not in CANONICAL_PEOPLE:
                continue
            for i in range(n_weeks):
                play = row[1 + i].strip() if 1 + i < len(row) else ""
                if play:
                    weekly[i]["picks"].append({"person": person, "play": play})
    weeks_with_picks = sum(1 for w in weekly if w["picks"])
    return {"weekly": weekly, "weeks_logged": weeks_with_picks}


def _norm_tab_name(name):
    return re.sub(r"\s+", "", name).lower()


def build_season(season, tabs):
    """Prefer a rich '{season} Analysis' tab; fall back to a picks-only tab matching
    the season (tolerant of the sheet's inconsistent spacing, e.g. '2025 - 2026')."""
    by_norm = {_norm_tab_name(n): n for n in tabs}
    analysis_key = by_norm.get(_norm_tab_name(f"{season} Analysis"))
    if analysis_key:
        rows = fetch_tab_rows(tabs[analysis_key])
        detail = parse_analysis_tab(rows)
        return {"has_detail": True, **detail}
    raw_key = by_norm.get(_norm_tab_name(season))
    if raw_key:
        rows = fetch_tab_rows(tabs[raw_key])
        raw = parse_raw_picks_tab(rows)
        return {"has_detail": False, **raw}
    return None


def aggregate_all_time(seasons_data):
    """Combine person_stats + category_stats across every season that has rich
    detail — computed fresh each run rather than trusting the sheet's own
    hand-maintained 'All-Time' row, so it updates automatically as seasons complete."""
    person_stats = {p: {"wins": 0, "losses": 0, "categories": {}} for p in CANONICAL_PEOPLE}
    category_stats = {}
    total_wins = total_losses = full_hit_weeks = graded_weeks = 0

    for season in seasons_data.values():
        detail = season.get("detail")
        if not detail or not detail.get("has_detail"):
            # No per-leg breakdown for this season (e.g. 2024-2025, which predates
            # detailed tracking) — but the Dashboard tab still knows whether the
            # full parlay hit that season, so fold that into the all-time count
            # even though we can't attribute it to individual people/categories.
            winnings = season.get("winnings")
            if winnings and winnings.get("full_hits") is not None and winnings.get("weeks"):
                full_hit_weeks += winnings["full_hits"]
                graded_weeks += winnings["weeks"]
            continue
        for person, stats in detail["person_stats"].items():
            ps = person_stats.setdefault(person, {"wins": 0, "losses": 0, "categories": {}})
            ps["wins"] += stats["wins"]
            ps["losses"] += stats["losses"]
            for cat, rec in stats["categories"].items():
                c = ps["categories"].setdefault(cat, {"wins": 0, "losses": 0})
                c["wins"] += rec["wins"]
                c["losses"] += rec["losses"]
        for cat, rec in detail["category_stats"].items():
            agg = category_stats.setdefault(cat, {"wins": 0, "losses": 0})
            agg["wins"] += rec["wins"]
            agg["losses"] += rec["losses"]
        total_wins += detail["totals"]["wins"]
        total_losses += detail["totals"]["losses"]
        full_hit_weeks += detail["totals"]["full_hit_weeks"]
        graded_weeks += detail["totals"]["graded_weeks"]

    for person, ps in person_stats.items():
        total = ps["wins"] + ps["losses"]
        ps["total"] = total
        ps["win_pct"] = ps["wins"] / total if total else None
        mpc = None
        if ps["categories"]:
            mpc = max(ps["categories"].items(), key=lambda kv: kv[1]["wins"] + kv[1]["losses"])[0]
        ps["mpc"] = mpc
        ps["mpc_count"] = (ps["categories"][mpc]["wins"] + ps["categories"][mpc]["losses"]) if mpc else 0
        ps["mpc_wins"] = ps["categories"][mpc]["wins"] if mpc else 0
        ps["mpc_pct"] = (ps["categories"][mpc]["wins"] / ps["mpc_count"]) if mpc and ps["mpc_count"] else None

    for cat, rec in category_stats.items():
        total = rec["wins"] + rec["losses"]
        rec["total"] = total
        rec["win_pct"] = rec["wins"] / total if total else None

    return {
        "person_stats": person_stats,
        "category_stats": category_stats,
        "totals": {"wins": total_wins, "losses": total_losses,
                   "win_pct": total_wins / (total_wins + total_losses) if (total_wins + total_losses) else None,
                   "full_hit_weeks": full_hit_weeks, "graded_weeks": graded_weeks},
    }


def main():
    print("Discovering sheet tabs...", file=sys.stderr)
    tabs = discover_tabs()
    print(f"  found: {list(tabs.keys())}", file=sys.stderr)

    dash_rows = fetch_tab_rows(tabs["Dashboard"])
    dashboard = parse_dashboard(dash_rows)

    seasons_data = {}
    for season in sorted(dashboard["earnings_by_year"].keys()):
        detail = build_season(season, tabs)
        if detail is None and dashboard["earnings_by_year"].get(season, {}).get("earnings") is None:
            continue
        seasons_data[season] = {
            "summary": dashboard["earnings_by_year"].get(season),
            "winnings": dashboard["winnings_by_year"].get(season),
            "win_pct_by_person": dashboard["win_pct_by_year"].get(season, {}),
            "detail": detail,
        }
        print(f"  {season}: {'rich analysis' if detail and detail.get('has_detail') else ('picks only' if detail else 'no tab found')}", file=sys.stderr)

    all_time_earnings = sum(
        (s["summary"]["earnings"] or 0) for s in seasons_data.values() if s["summary"]
    )
    all_time = aggregate_all_time(seasons_data)
    all_time["earnings"] = all_time_earnings

    now = datetime.now(timezone.utc)
    data = {
        "generated": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(),
        "people": CANONICAL_PEOPLE,
        "seasons": seasons_data,
        "all_time": all_time,
    }

    template_path = os.path.join(BASE_DIR, "template.html")
    out_path = os.path.join(BASE_DIR, "index.html")
    with open(template_path) as f:
        template = f.read()
    with open(out_path, "w") as f:
        f.write(template.replace("__DATA_JSON__", json.dumps(data)))
    print(f"Wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
