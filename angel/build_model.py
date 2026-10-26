"""
Renders angel/template.html using angel/data.json, writing angel/index.html.

This pipeline has no external data source (no API, no sheet) — it's a hand-maintained
ledger. Whenever a new check goes out, a deal's status changes, or a valuation updates,
edit data.json, then rerun this script.
"""
import json
import os
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    data_path = os.path.join(BASE_DIR, "data.json")
    with open(data_path) as f:
        data = json.load(f)

    data["generated"] = date.today().isoformat()

    template_path = os.path.join(BASE_DIR, "template.html")
    out_path = os.path.join(BASE_DIR, "index.html")
    with open(template_path) as f:
        template = f.read()
    with open(out_path, "w") as f:
        f.write(template.replace("__DATA_JSON__", json.dumps(data)))

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
