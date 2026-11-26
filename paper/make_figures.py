"""Paper figures, generated from results files only (300 dpi, grayscale-readable).

    python paper/make_figures.py          # writes paper/figures/*.png

Every figure reads a file under results/ (or the cached mirror pairs) and never types a number.
Grayscale readability: series differ by marker, line style and hatch, not only by colour.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "paper" / "figures"
DPI = 300
plt.rcParams.update({"font.size": 8, "font.family": "serif", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25,
                     "savefig.dpi": DPI, "savefig.bbox": "tight"})
K, G1, G2 = "#111111", "#666666", "#AAAAAA"


def js(p: str) -> dict:
    return json.loads((ROOT / p).read_text())


def architecture() -> None:
    """Two-layer architecture (drawn, no data)."""
    fig, ax = plt.subplots(figsize=(3.4, 2.7))
    ax.set_axis_off()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)

    def box(x, y, w, h, text, fill="white", bold=False):
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=fill, edgecolor=K, lw=0.8))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=6.3,
                fontweight="bold" if bold else "normal", wrap=True)

    def arrow(x1, y1, x2, y2):
        ax.annotate("", (x2, y2), (x1, y1), arrowprops=dict(arrowstyle="-|>", lw=0.7, color=K))

    ax.text(0.1, 9.6, "Macro layer (real UN Comtrade)", fontsize=6.8, fontweight="bold")
    box(0.1, 7.6, 3.0, 1.6, "UAE reports\n(X, RX, M, RM)")
    box(3.5, 7.6, 3.0, 1.6, "Partner mirror\nreports (M, X)")
    box(6.9, 7.6, 3.0, 1.6, "World exports\n(unit values)")
    box(1.5, 5.6, 7.0, 1.3, "Mirror gap, weight gap, unit-value z;\npeer baseline per HS6 x direction", "#EEEEEE")
    for x in (1.6, 5.0, 8.4):
        arrow(x, 7.6, x if x == 5.0 else (3.0 if x < 5 else 7.0), 6.9)
    ax.text(2.6, 4.85, "Invoice layer (trader's own records)", fontsize=6.8, fontweight="bold")
    box(0.1, 3.0, 2.3, 1.5, "Price\nbenchmark")
    box(2.55, 3.0, 2.3, 1.5, "Document\nconsistency")
    box(5.0, 3.0, 2.3, 1.5, "Counterparty\ngraph")
    box(7.45, 3.0, 2.45, 1.5, "Route\n(FATF lists)")
    box(1.5, 1.1, 7.0, 1.3, "Calibrated noisy-OR score; alerts with evidence", "#DDDDDD", True)
    for x in (1.25, 3.7, 6.15, 8.65):
        arrow(x, 3.0, min(max(x, 2.0), 8.0), 2.4)
    ax.annotate("", (1.25, 4.5), (1.5, 5.6), arrowprops=dict(arrowstyle="-|>", lw=0.7, color=K, ls="--"))
    ax.text(0.15, 5.25, "real reference\nprices", fontsize=5.2, color=G1, ha="left", va="center")
    box(3.0, 0.0, 4.0, 0.75, "Analyst decides", bold=True)
    arrow(5.0, 1.1, 5.0, 0.75)
    fig.savefig(OUT / "fig_architecture.png")
    plt.close(fig)


def mirror_gaps() -> None:
    """Distribution of real mirror gaps by direction, UAE exports with and without re-exports."""
    f = ROOT / "results" / "macro" / "flags.csv"
    p = pd.read_csv(f, dtype={"hs6": str})
    fig, ax = plt.subplots(figsize=(3.4, 2.2))
    bins = np.linspace(-8, 8, 65)
    imp = p.loc[p["direction"] == "uae_import", "mirror_gap"].dropna()
    exp_ = p.loc[p["direction"] == "uae_export", "mirror_gap"].dropna()
    exp_x = p.loc[p["direction"] == "uae_export", "mirror_gap_x_only"].dropna() if "mirror_gap_x_only" in p else None
    ax.hist(imp, bins=bins, histtype="step", color=K, lw=1.1, label=f"UAE imports (n={len(imp):,})")
    ax.hist(exp_, bins=bins, histtype="stepfilled", color=G2, alpha=0.7, hatch="///", edgecolor=G1,
            label=f"UAE exports, X+RX (n={len(exp_):,})")
    if exp_x is not None:
        ax.hist(exp_x, bins=bins, histtype="step", color=G1, lw=1.0, ls="--", label=f"UAE exports, X only (n={len(exp_x):,})")
    ax.axvline(0, color=K, lw=0.6)
    ax.set_xlabel("Mirror gap  log(importer / (1.10 x exporter))")
    ax.set_ylabel("Eligible pairs")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.45)
    ax.legend(frameon=True, framealpha=0.9, edgecolor="none", fontsize=5.8, loc="upper left")
    fig.savefig(OUT / "fig_mirror_gaps.png")
    plt.close(fig)


def injection() -> None:
    s = pd.DataFrame(js("results/macro/macro_summary.json")["injection"])
    fig, ax = plt.subplots(figsize=(3.4, 2.2))
    for m, mk, ls, lab in (("rules", "o", "-", "Rules (peer baseline)"), ("iforest", "s", "--", "Isolation Forest")):
        d = s[s["method"] == m].sort_values("size")
        ax.plot(1 + d["size"], d["recall_on_unflagged"], marker=mk, ls=ls, color=K, ms=3.5, lw=1, label=lab)
    ax.set_xscale("log")
    ax.set_xticks([1.1, 1.5, 2, 3, 5, 10])
    ax.set_xticklabels(["1.1", "1.5", "2", "3", "5", "10"])
    ax.minorticks_off()
    ax.set_xlabel("Injected distortion factor of importer value (x or ÷)")
    ax.set_ylabel("Recall (pairs not already flagged)")
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, fontsize=6.5)
    fig.savefig(OUT / "fig_injection.png")
    plt.close(fig)


def synthetic_f1() -> None:
    C = js("results/summary.json")["configs"]
    order = ["kashf_full", "kashf_heuristic", "minus_price", "minus_route", "minus_documents", "minus_graph",
             "price_only", "isolation_forest", "checklist"]
    labels = ["Kashf", "hand-set", "-price", "-route", "-docs", "-graph", "price only", "iForest", "checklist"]
    hatch = ["", "..", "//", "//", "//", "//", "xx", "xx", "xx"]
    shade = [K, G1, G2, G2, G2, G2, "white", "white", "white"]
    fig, ax = plt.subplots(figsize=(3.4, 2.1))
    v = [C[c]["f1"]["mean"] for c in order]
    e = [C[c]["f1"]["sd"] for c in order]
    ax.bar(range(len(order)), v, yerr=e, color=shade, edgecolor=K, hatch=hatch, lw=0.6, capsize=2)
    for i, x in enumerate(v):
        ax.text(i, x + 0.03, f"{x:.2f}", ha="center", fontsize=5.8)
    ax.set_xticks(range(len(order)), labels, rotation=35, ha="right")
    ax.set_ylabel("F1 (held-out seeds)")
    ax.set_ylim(0, 1.05)
    fig.savefig(OUT / "fig_synthetic_f1.png")
    plt.close(fig)


def typology() -> None:
    C = js("results/summary.json")["configs"]
    typ = list(C["kashf_full"]["recall_by_typology"])
    cfg = [("kashf_full", K, ""), ("price_only", G2, "//"), ("isolation_forest", "white", "xx"), ("checklist", "white", "..")]
    fig, ax = plt.subplots(figsize=(3.4, 2.2))
    x = np.arange(len(typ))
    w = 0.2
    for i, (c, col, h) in enumerate(cfg):
        ax.bar(x + (i - 1.5) * w, [C[c]["recall_by_typology"][t]["mean"] for t in typ], w, color=col,
               edgecolor=K, hatch=h, lw=0.5, label=c.replace("_", " ").replace("kashf full", "Kashf"))
    ax.set_xticks(x, [t.replace("_", " ") for t in typ], fontsize=5.5, rotation=30, ha="right")
    ax.set_ylabel("Recall")
    ax.set_ylim(0, 1.15)
    ax.legend(frameon=False, ncol=4, fontsize=5.5, loc="upper center")
    fig.savefig(OUT / "fig_typology.png")
    plt.close(fig)


def robustness() -> None:
    r = js("results/robustness.json")
    thr = r["alert_threshold"]
    t = sorted(thr, key=float)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(3.4, 1.9), gridspec_kw={"width_ratios": [1.4, 1]})
    for k, mk, ls, lab in (("precision", "o", "-", "precision"), ("recall", "s", "--", "recall"),
                           ("f1", "^", ":", "F1")):
        a1.plot([float(x) for x in t], [thr[x][k]["mean"] for x in t], marker=mk, ls=ls, color=K, ms=3, lw=0.9, label=lab)
    a1.set_xlabel("Alert threshold")
    a1.set_ylabel("Score")
    a1.set_ylim(0.5, 1)
    a1.legend(frameon=False, fontsize=5.5)
    s = r["shift"]
    vals = [s["same_generator"]["f1"]["mean"], s["shifted_generator"]["f1"]["mean"]]
    a2.bar([0, 1], vals, color=[K, "white"], edgecolor=K, hatch=["", "//"], lw=0.6,
           yerr=[s["same_generator"]["f1"]["sd"], s["shifted_generator"]["f1"]["sd"]], capsize=2)
    for i, v in enumerate(vals):
        a2.text(i, v + 0.03, f"{v:.2f}", ha="center", fontsize=6)
    a2.set_xticks([0, 1], ["same\ngenerator", "shifted\ngenerator"], fontsize=6)
    a2.set_ylabel("F1")
    a2.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(OUT / "fig_robustness.png")
    plt.close(fig)


def screen_crops() -> None:
    """Crop the Playwright screenshots (paper/figures/screens/, 1600x1000 at 2x) to the panel each figure shows."""
    from PIL import Image
    S = OUT / "screens"
    if not S.exists():
        return
    crops = {  # file: (left, top, right, bottom) as fractions of the image
        "alerts": (0.0, 0.0, 0.55, 0.62),          # header, stats and alert list
        "evidence": (0.545, 0.17, 1.0, 0.62),      # one alert's evidence panel
        "network": (0.545, 0.58, 1.0, 1.0),        # counterparty network around the seller
        "macro_diamonds": (0.09, 0.075, 0.915, 0.60),  # Macro view chart and the 2020-2021 flags
    }
    for name, (l, t, r, b) in crops.items():
        f = S / f"{name}.png"
        if f.exists():
            im = Image.open(f)
            w, h = im.size
            im.crop((int(l * w), int(t * h), int(r * w), int(b * h))).save(OUT / f"screen_{name}.png", dpi=(DPI, DPI))


def derived_stats() -> None:
    """Counts the paper needs that are not stored in macro_summary.json, computed from results/macro/flags.csv."""
    import json
    f = pd.read_csv(ROOT / "results/macro/flags.csv")
    fl = f[f["rule_flag"].astype(bool)]
    out = {
        "_source": "results/macro/flags.csv (computed by paper/make_figures.py derived_stats)",
        "eligible": int(len(f)),
        "rule_flags": int(len(fl)),
        "if_flags": int(f["if_flag"].astype(bool).sum()),
        "both_flags": int((f["rule_flag"].astype(bool) & f["if_flag"].astype(bool)).sum()),
        "reason_value_gap": int((fl["r_gap"] >= 1).sum()),
        "reason_weight_gap": int((fl["r_wgt"] >= 1).sum()),
        "reason_unit_value": int((fl["r_uv"] >= 1).sum()),
        "flag_rate_by_direction": {k: float(v) for k, v in f.groupby("direction")["rule_flag"].mean().items()},
        "pairs_by_direction": {k: int(v) for k, v in f.groupby("direction").size().items()},
        "flag_rate_by_year": {str(k): float(v) for k, v in f.groupby("year")["rule_flag"].mean().items()},
        "top_hs6_by_flags": [[str(k), int(v)] for k, v in fl["hs6"].astype(str).value_counts().head(5).items()],
    }
    (OUT / "derived_stats.json").write_text(json.dumps(out, indent=1))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in (architecture, mirror_gaps, injection, synthetic_f1, typology, robustness, screen_crops, derived_stats):
        f()
        print("wrote", f.__name__)


if __name__ == "__main__":
    sys.exit(main())
