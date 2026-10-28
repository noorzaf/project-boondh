"""
Compare each test-strip reading with WHO drinking-water guideline values, and check
whether the strip is sensitive enough to tell safe water from unsafe at that limit.

Reads ../data/readings.csv and writes:
    ../results/summary.md          table of results, overall and by site
    ../results/exceedances.png     chart of the share of samples above each limit

Usage:
    python analyse.py
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "readings.csv")
OUT = os.path.join(HERE, "..", "results")

# Health-based limits for drinking water, mg/L (WHO Guidelines for Drinking-water
# Quality, 4th ed.). "smallest_step" is the lowest non-zero colour pad on the
# Vansful 14-in-1 strip, i.e. the smallest amount the strip can report.
CHECKS = [
    # key,        label,                     rule,   limit, smallest_step
    ("lead",      "Lead",                    "above", 0.01,  20),
    ("chromium",  "Chromium",                "above", 0.05,  2),
    ("fluoride",  "Fluoride",                "above", 1.5,   25),
    ("copper",    "Copper",                  "above", 2.0,   1),
    ("nitrite",   "Nitrite",                 "above", 3.0,   1),
    ("nitrate",   "Nitrate",                 "above", 50.0,  10),
    ("free_chlorine", "No chlorine residual", "below", 0.2,  0.5),
    ("ph",        "pH outside 6.5-8.5",      "range", (6.5, 8.5), 0.5),
]


def load():
    with open(DATA, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in list(r):
            if k.endswith(("_low", "_high")):
                r[k] = float(r[k]) if r[k] != "" else None
    return rows


def flagged(r, key, rule, limit):
    """True / False / None (no reading). Uses the conservative end of a range."""
    lo, hi = r[f"{key}_low"], r[f"{key}_high"]
    if lo is None:
        return None
    if rule == "above":
        return lo > limit
    if rule == "below":
        return hi < limit
    return lo < limit[0] or hi > limit[1]


def resolvable(rule, limit, step):
    """Can the strip distinguish a sample at the limit from one above it?"""
    if rule == "above":
        return step <= limit
    return True


def summarise(rows):
    sites = sorted({r["site"] for r in rows})
    table = []
    for key, label, rule, limit, step in CHECKS:
        vals = [flagged(r, key, rule, limit) for r in rows]
        n = sum(v is not None for v in vals)
        k = sum(bool(v) for v in vals)
        by_site = {}
        for s in sites:
            sv = [flagged(r, key, rule, limit) for r in rows if r["site"] == s]
            sn = sum(v is not None for v in sv)
            by_site[s] = (sum(bool(v) for v in sv), sn)
        table.append(dict(key=key, label=label, rule=rule, limit=limit, step=step,
                          n=n, k=k, pct=100 * k / n if n else 0,
                          ok=resolvable(rule, limit, step), by_site=by_site))
    return sites, table


def fmt_limit(t):
    if t["rule"] == "range":
        return f"{t['limit'][0]}–{t['limit'][1]}"
    sign = ">" if t["rule"] == "above" else "<"
    return f"{sign} {t['limit']} mg/L"


def write_markdown(rows, sites, table):
    ill = sum(r["household_reports_illness"] == "yes" for r in rows)
    lines = [
        "# Results",
        "",
        f"{len(rows)} household water samples from {len(sites)} school sites in Gilgit. "
        f"{ill} households reported a family member with a water-related illness.",
        "",
        "| Check | WHO limit | Smallest strip step | Strip can resolve limit? | Samples flagged |"
        + "".join(f" {s} |" for s in sites),
        "|---|---|---|---|---|" + "---|" * len(sites),
    ]
    for t in table:
        step = t["step"] if t["rule"] == "above" else "—"
        ok = "yes" if t["ok"] else f"no ({t['step'] / t['limit']:.0f}× too coarse)"
        site_cells = "".join(f" {k}/{n} |" for k, n in t["by_site"].values())
        lines.append(f"| {t['label']} | {fmt_limit(t)} | {step} | {ok} | "
                     f"{t['k']}/{t['n']} ({t['pct']:.0f}%) |{site_cells}")
    lines += [
        "",
        "Ranges recorded between two colour pads are judged on their lower value, so a",
        "sample is only flagged when even the most favourable reading is past the limit.",
        "",
        "Where the strip cannot resolve a limit, a reading of 0 does not show the water is",
        "safe, and a non-zero reading is a strong signal that needs laboratory confirmation.",
    ]
    with open(os.path.join(OUT, "summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def plot(table):
    surface, ink, ink2 = "#fcfcfb", "#0b0b0b", "#52514e"
    blue = "#2a78d6"
    order = sorted(table, key=lambda t: t["pct"])
    labels = [t["label"] for t in order]
    pcts = [t["pct"] for t in order]

    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=200)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)

    bars = ax.barh(labels, pcts, height=0.6, color=blue, edgecolor=surface, linewidth=2)
    for b, t in zip(bars, order):
        if not t["ok"]:
            b.set_hatch("////")
            b.set_facecolor("#a9c9ef")
            b.set_edgecolor(blue)
            b.set_linewidth(0.8)
        note = "" if t["ok"] else "   strip can't resolve limit"
        ax.text(b.get_width() + 1.2, b.get_y() + b.get_height() / 2,
                f"{t['k']}/{t['n']}{note}", va="center", fontsize=8.5, color=ink2)

    ax.set_xlim(0, 115)
    ax.set_xlabel("Share of samples past the WHO limit (%)", color=ink2, fontsize=9)
    ax.set_title("Gilgit household water: samples flagged by test strip",
                 loc="left", color=ink, fontsize=11, pad=12)
    ax.tick_params(colors=ink2, labelsize=9, length=0)
    ax.xaxis.grid(True, color="#e6e5e1", linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "exceedances.png"), facecolor=surface)


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = load()
    sites, table = summarise(rows)
    write_markdown(rows, sites, table)
    plot(table)
    for t in table:
        print(f"{t['label']:<22} {t['k']:>2}/{t['n']}  resolvable={t['ok']}")


if __name__ == "__main__":
    main()
