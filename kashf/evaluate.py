"""Evaluation protocol (used for the paper).

* Seed 0 = tuning set: each configuration's alert threshold is chosen there to maximise F1.
* Seeds 1..N = held-out test sets: thresholds are frozen; we report mean ± sd.
* Configurations
      kashf_full                 all four detectors
      minus_<detector>           ablations, one detector removed
      price_only                 price benchmark alone (the classic TBML method)
      checklist                  a manual-review checklist encoded as rules (no tuning, binary)
      isolation_forest           unsupervised ML on per-invoice features (threshold tuned on seed 0)
* Metrics: precision, recall, F1, false-alarm rate (FAR), alerts per 1,000 invoices,
  average precision (threshold-free), recall per typology, and evidence attribution
  (share of true alerts whose evidence names the mechanism actually planted).

    python -m kashf.evaluate --seeds 5 --n 20000
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, precision_recall_curve

from dataclasses import replace

from kashf import calibrate, reference
from kashf.config import Settings
from kashf.detectors import run_all
from kashf.generate import Config, generate
from kashf.scoring import score_invoices

log = logging.getLogger("kashf.evaluate")

DETECTORS = ("price", "route", "documents", "graph")
TYPOLOGIES = ("over_invoicing", "under_invoicing", "phantom_shipment", "multiple_invoicing",
              "misdescription", "circular_trading", "shell_cluster")
# rules whose evidence correctly describes each planted mechanism
EXPECTED = {
    "over_invoicing": {"over_priced"}, "under_invoicing": {"under_priced"},
    "phantom_shipment": {"no_transport_doc", "implausible_dates", "unknown_vessel", "weight_mismatch"},
    "multiple_invoicing": {"doc_reused"},
    "misdescription": {"over_priced", "under_priced", "implausible_unit_weight"},
    "circular_trading": {"circular_trade"}, "shell_cluster": {"linked_parties", "linked_cluster"},
}


# ------------------------------------------------------------------ baselines
def checklist_scores(t: dict, ref: pd.DataFrame, s: Settings) -> pd.Series:
    """What a reviewer with a checklist does: price outside 0.5-2x a known price, missing shipping
    document, high-risk counterparty, quantity mismatch over 5%. Any hit = alert (score 1)."""
    inv = t["invoices"].merge(ref[["hs6", "ref_usd"]], on="hs6", how="left")
    docs = t["transport_docs"].set_index("doc_no")
    ratio = inv["unit_price_usd"] / inv["ref_usd"]
    hit = (ratio > 2) | (ratio < 0.5)
    hit |= ~inv["doc_no"].isin(docs.index)
    hit |= inv["origin"].isin(s.high_risk) | inv["destination"].isin(s.high_risk)
    dq = inv["doc_no"].map(docs["quantity"])
    hit |= ((dq - inv["quantity"]).abs() / inv["quantity"]) > 0.05
    return pd.Series(hit.astype(float).values, index=inv["invoice_no"])


def features(t: dict, ref: pd.DataFrame, s: Settings) -> pd.DataFrame:
    inv = t["invoices"].merge(ref[["hs6", "ref_usd", "kg_per_unit", "unit"]], on="hs6", how="left",
                              suffixes=("", "_ref"))
    docs = t["transport_docs"].set_index("doc_no")
    f = pd.DataFrame(index=inv["invoice_no"])
    f["log_price_ratio"] = np.log(inv["unit_price_usd"] / inv["ref_usd"]).values
    kpu = np.where(inv["unit_ref"] == "unit", inv["declared_weight_kg"] / inv["quantity"] / inv["kg_per_unit"], 1.0)
    f["log_unit_weight_ratio"] = np.log(np.clip(kpu, 1e-6, None))
    f["doc_missing"] = (~inv["doc_no"].isin(docs.index)).astype(float).values
    dq = inv["doc_no"].map(docs["quantity"]).fillna(inv["quantity"])
    dw = inv["doc_no"].map(docs["gross_weight_kg"]).fillna(inv["declared_weight_kg"])
    f["qty_gap"] = ((dq - inv["quantity"]).abs() / inv["quantity"]).values
    f["weight_gap"] = ((dw - inv["declared_weight_kg"]).abs() / inv["declared_weight_kg"]).values
    f["legs"] = inv["route"].str.count(">").values
    f["high_risk"] = (inv["origin"].isin(s.high_risk) | inv["destination"].isin(s.high_risk)).astype(float).values
    f["log_value"] = np.log1p(inv["value_usd"]).values
    return f


def iforest_scores(t: dict, ref: pd.DataFrame, s: Settings, seed: int) -> pd.Series:
    X = features(t, ref, s)
    m = IsolationForest(n_estimators=300, random_state=seed).fit(X.values)
    return pd.Series(-m.score_samples(X.values), index=X.index)


# ------------------------------------------------------------------ helpers
def kashf_scores(t: dict, sig: pd.DataFrame, s: Settings, keep: tuple[str, ...]) -> pd.Series:
    """Scores from the chosen detectors only (ablations reuse one detector run)."""
    sc = score_invoices(t["invoices"], sig[sig["detector"].isin(keep)], s)
    return sc.set_index("invoice_no")["score"]


def best_threshold(y: np.ndarray, score: np.ndarray) -> float:
    p, r, th = precision_recall_curve(y, score)
    f1 = np.where(p + r > 0, 2 * p * r / (p + r + 1e-12), 0)[:-1]
    return float(th[int(np.argmax(f1))]) if len(th) else 0.5


def metrics(y: pd.Series, score: pd.Series, thr: float, typ: pd.Series, sig: pd.DataFrame | None) -> dict:
    score = score.reindex(y.index).fillna(0.0)
    a = score >= thr
    pos = y.astype(bool)
    tp, fp, fn = int((a & pos).sum()), int((a & ~pos).sum()), int((~a & pos).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    out = {"precision": prec, "recall": rec, "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
           "far": fp / int((~pos).sum()), "alerts_per_1000": 1000 * int(a.sum()) / len(y),
           "avg_precision": float(average_precision_score(pos, score)),
           "recall_by_typology": {k: float(a[typ == k].mean()) for k in TYPOLOGIES if (typ == k).any()}}
    if sig is not None:
        rules = sig.groupby("invoice_no")["rule"].apply(set)
        tp_ids = y.index[a & pos]
        ok = [bool(rules.get(i, set()) & EXPECTED[typ[i]]) for i in tp_ids]
        out["evidence_attribution"] = float(np.mean(ok)) if ok else 0.0
    return out


def mispricing_curve(t: dict, ref: pd.DataFrame, score: pd.Series, thr: float, typ: pd.Series) -> pd.DataFrame:
    """Recall of over/under-invoicing as a function of how far the price was pushed from the benchmark."""
    inv = t["invoices"].merge(ref[["hs6", "ref_usd"]], on="hs6").set_index("invoice_no")
    m = typ[typ.isin(["over_invoicing", "under_invoicing"])].index
    d = pd.DataFrame({"factor": np.exp(np.abs(np.log(inv.loc[m, "unit_price_usd"] / inv.loc[m, "ref_usd"]))),
                      "hit": (score.reindex(m).fillna(0) >= thr).values, "typology": typ[m].values}, index=m)
    bins = [1, 1.5, 2, 3, 4, 6, 10, 1e9]
    d["bin"] = pd.cut(d["factor"], bins, labels=["1-1.5x", "1.5-2x", "2-3x", "3-4x", "4-6x", "6-10x", ">10x"])
    return d.groupby("bin", observed=False).agg(n=("hit", "size"), recall=("hit", "mean")).reset_index()


# ------------------------------------------------------------------ main
def run(n_seeds: int = 5, n: int = 20000, out: str | Path = "results",
        reference_path: str | Path | None = None, figures: bool = True) -> dict:
    """Full protocol. reference_path = a real reference CSV (kashf.comtrade); None = illustrative table.

    With a real reference, the detectors benchmark against real Comtrade unit values AND the
    generator draws its (still synthetic) invoice prices around them.
    """
    out = Path(out)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    s = Settings.from_yaml()
    ref = reference.load(reference_path) if reference_path else reference.default_table()
    gen_ref = ref if reference_path else None
    configs = ["kashf_full", "kashf_heuristic", *[f"minus_{d}" for d in DETECTORS],
               "price_only", "checklist", "isolation_forest"]

    # ---- tune on seed 0: per-rule calibration, then each configuration's threshold
    t0 = generate(Config(seed=0, n_invoices=n, reference=gen_ref))
    sig0 = run_all(t0, ref, s)
    table = calibrate.fit(sig0, t0["labels"])
    calibrate.save(table, out / "calibration.json")
    sc_cal = replace(s, calibration=table)

    def scores_for(t, sig, seed):
        sc = {"kashf_full": kashf_scores(t, sig, sc_cal, DETECTORS),
              "kashf_heuristic": kashf_scores(t, sig, s, DETECTORS),
              "price_only": kashf_scores(t, sig, sc_cal, ("price",)),
              "checklist": checklist_scores(t, ref, s),
              "isolation_forest": iforest_scores(t, ref, s, seed)}
        for d in DETECTORS:
            sc[f"minus_{d}"] = kashf_scores(t, sig, sc_cal, tuple(x for x in DETECTORS if x != d))
        return sc

    y0 = (t0["labels"].set_index("invoice_no")["typology"] != "none").astype(int)
    sc0 = scores_for(t0, sig0, 0)
    thr = {c: (0.5 if c == "checklist" else best_threshold(y0.values, sc0[c].reindex(y0.index).fillna(0).values))
           for c in configs}

    # ---- test on held-out seeds
    per_seed: dict[str, list[dict]] = {c: [] for c in configs}
    curves, pr = [], {}
    for seed in range(1, n_seeds + 1):
        t = generate(Config(seed=seed, n_invoices=n, reference=gen_ref))
        sig = run_all(t, ref, s)
        lab = t["labels"].set_index("invoice_no")["typology"]
        y = (lab != "none").astype(int)
        sc = scores_for(t, sig, seed)
        for c in configs:
            per_seed[c].append(metrics(y, sc[c], thr[c], lab, sig if c.startswith(("kashf", "minus")) else None))
        per_seed.setdefault("_counts", []).append({"invoices": len(y), "laundering": int(y.sum()),
                                                   **{k: int((lab == k).sum()) for k in TYPOLOGIES}})
        curves.append(mispricing_curve(t, ref, sc["kashf_full"], thr["kashf_full"], lab).assign(seed=seed))
        if seed == 1:
            for c in ("kashf_full", "price_only", "isolation_forest"):
                p, r, _ = precision_recall_curve(y.values, sc[c].reindex(y.index).fillna(0).values)
                pr[c] = (p, r)
        n_pos = int(y.sum())
        log.info("seed %d: %d invoices, %d laundering (%.1f%%), full F1 %.3f", seed, len(y), n_pos,
                 100 * n_pos / len(y), per_seed["kashf_full"][-1]["f1"])

    def agg(rows: list[dict]) -> dict:
        res = {}
        for k in rows[0]:
            if isinstance(rows[0][k], dict):
                res[k] = {kk: _ms([r[k].get(kk, math.nan) for r in rows]) for kk in rows[0][k]}
            else:
                res[k] = _ms([r[k] for r in rows])
        return res

    summary = {"protocol": {"tuning_seed": 0, "test_seeds": list(range(1, n_seeds + 1)), "invoices_per_seed": n,
                            "reference": str(reference_path) if reference_path else "illustrative (kashf/reference.py)"},
               "counts": per_seed["_counts"], "calibration": table,
               "thresholds": thr, "configs": {c: agg(per_seed[c]) for c in configs}}
    curve = pd.concat(curves).groupby("bin", observed=False).agg(n=("n", "sum"), recall=("recall", "mean")).reset_index()
    summary["mispricing_recall"] = curve.to_dict("records")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    _write_md(summary, out / "results.md")
    if figures:
        _figures(summary, curve, pr, out / "figures")
    return summary


# ------------------------------------------------------------------ robustness checks
def _tune_and_test(s: Settings, ref: pd.DataFrame, tune_cfg: Config, test_cfgs: list[Config]) -> dict:
    """Calibrate + pick the threshold on tune_cfg, then report full-Kashf metrics on each test config."""
    t0 = generate(tune_cfg)
    sig0 = run_all(t0, ref, s)
    table = calibrate.fit(sig0, t0["labels"])
    sc = replace(s, calibration=table)
    y0 = (t0["labels"].set_index("invoice_no")["typology"] != "none").astype(int)
    thr = best_threshold(y0.values, kashf_scores(t0, sig0, sc, DETECTORS).reindex(y0.index).fillna(0).values)
    rows = []
    for c in test_cfgs:
        t = generate(c)
        sig = run_all(t, ref, s)
        lab = t["labels"].set_index("invoice_no")["typology"]
        y = (lab != "none").astype(int)
        m = metrics(y, kashf_scores(t, sig, sc, DETECTORS), thr, lab, None)
        rows.append({k: m[k] for k in ("precision", "recall", "f1", "far", "avg_precision")})
    agg = {k: _ms([r[k] for r in rows]) for k in rows[0]}
    agg["threshold"] = thr
    return agg


SWEEP = {"price_z": [1.5, 2.0, 2.5, 3.0], "qty_tolerance": [0.01, 0.03, 0.05, 0.10],
         "weight_tolerance": [0.10, 0.15, 0.25, 0.40]}
SHIFT = {"price_noise_scale": 1.3, "premium_rate": 0.06, "clearance_rate": 0.04, "premium_range": (1.4, 3.5),
         "over_range": (1.3, 4.0), "under_range": (0.25, 0.75), "typology_rate": 0.004}


def robustness(n_seeds: int = 3, n: int = 20000, out: str | Path = "results",
               reference_path: str | Path | None = None) -> dict:
    """(1) Sensitivity of full Kashf to each hand-set threshold, one at a time (re-tuned on seed 0 each time).
    (2) Alert-threshold sweep with everything else fixed.
    (3) Generator shift: tune on the default generator, test on seeds drawn with different noise and
        typology parameters (SHIFT) — a check against tuning to the generator's own quirks."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    base = Settings.from_yaml()
    ref = reference.load(reference_path) if reference_path else reference.default_table()
    gref = ref if reference_path else None
    tune = Config(seed=0, n_invoices=n, reference=gref)
    tests = [Config(seed=k, n_invoices=n, reference=gref) for k in range(1, n_seeds + 1)]
    res: dict = {"sweep": {}, "shift": {}}
    for name, values in SWEEP.items():
        res["sweep"][name] = {}
        for v in values:
            log.info("sensitivity %s=%s", name, v)
            res["sweep"][name][str(v)] = _tune_and_test(replace(base, **{name: v}), ref, tune, tests)

    # alert-threshold sweep on the default settings (calibration fixed, threshold forced)
    t0 = generate(tune)
    sig0 = run_all(t0, ref, base)
    sc = replace(base, calibration=calibrate.fit(sig0, t0["labels"]))
    thr_rows = {}
    sets = []
    for c in tests:
        t = generate(c)
        sig = run_all(t, ref, base)
        lab = t["labels"].set_index("invoice_no")["typology"]
        sets.append(((lab != "none").astype(int), kashf_scores(t, sig, sc, DETECTORS), lab))
    for thr in (0.2, 0.3, 0.4, 0.44, 0.5, 0.6, 0.7, 0.8):
        ms = [metrics(y, scr, thr, lab, None) for y, scr, lab in sets]
        thr_rows[str(thr)] = {k: _ms([m[k] for m in ms]) for k in ("precision", "recall", "f1", "far")}
    res["alert_threshold"] = thr_rows

    log.info("generator shift test")
    res["shift"]["same_generator"] = _tune_and_test(base, ref, tune, tests)
    shifted = [replace(c, seed=100 + c.seed, **SHIFT) for c in tests]
    res["shift"]["shifted_generator"] = _tune_and_test(base, ref, tune, shifted)
    res["shift"]["shift_params"] = {k: list(v) if isinstance(v, tuple) else v for k, v in SHIFT.items()}
    res["protocol"] = {"tuning_seed": 0, "test_seeds": [c.seed for c in tests], "invoices_per_seed": n,
                       "reference": str(reference_path) if reference_path else "illustrative (kashf/reference.py)"}
    (out / "robustness.json").write_text(json.dumps(res, indent=2, default=float))
    _write_robustness_md(res, out / "robustness.md")
    return res


def _write_robustness_md(r: dict, path: Path) -> None:
    p = r["protocol"]
    L = ["# Robustness of the invoice layer (SYNTHETIC invoices)", "",
         f"Synthetic invoices from kashf.generate; reference prices: {p['reference']}. Tuned on seed "
         f"{p['tuning_seed']}, tested on seeds {p['test_seeds']} ({p['invoices_per_seed']:,} invoices each); "
         "mean ± sd. Each sweep changes one setting and re-runs calibration and threshold tuning on seed 0.", "",
         "## 1. Sensitivity to hand-set thresholds", ""]
    for name, vals in r["sweep"].items():
        L += [f"### {name}", "", "| Value | Precision | Recall | F1 | False-alarm rate |", "|---|---|---|---|---|"]
        for v, m in vals.items():
            L.append(f"| {v} | {_f(m['precision'])} | {_f(m['recall'])} | {_f(m['f1'])} | {_f(m['far'], 2, pct=True)} |")
        L.append("")
    L += ["## 2. Alert threshold (calibration fixed)", "",
          "| Threshold | Precision | Recall | F1 | False-alarm rate |", "|---|---|---|---|---|"]
    for v, m in r["alert_threshold"].items():
        L.append(f"| {v} | {_f(m['precision'])} | {_f(m['recall'])} | {_f(m['f1'])} | {_f(m['far'], 2, pct=True)} |")
    s = r["shift"]
    L += ["", "## 3. Generator shift", "",
          "Tuned on the default generator; tested on seeds from the same generator vs a shifted one "
          f"({', '.join(f'{k}={v}' for k, v in s['shift_params'].items())}).", "",
          "| Test data | Precision | Recall | F1 | False-alarm rate | Avg. precision |", "|---|---|---|---|---|---|"]
    for k in ("same_generator", "shifted_generator"):
        m = s[k]
        L.append(f"| {k.replace('_', ' ')} | {_f(m['precision'])} | {_f(m['recall'])} | {_f(m['f1'])} | "
                 f"{_f(m['far'], 2, pct=True)} | {_f(m['avg_precision'])} |")
    path.write_text("\n".join(L) + "\n")


def _ms(v: list[float]) -> dict:
    a = np.array(v, dtype=float)
    return {"mean": float(np.nanmean(a)), "sd": float(np.nanstd(a, ddof=1)) if len(a) > 1 else 0.0}


def _write_md(sm: dict, path: Path) -> None:
    C = sm["configs"]
    L = ["# Kashf invoice-layer results (SYNTHETIC invoices)", "",
         "Data: synthetic invoices from kashf.generate (not real trade). "
         f"Reference prices: {sm['protocol'].get('reference', 'illustrative (kashf/reference.py)')}. "
         "Real-data results are in results/macro/.", "",
         f"Thresholds tuned on seed 0; mean ± sd over held-out seeds {sm['protocol']['test_seeds']} "
         f"({sm['protocol']['invoices_per_seed']:,} invoices each).", "",
         "## Overall", "",
         "| Configuration | Precision | Recall | F1 | False-alarm rate | Alerts / 1,000 | Avg. precision |",
         "|---|---|---|---|---|---|---|"]
    for c, m in C.items():
        L.append(f"| {c} | {_f(m['precision'])} | {_f(m['recall'])} | {_f(m['f1'])} | {_f(m['far'], 2, pct=True)} | "
                 f"{m['alerts_per_1000']['mean']:.1f} | {_f(m['avg_precision'])} |")
    L += ["", "## Recall by typology", "", "| Configuration | " + " | ".join(TYPOLOGIES) + " |",
          "|---|" + "---|" * len(TYPOLOGIES)]
    for c, m in C.items():
        L.append(f"| {c} | " + " | ".join(f"{m['recall_by_typology'][k]['mean']:.2f}" for k in TYPOLOGIES) + " |")
    L += ["", "## Evidence attribution (share of true alerts whose evidence names the planted mechanism)", ""]
    for c, m in C.items():
        if "evidence_attribution" in m:
            L.append(f"- {c}: {_f(m['evidence_attribution'])}")
    L += ["", "## Kashf recall vs. size of price distortion (over- and under-invoicing)", "",
          "| Distortion vs benchmark | Invoices | Recall |", "|---|---|---|"]
    for r in sm["mispricing_recall"]:
        L.append(f"| {r['bin']} | {int(r['n'])} | {r['recall']:.2f} |")
    L += ["", "Thresholds: " + ", ".join(f"{k} = {v:.3f}" for k, v in sm["thresholds"].items())]
    path.write_text("\n".join(L) + "\n")


def _f(d: dict, nd: int = 3, pct: bool = False) -> str:
    if pct:
        return f"{100 * d['mean']:.{nd}f}% ± {100 * d['sd']:.{nd}f}"
    return f"{d['mean']:.{nd}f} ± {d['sd']:.{nd}f}"


def _figures(sm: dict, curve: pd.DataFrame, pr: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    navy, gold, grey, teal = "#0E2A47", "#C9A227", "#9AA5B1", "#2A9D8F"
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    C = sm["configs"]

    # 1. F1 by configuration
    order = ["kashf_full", "kashf_heuristic", "minus_price", "minus_route", "minus_documents", "minus_graph",
             "price_only", "isolation_forest", "checklist"]
    f1 = [C[c]["f1"]["mean"] for c in order]
    sd = [C[c]["f1"]["sd"] for c in order]
    col = [navy if c == "kashf_full" else (teal if c.startswith("minus") else gold if c == "kashf_heuristic" else grey)
           for c in order]
    fig, ax = plt.subplots(figsize=(7, 3.1), dpi=200)
    ax.bar(range(len(order)), f1, yerr=sd, color=col, capsize=3)
    for i, v in enumerate(f1):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
    ax.set_xticks(range(len(order)), [o.replace("_", " ") for o in order], rotation=25, ha="right")
    ax.set_ylabel("F1 (held-out seeds)")
    ax.set_ylim(0, 1.05)
    fig.tight_layout()
    fig.savefig(out / "f1_by_config.png")
    plt.close(fig)

    # 2. recall by typology: full vs baselines
    cfgs = ["kashf_full", "price_only", "isolation_forest", "checklist"]
    colors = [navy, gold, teal, grey]
    x = np.arange(len(TYPOLOGIES))
    w = 0.2
    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=200)
    for i, c in enumerate(cfgs):
        ax.bar(x + (i - 1.5) * w, [C[c]["recall_by_typology"][k]["mean"] for k in TYPOLOGIES], w,
               label=c.replace("_", " "), color=colors[i])
    ax.set_xticks(x, [k.replace("_", "\n") for k in TYPOLOGIES], fontsize=8)
    ax.set_ylabel("Recall")
    ax.set_ylim(0, 1.08)
    ax.legend(frameon=False, ncol=4, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, 1.15))
    fig.tight_layout()
    fig.savefig(out / "recall_by_typology.png")
    plt.close(fig)

    # 3. mispricing detectability
    fig, ax = plt.subplots(figsize=(5, 2.8), dpi=200)
    ax.plot(curve["bin"].astype(str), curve["recall"], marker="o", color=navy)
    ax.set_xlabel("Price distortion vs benchmark (either direction)")
    ax.set_ylabel("Kashf recall")
    ax.set_ylim(0, 1.05)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "mispricing_recall.png")
    plt.close(fig)

    # 4. precision-recall curves (seed 1)
    fig, ax = plt.subplots(figsize=(4.2, 3.4), dpi=200)
    for c, colr in (("kashf_full", navy), ("price_only", gold), ("isolation_forest", teal)):
        p, r = pr[c]
        ax.plot(r, p, label=c.replace("_", " "), color=colr)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "pr_curves.png")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--out", default="results")
    ap.add_argument("--reference", help="real reference CSV from `python -m kashf.comtrade reference`")
    ap.add_argument("--robustness", action="store_true", help="threshold sweeps + generator-shift test")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if a.robustness:
        robustness(min(a.seeds, 3), a.n, a.out, a.reference)
    else:
        run(a.seeds, a.n, a.out, a.reference)


if __name__ == "__main__":
    main()
