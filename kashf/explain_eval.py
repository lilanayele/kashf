"""Measuring explainability (results/explainability.json, results/explainability.md).

Definition used in the paper and README: an alert is *explainable* when it lists the specific
evidence (values, benchmark, rule) that produced it, AND removing that evidence removes the alert.

Three measurements:

1. Evidence attribution per typology (SYNTHETIC): share of true alerts whose evidence names the
   mechanism that was actually planted (kashf.evaluate.EXPECTED).
2. Deletion / faithfulness test (SYNTHETIC): for each alert, drop its strongest signal and re-score
   (eq. 3); how often does the score fall below the alert threshold? Compared with dropping a random
   one of its signals. Reported for all alerts and for alerts with two or more signals (for a
   single-signal alert both deletions are the same signal).
3. Macro layer (REAL, UN Comtrade): for pairs flagged by both the rules and the Isolation Forest,
   does the feature SHAP ranks first belong to a rule that fired? Compared with the agreement
   expected if SHAP picked a feature at random.

    python -m kashf.explain_eval --seeds 5
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from kashf import calibrate, reference
from kashf.config import Settings, load_yaml
from kashf.detectors import run_all
from kashf.evaluate import EXPECTED, TYPOLOGIES
from kashf.generate import Config, generate

log = logging.getLogger("kashf.explain_eval")
ROOT = Path(__file__).resolve().parent.parent


def signal_weights(sig: pd.DataFrame, s: Settings) -> pd.DataFrame:
    """One row per (invoice, rule): the calibrated, weighted strength that enters eq. 3."""
    sg = calibrate.apply(sig, s.calibration) if s.calibration else sig.copy()
    sg["ws"] = (sg["detector"].map(s.weights).fillna(1.0) * sg["strength"]).clip(0, 0.999)
    return sg.sort_values("ws", ascending=False).drop_duplicates(["invoice_no", "rule"])


def noisy_or(ws: np.ndarray) -> float:
    return float(1 - np.prod(1 - ws)) if len(ws) else 0.0


def deletion_test(best: pd.DataFrame, thr: float, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for inv, g in best.groupby("invoice_no"):
        ws = g["ws"].to_numpy()
        score = noisy_or(ws)
        if score < thr:
            continue
        top = int(np.argmax(ws))
        rnd = int(rng.integers(len(ws)))
        rows.append({"invoice_no": inv, "n_signals": len(ws), "score": score,
                     "drop_top": noisy_or(np.delete(ws, top)) < thr,
                     "drop_random": noisy_or(np.delete(ws, rnd)) < thr,
                     "top_alone": ws[top] >= thr})
    return pd.DataFrame(rows)


def synthetic(n_seeds: int, n: int, seed_offset: int = 1) -> dict:
    s = Settings.from_yaml()
    summ = json.loads((ROOT / "results/summary.json").read_text())
    thr = float(summ["thresholds"]["kashf_full"])
    table = calibrate.load(ROOT / "results/calibration.json")
    sc = replace(s, calibration=table)
    ref = reference.default_table()
    rng = np.random.default_rng(0)
    attr: dict[str, list[float]] = {k: [] for k in TYPOLOGIES}
    dels = []
    for seed in range(seed_offset, seed_offset + n_seeds):
        t = generate(Config(seed=seed, n_invoices=n))
        sig = run_all(t, ref, s)
        lab = t["labels"].set_index("invoice_no")["typology"]
        best = signal_weights(sig, sc)
        d = deletion_test(best, thr, rng).assign(seed=seed)
        d["laundering"] = d["invoice_no"].map(lab).fillna("none") != "none"
        dels.append(d)
        rules = best.groupby("invoice_no")["rule"].apply(set)
        alerts = set(d["invoice_no"])
        for k in TYPOLOGIES:
            ids = [i for i in lab.index[lab == k] if i in alerts]
            if ids:
                attr[k].append(float(np.mean([bool(rules.get(i, set()) & EXPECTED[k]) for i in ids])))
    D = pd.concat(dels, ignore_index=True)
    multi = D[D["n_signals"] >= 2]

    def rates(x: pd.DataFrame) -> dict:
        return {"alerts": int(len(x)), "drop_top_removes_alert": float(x["drop_top"].mean()) if len(x) else float("nan"),
                "drop_random_removes_alert": float(x["drop_random"].mean()) if len(x) else float("nan"),
                "top_signal_alone_is_alert": float(x["top_alone"].mean()) if len(x) else float("nan")}

    return {
        "label": "SYNTHETIC (kashf.generate), held-out seeds",
        "seeds": list(range(seed_offset, seed_offset + n_seeds)), "invoices_per_seed": n, "alert_threshold": thr,
        "attribution_by_typology": {k: {"mean": float(np.mean(v)), "seeds": len(v)} for k, v in attr.items() if v},
        "deletion": {"all_alerts": rates(D), "multi_signal_alerts": rates(multi),
                     "true_alerts": rates(D[D["laundering"]]), "false_alerts": rates(D[~D["laundering"]]),
                     "share_single_signal": float((D["n_signals"] == 1).mean())},
    }


def macro_shap() -> dict:
    """Agreement between the Isolation Forest's SHAP top feature and the rule that fired (real data)."""
    from kashf import macro

    flags = ROOT / "results/macro/flags.csv"
    if not flags.exists():
        return {"skipped": "results/macro/flags.csv not found (run kashf.macro first)"}
    cfg = load_yaml()["macro"]
    p = pd.read_csv(flags)
    f, model, cols = macro.iforest(p, cfg, seed=0)
    same = float((f["if_flag"].astype(bool).values == p["if_flag"].astype(bool).values).mean())
    both = p.index[p["rule_flag"].astype(bool) & f["if_flag"].astype(bool)]
    X, _ = macro.feature_matrix(p)
    import shap

    vals = -np.asarray(shap.TreeExplainer(model).shap_values(X[p.index.get_indexer(both)]))
    base = [c.replace("_missing", "") for c in cols]
    thr_uv = float(cfg["uv_z_threshold"])
    top1 = top2 = 0
    rand = []
    for k, i in enumerate(both):
        r = p.loc[i]
        fired = set()
        if r["r_gap"] >= 1:
            fired.add("gap_rz")
        if r["r_wgt"] >= 1:
            fired.add("wgap_rz")
        if r["r_uv"] >= 1:
            for c in ("uv_z_exp", "uv_z_imp"):
                if pd.notna(r[c]) and abs(r[c]) >= thr_uv:
                    fired.add(c)
        contrib: dict[str, float] = {}
        for j, b in enumerate(base):
            contrib[b] = contrib.get(b, 0.0) + vals[k, j]
        order = sorted(contrib, key=contrib.get, reverse=True)
        top1 += order[0] in fired
        top2 += bool(set(order[:2]) & fired)
        rand.append(len(fired) / len(macro.FEATURES))
    n = len(both)
    return {"label": "REAL (UN Comtrade), results/macro/flags.csv",
            "pairs_flagged_by_both": int(n), "if_flags_reproduced": same,
            "shap_top1_in_fired_rule": top1 / n if n else float("nan"),
            "shap_top2_contains_fired_rule": top2 / n if n else float("nan"),
            "random_top1_expected": float(np.mean(rand)) if rand else float("nan")}


def write_md(r: dict, path: Path) -> None:
    sy, m = r["synthetic"], r["macro"]
    d = sy["deletion"]
    pc = lambda x: f"{100 * x:.1f}%"  # noqa: E731
    L = ["# Explainability measurements", "",
         "Definition: an alert is explainable when it lists the specific evidence (values, benchmark, rule) that "
         "produced it, and removing that evidence removes the alert.", "",
         f"## 1. Evidence attribution by typology ({sy['label']})", "",
         "Share of true alerts whose evidence names the planted mechanism.", "",
         "| Typology | Attribution | Seeds |", "|---|---|---|"]
    for k, v in sy["attribution_by_typology"].items():
        L.append(f"| {k} | {v['mean']:.3f} | {v['seeds']} |")
    L += ["", f"## 2. Deletion test ({sy['label']}, alert threshold {sy['alert_threshold']:.3f})", "",
          "| Alerts | n | Drop strongest signal -> no alert | Drop random signal -> no alert | Strongest signal alone is an alert |",
          "|---|---|---|---|---|"]
    for k in ("all_alerts", "multi_signal_alerts", "true_alerts", "false_alerts"):
        x = d[k]
        L.append(f"| {k.replace('_', ' ')} | {x['alerts']:,} | {pc(x['drop_top_removes_alert'])} | "
                 f"{pc(x['drop_random_removes_alert'])} | {pc(x['top_signal_alone_is_alert'])} |")
    L += ["", f"Single-signal alerts: {pc(d['share_single_signal'])} of all alerts (for these the strongest and the "
          "random signal are the same, and removing it always removes the alert).", "",
          f"## 3. Macro layer: SHAP vs rules ({m.get('label', '')})", ""]
    if "skipped" in m:
        L.append(m["skipped"])
    else:
        L += [f"Pairs flagged by both the rules and the Isolation Forest: {m['pairs_flagged_by_both']:,} "
              f"(Isolation Forest flags reproduced exactly for {pc(m['if_flags_reproduced'])} of pairs).", "",
              f"- SHAP top feature belongs to a rule that fired: {pc(m['shap_top1_in_fired_rule'])}",
              f"- One of SHAP's top two features belongs to a rule that fired: {pc(m['shap_top2_contains_fired_rule'])}",
              f"- Expected top-1 agreement if SHAP picked a feature at random: {pc(m['random_top1_expected'])}"]
    L += ["", "No user study has been run; see docs/user_study.md for the protocol."]
    path.write_text("\n".join(L) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--out", default=str(ROOT / "results"))
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    r = {"synthetic": synthetic(a.seeds, a.n), "macro": macro_shap()}
    out = Path(a.out)
    (out / "explainability.json").write_text(json.dumps(r, indent=2))
    write_md(r, out / "explainability.md")
    log.info("wrote %s", out / "explainability.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
