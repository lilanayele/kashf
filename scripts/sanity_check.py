"""Sanity-check the real Comtrade outputs before anything is committed or pitched.

    python scripts/sanity_check.py          # exit code 1 if something is clearly broken

Prints row counts, missing quantity/weight shares, mirror-gap distribution and how the real
reference prices compare with the illustrative ones. WARN lines are things to look at and
mention honestly; FAIL lines stop the pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kashf import comtrade, reference  # noqa: E402

fails: list[str] = []
warns: list[str] = []


def main() -> int:
    flows = comtrade.load_raw()
    print("== Cached rows (real, UN Comtrade)")
    cov = flows.groupby(["source", "year"]).agg(rows=("value_usd", "size"),
                                                 reporters=("reporter", "nunique"),
                                                 partners=("partner", "nunique"),
                                                 hs6=("hs6", "nunique"),
                                                 qty_missing=("qty", lambda x: x.isna().mean()),
                                                 wgt_missing=("net_wgt_kg", lambda x: x.isna().mean()))
    print(cov.to_string(float_format=lambda v: f"{v:.0%}" if v <= 1 else f"{v:,.0f}"))
    for src in ("uae", "mirror", "world"):
        if src not in set(flows["source"]):
            fails.append(f"no '{src}' rows cached")
    if (flows["source"] == "uae").any() and flows.loc[flows["source"] == "uae", "net_wgt_kg"].isna().mean() > 0.5:
        warns.append("more than half of UAE-reported rows have no net weight: weight gaps and unit values are thin")

    pairs_f = ROOT / "results" / "macro" / "mirror_pairs.csv"
    if pairs_f.exists():
        p = pd.read_csv(pairs_f, dtype={"hs6": str})
        g = p["mirror_gap"]
        print(f"\n== Mirror pairs (real): {len(p):,}")
        print(f"gap NaN {g.isna().mean():.1%} | exactly 0 {(g == 0).mean():.1%} | median {g.median():+.2f} | "
              f"IQR [{g.quantile(.25):+.2f}, {g.quantile(.75):+.2f}] | |gap| > ln 1.5: {(g.abs() > np.log(1.5)).mean():.1%}")
        print(p.groupby("direction")["mirror_gap"].describe().to_string(float_format=lambda v: f"{v:.2f}"))
        if len(p) == 0 or g.notna().sum() == 0:
            fails.append("mirror gaps are all missing")
        elif (g.dropna() == 0).all():
            fails.append("mirror gaps are all exactly zero (join or units bug)")
        if g.median() < -0.7 or g.median() > 0.7:
            warns.append(f"median mirror gap {g.median():+.2f} is large: systematic reporting difference "
                         "(re-exports or origin attribution), not misinvoicing; say so in the pitch")
    else:
        fails.append("results/macro/mirror_pairs.csv missing: run python -m kashf.macro")

    ref_f = ROOT / "data" / "reference_comtrade_detail.csv"
    if ref_f.exists():
        real = pd.read_csv(ref_f, dtype={"hs6": str}).set_index("hs6")
        ill = reference.default_table().set_index("hs6")
        cmp = real[["description", "unit", "ref_usd", "log_mad", "n_reporter_years"]].join(
            ill[["unit", "ref_usd"]].rename(columns={"unit": "unit_illus", "ref_usd": "illus_usd"}))
        cmp["real/illus"] = cmp["ref_usd"] / cmp["illus_usd"]
        print("\n== Reference prices: real (UN Comtrade) vs illustrative")
        print(cmp.to_string(float_format=lambda v: f"{v:,.2f}"))
        odd = cmp[(cmp["real/illus"] > 10) | (cmp["real/illus"] < 0.1)]
        for hs, r in odd.iterrows():
            warns.append(f"HS {hs} {r['description']}: real median ${r['ref_usd']:,.2f}/{r['unit']} is "
                         f"{r['real/illus']:.1f}x the illustrative value; check the quantity unit")
        changed = cmp[cmp["unit"] != cmp["unit_illus"]]
        for hs, r in changed.iterrows():
            warns.append(f"HS {hs}: Comtrade prices it per {r['unit']}, the illustrative table per {r['unit_illus']}")
        missing = sorted(set(ill.index) - set(real.index))
        if missing:
            warns.append(f"no real reference for {missing}: left out (not filled with illustrative values)")
    else:
        fails.append("data/reference_comtrade_detail.csv missing: run python -m kashf.comtrade reference")

    print()
    for w in warns:
        print("WARN", w)
    for f in fails:
        print("FAIL", f)
    print("sanity check:", "FAILED" if fails else "passed" + (f" with {len(warns)} warning(s)" if warns else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
