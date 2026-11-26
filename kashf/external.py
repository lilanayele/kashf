"""External validation of the macro layer against independently published reports (REAL data).

data/external_validation.csv lists UAE trade flows that NGO/UN reports name as anomalous (each row
cites its source). This is NOT ground truth for laundering: the reports document smuggling, transit
or mismatched statistics, which may or may not involve money laundering, and many anomalous flows are
undocumented. The test asks a narrower question: does Kashf rank the flows that independent
investigators singled out higher than chance?

Outputs results/external_validation.{json,md}:
  * coverage: documented (partner, HS6, year) keys that exist as eligible mirror pairs
    (a flow whose partner did not report to UN Comtrade cannot be a mirror pair at all);
  * for each method (Kashf rules, Isolation Forest, GFI-style gap, IQR filter): how many documented
    keys are flagged, the rank of their best pair among all eligible pairs, and precision@k
    against the random expectation, both over all pairs and within HS 7108 UAE-import pairs.

    python -m kashf.external
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from kashf import baselines
from kashf.config import load_yaml

log = logging.getLogger("kashf.external")
ROOT = Path(__file__).resolve().parent.parent
KS = (10, 25, 50, 100)


def load_set(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, dtype=str)
    rows = []
    for r in d.itertuples(index=False):
        for hs in r.hs6.split("|"):
            for p in r.partner_iso.split("|"):
                for y in r.years.split("|"):
                    rows.append({"id": r.id, "kind": r.kind, "hs6": hs, "partner_iso": p, "year": int(y),
                                 "direction": r.direction, "source": r.publisher})
    return pd.DataFrame(rows)


def scores(f: pd.DataFrame, cif_fob: float) -> dict[str, np.ndarray]:
    out = {"kashf_rules": f["rule_score"].to_numpy(float), "isolation_forest": f["if_score"].to_numpy(float),
           "gfi_gap": baselines.gfi_gap(f, cif_fob)}
    if "uv_log_q1" in f:
        out["iqr_filter"] = baselines.iqr_filter(f)
    return out


def flags(f: pd.DataFrame, sc: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    k = int(f["rule_flag"].astype(bool).sum())
    out = {"kashf_rules": f["rule_flag"].astype(bool).to_numpy(), "isolation_forest": f["if_flag"].astype(bool).to_numpy(),
           "gfi_gap": baselines.top_k(sc["gfi_gap"], k)}
    if "iqr_filter" in sc:
        out["iqr_filter"] = baselines.top_k(sc["iqr_filter"], k)    # same flag count as the rules
    return out


def rank_desc(s: np.ndarray) -> np.ndarray:
    s = np.nan_to_num(s, nan=-np.inf)
    order = np.argsort(-s, kind="stable")
    r = np.empty(len(s), dtype=int)
    r[order] = np.arange(1, len(s) + 1)
    return r


def evaluate(f: pd.DataFrame, ext: pd.DataFrame, cif_fob: float) -> dict:
    f = f.copy()
    f["hs6"] = f["hs6"].astype(str)
    # one key per (partner, year): a flow named by two sources counts once, under its strongest kind
    order = {"mirror_discrepancy": 0, "transit_hub": 1, "partner_not_reporting": 2}
    ext = ext.assign(_o=ext["kind"].map(order)).sort_values("_o")
    first = ext.drop_duplicates(["partner_iso", "year"])[["partner_iso", "year", "id", "kind"]]
    ext = ext.drop(columns=["id", "kind", "_o"]).merge(first, on=["partner_iso", "year"])
    key = ["hs6", "partner_iso", "year", "direction"]
    m = f.reset_index().merge(ext.drop_duplicates(key), on=key, how="inner")
    doc_rows = np.zeros(len(f), dtype=bool)
    doc_rows[m["index"].unique()] = True
    keys = ext.drop_duplicates(["partner_iso", "year"])
    covered = m.drop_duplicates(["partner_iso", "year"])
    sc = scores(f, cif_fob)
    fl = flags(f, sc)
    gold = (f["hs6"].str.startswith("7108") & (f["direction"] == "uae_import")).to_numpy()
    res = {"label": "REAL (UN Comtrade) pairs vs published reports; NOT ground truth for laundering",
           "eligible_pairs": int(len(f)), "documented_keys": int(len(keys)),
           "documented_keys_in_data": int(len(covered)), "documented_pairs": int(doc_rows.sum()),
           "gold_import_pairs": int(gold.sum()),
           "keys_not_in_data": sorted(set(map(tuple, keys[["partner_iso", "year"]].values.tolist()))
                                      - set(map(tuple, covered[["partner_iso", "year"]].values.tolist()))),
           "by_kind": {}, "methods": {}}
    for kind, g in keys.groupby("kind"):
        res["by_kind"][kind] = {"keys": int(len(g)), "in_data": int((covered["kind"] == kind).sum())}
    for name, s in sc.items():
        r_all = rank_desc(s)
        s_gold = np.where(gold, s, np.nan)
        r_gold = rank_desc(s_gold)
        per_key = []
        for (p, y), g in m.groupby(["partner_iso", "year"]):
            idx = g["index"].to_numpy()
            per_key.append({"id": g["id"].iloc[0], "partner": p, "year": int(y), "kind": g["kind"].iloc[0],
                            "best_rank": int(r_all[idx].min()), "best_rank_in_gold": int(r_gold[idx].min()),
                            "flagged": bool(fl[name][idx].any())})
        pk = pd.DataFrame(per_key)
        prec = {}
        for k in KS:
            top = np.argsort(-np.nan_to_num(s, nan=-np.inf), kind="stable")[:k]
            topg = np.argsort(-np.nan_to_num(s_gold, nan=-np.inf), kind="stable")[:min(k, int(gold.sum()))]
            prec[str(k)] = {"all_pairs": float(doc_rows[top].mean()),
                            "gold_import_pairs": float(doc_rows[topg].mean()) if len(topg) else float("nan")}
        res["methods"][name] = {
            "keys_flagged": int(pk["flagged"].sum()) if len(pk) else 0,
            "keys_flagged_by_kind": pk.groupby("kind")["flagged"].sum().astype(int).to_dict() if len(pk) else {},
            "median_best_rank": float(pk["best_rank"].median()) if len(pk) else float("nan"),
            "median_best_rank_in_gold": float(pk["best_rank_in_gold"].median()) if len(pk) else float("nan"),
            "precision_at_k": prec, "per_key": per_key}
    res["random"] = {"precision_all_pairs": float(doc_rows.mean()),
                     "precision_gold_import_pairs": float(doc_rows[gold].mean()) if gold.any() else float("nan"),
                     "expected_median_best_rank_note": "a random ranking puts a key's best of n pairs near N/(n+1)"}
    return res


def write_md(r: dict, path: Path) -> None:
    L = ["# External validation against published reports (REAL UN Comtrade data)", "",
         "**Not ground truth for laundering.** The documented flows come from NGO reports on gold smuggling and "
         "transit (SWISSAID 2024, 2025; see data/external_validation.csv for every source and page). They are a "
         "small, gold-only, Africa-only set chosen by investigators, not a sample of laundering.", "",
         f"- Eligible mirror pairs: {r['eligible_pairs']:,}; documented (partner, year) keys: {r['documented_keys']}; "
         f"present as eligible pairs: {r['documented_keys_in_data']} ({r['documented_pairs']} pairs over HS 710812/710813).",
         f"- Keys absent from the data (partner did not report, or a side below the value filter): "
         f"{', '.join(f'{p} {y}' for p, y in r['keys_not_in_data'])}.",
         f"- Random precision: {r['random']['precision_all_pairs']:.4f} over all pairs, "
         f"{r['random']['precision_gold_import_pairs']:.3f} within HS 7108 UAE-import pairs ({r['gold_import_pairs']} pairs).", "",
         "| Method | Keys flagged (by kind) | Median best rank (all) | Median best rank (gold imports) | P@10 all | P@25 all | P@10 gold | P@25 gold |",
         "|---|---|---|---|---|---|---|---|"]
    for name, x in r["methods"].items():
        p = x["precision_at_k"]
        kb = x["keys_flagged_by_kind"]
        L.append(f"| {name} | {x['keys_flagged']}/{r['documented_keys_in_data']} "
                 f"(mirror {kb.get('mirror_discrepancy', 0)}/{r['by_kind'].get('mirror_discrepancy', {}).get('in_data', 0)}, "
                 f"transit {kb.get('transit_hub', 0)}/{r['by_kind'].get('transit_hub', {}).get('in_data', 0)}) | {x['median_best_rank']:.0f} | "
                 f"{x['median_best_rank_in_gold']:.0f} | {p['10']['all_pairs']:.2f} | {p['25']['all_pairs']:.2f} | "
                 f"{p['10']['gold_import_pairs']:.2f} | {p['25']['gold_import_pairs']:.2f} |")
    L += ["", "GFI gap and IQR filter flag the same number of pairs as the Kashf rules (top k), so flag counts are comparable.",
          "", "## Per documented key (Kashf rules)", "", "| Source id | Partner | Year | Kind | Best rank (all) | Best rank (gold) | Flagged |",
          "|---|---|---|---|---|---|---|"]
    for k in sorted(r["methods"]["kashf_rules"]["per_key"], key=lambda x: (x["id"], x["partner"], x["year"])):
        L.append(f"| {k['id']} | {k['partner']} | {k['year']} | {k['kind']} | {k['best_rank']} | {k['best_rank_in_gold']} | "
                 f"{'yes' if k['flagged'] else 'no'} |")
    path.write_text("\n".join(L) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="External validation of the macro layer")
    ap.add_argument("--set", default=str(ROOT / "data/external_validation.csv"))
    ap.add_argument("--flags", default=str(ROOT / "results/macro/flags.csv"))
    ap.add_argument("--out", default=str(ROOT / "results"))
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    f = pd.read_csv(a.flags, dtype={"hs6": str})
    r = evaluate(f, load_set(Path(a.set)), float(load_yaml()["macro"]["cif_fob_factor"]))
    out = Path(a.out)
    (out / "external_validation.json").write_text(json.dumps(r, indent=2, default=str))
    write_md(r, out / "external_validation.md")
    log.info("wrote %s", out / "external_validation.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
