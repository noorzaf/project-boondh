"""
Turn the private field spreadsheet into the anonymised dataset published in data/.

The raw sheet holds children's and parents' names, phone numbers, household income,
and family illness details. None of that is published. This script keeps only:
  - a random sample ID
  - the site (school replaced by a neutral label)
  - whether the household reported a water-related illness (yes / no / unknown)
  - the 14 test-strip readings, cleaned into numbers

The mapping from school name to site label lives in private/sites.json (not committed),
as a JSON object such as {"<school name in the raw sheet>": "A", ...}.

Usage:
    python anonymise.py path/to/private_raw.csv ../data/readings.csv
"""
import csv
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "..", "private", "sites.json")) as f:
    SITES = json.load(f)

READINGS = [
    "free_chlorine", "ph", "total_alkalinity", "hardness", "iron", "copper", "lead",
    "nitrate", "nitrite", "bromine", "total_chlorine", "chromium", "fluoride", "cyanuric_acid",
]

NO_ILLNESS = {"", "-", "none", "no", "nil", "n/a"}


def parse_reading(cell):
    """Return (low, high) for a strip reading.

    Entries are a single value ("20"), a range when the colour fell between two
    pads ("30 - 50"), or carry a stray "-" from the sheet layout ("- 100").
    Blank or unreadable cells return (None, None).
    """
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", cell or "")]
    if not nums:
        return None, None
    return min(nums), max(nums)


def main(src, dst):
    with open(src, newline="") as f:
        rows = list(csv.DictReader(f))

    random.seed(2026)          # IDs are random but reproducible
    random.shuffle(rows)       # so row order can't be matched back to the sheet

    out = []
    for i, r in enumerate(rows, 1):
        ill = (r.get("illmember") or "").strip().lower()
        rec = {
            "sample_id": f"S{i:02d}",
            "site": SITES.get(r["school"], "unknown"),
            "household_reports_illness": "unknown" if ill == "" else ("no" if ill in NO_ILLNESS else "yes"),
        }
        for k in READINGS:
            lo, hi = parse_reading(r.get(k))
            rec[f"{k}_low"] = "" if lo is None else lo
            rec[f"{k}_high"] = "" if hi is None else hi
        out.append(rec)

    out.sort(key=lambda d: (d["site"], d["sample_id"]))
    with open(dst, "w", newline="") as f:
        w = csv.DictWriter(f, list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)} samples written to {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
