"""Macro layer: trade-misinvoicing signals on REAL UN Comtrade data.

Unit of analysis: one mirror pair = (direction, UAE, partner, HS6, year), where the same
flow is reported by both sides:

    uae_export   UAE-reported exports + re-exports to partner   vs  partner-reported imports from UAE
    uae_import   UAE-reported imports from partner              vs  partner-reported exports to UAE

Features (all logs are natural logs)

    mirror_gap   log( importer value / ((1 + c) * exporter value) )
                 c = CIF/FOB factor, a documented assumption (configs/default.yaml, default 0.10).
                 > 0: importer reports more than expected; < 0: less.
    weight_gap   log( importer net weight / exporter net weight )        (no freight adjustment)
    uv_z_exp/imp robust z of each side's unit value against the global HS6 x year distribution of
                 unit values in all reporters' exports to World:
                     z = (log uv - median log uv) / (1.4826 * MAD)
                 the importer's unit value is divided by (1 + c) first, to put it on an FOB basis.

Detectors

    rules        flag if |mirror_gap| > T_gap, or |weight_gap| > T_w, or max |uv_z| > T_z.
                 Thresholds are fixed in the YAML before looking at results (not tuned).
    iforest      Isolation Forest over the same features; per-flag explanation by SHAP if
                 installed, otherwise by each feature's robust deviation.

Methodological background (cited in the paper; verify before quoting):
  * Mirror-statistics comparison of partner-reported trade: the trade-misinvoicing approach of
    Global Financial Integrity (GFI), "Trade-Related Illicit Financial Flows in 135 Developing
    Countries: 2008-2017" (2020). [title/year from memory: VERIFY before citing]
  * Price-filter / unit-value outlier idea: J. S. Zdanowicz, "Trade-Based Money Laundering and
    Terrorist Financing," Review of Law & Economics 5(2):855-878, 2009, doi:10.2202/1555-5879.1419.
  * Typologies and red flags: FATF & Egmont Group, "Trade-Based Money Laundering: Trends and
    Developments" (Dec 2020) and "Trade-Based Money Laundering: Risk Indicators" (Mar 2021).

A mirror gap is NOT evidence of laundering by itself. Re-exports, origin vs consignment
attribution, CIF/FOB differences, timing, classification differences, confidential codes and
Comtrade's own estimated quantities all create gaps (docs/DATA_CARD.md). The macro layer
ranks country x product flows for a closer look; it does not accuse anyone.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score

from kashf.config import load_yaml

log = logging.getLogger("kashf.macro")

UAE = 784
# Comtrade partner codes that are aggregates or special areas, not countries
NON_COUNTRY = {0, 97, 837, 838, 839, 899}
FEATURES = ["mirror_gap", "weight_gap", "uv_z_exp", "uv_z_imp"]
MAD_K = 1.4826


def cfg_macro(cfg: Optional[dict] = None) -> dict:
    return cfg if cfg is not None else load_yaml().get("macro", {})


# ------------------------------------------------------------------ mirror pairs
def _side(df: pd.DataFrame, flows: tuple[str, ...], who: str) -> pd.DataFrame:
    """Sum one side's flows per counterpart x HS6 x year. `who` = column holding the counterpart."""
    d = df[df["flow"].isin(flows)].copy()
    d["counterpart"] = d[who]
    d["rx_value"] = np.where(d["flow"].isin(["RX", "RM"]), d["value_usd"], 0.0)
    d["wgt_est"] = d["wgt_estimated"].fillna(False).astype(bool)
    g = d.groupby(["counterpart", "hs6", "year"]).agg(
        value=("value_usd", lambda x: x.sum(min_count=1)),
        wgt=("net_wgt_kg", lambda x: x.sum(min_count=1)),
        qty=("qty", lambda x: x.sum(min_count=1)),
        rx_value=("rx_value", "sum"),
        wgt_est=("wgt_est", "any"),
    ).reset_index()
    return g


def build_pairs(flows: pd.DataFrame, cif_fob: float = 0.10) -> pd.DataFrame:
    """Join the UAE's reports with its partners' reports of the same flows."""
    uae = flows[(flows["source"] == "uae") & (flows["reporter"] == UAE) & ~flows["partner"].isin(NON_COUNTRY)]
    mir = flows[(flows["source"] == "mirror") & (flows["partner"] == UAE) & ~flows["reporter"].isin(NON_COUNTRY)
                & (flows["reporter"] != UAE)]
    if uae.empty or mir.empty:
        raise ValueError("need both UAE-reported and partner-reported flows to build mirror pairs")
    names = pd.concat([
        uae[["partner", "partner_iso"]].rename(columns={"partner": "code", "partner_iso": "iso"}),
        mir[["reporter", "reporter_iso"]].rename(columns={"reporter": "code", "reporter_iso": "iso"}),
    ]).dropna().drop_duplicates("code").set_index("code")["iso"]

    out = []
    # UAE exports + re-exports vs partner imports from UAE
    e = _side(uae, ("X", "RX"), "partner")
    i = _side(mir, ("M",), "reporter")
    p = e.merge(i, on=["counterpart", "hs6", "year"], suffixes=("_exp", "_imp"))
    p["direction"] = "uae_export"
    out.append(p)
    # UAE imports + re-imports vs partner exports to UAE
    e = _side(mir, ("X",), "reporter")
    i = _side(uae, ("M", "RM"), "partner")
    p = e.merge(i, on=["counterpart", "hs6", "year"], suffixes=("_exp", "_imp"))
    p["direction"] = "uae_import"
    out.append(p)

    pairs = pd.concat(out, ignore_index=True).rename(columns={"counterpart": "partner"})
    pairs["partner_iso"] = pairs["partner"].map(names)
    pairs["rx_share"] = np.where(pairs["direction"] == "uae_export",
                                 pairs["rx_value_exp"] / pairs["value_exp"], np.nan)
    pairs = pairs.drop(columns=["rx_value_imp"]).rename(columns={"rx_value_exp": "rx_value"})
    pairs["mirror_gap"] = np.log(pairs["value_imp"] / ((1 + cif_fob) * pairs["value_exp"]))
    pairs["weight_gap"] = np.log(pairs["wgt_imp"] / pairs["wgt_exp"])
    return pairs[["direction", "partner", "partner_iso", "hs6", "year", "value_exp", "value_imp", "wgt_exp",
                  "wgt_imp", "qty_exp", "qty_imp", "rx_value", "rx_share", "wgt_est_exp", "wgt_est_imp",
                  "mirror_gap", "weight_gap"]]


def add_unit_value_z(pairs: pd.DataFrame, dist: pd.DataFrame, cif_fob: float = 0.10) -> pd.DataFrame:
    """Robust z of each side's unit value vs the global HS6 x year distribution (kashf.comtrade)."""
    d = dist.set_index(["hs6", "year"])
    p = pairs.copy()
    idx = pd.MultiIndex.from_frame(p[["hs6", "year"]])
    med = d["log_median"].reindex(idx).values
    mad = np.maximum(d["log_mad"].reindex(idx).values, 0.05)
    ok = d["enough"].reindex(idx).fillna(False).values.astype(bool)
    basis = d["basis"].reindex(idx).values
    per_kg = basis == "kg"
    for side, adj in (("exp", 1.0), ("imp", 1.0 + cif_fob)):
        denom = np.where(per_kg, p[f"wgt_{side}"], p[f"qty_{side}"])
        uv = p[f"value_{side}"].values / adj / denom
        z = (np.log(uv) - med) / (MAD_K * mad)
        p[f"uv_{side}"] = uv
        p[f"uv_z_{side}"] = np.where(ok & np.isfinite(z), z, np.nan)
    p["uv_basis"] = basis
    p["uv_median"] = np.exp(med)
    p["uv_log_mad"] = mad
    return p


def eligible(p: pd.DataFrame, min_flow: float) -> pd.DataFrame:
    """Pairs where both sides report a value of at least min_flow USD."""
    m = (p["value_exp"] >= min_flow) & (p["value_imp"] >= min_flow)
    return p[m].reset_index(drop=True)


# ------------------------------------------------------------------ detectors
def rules(p: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Rules baseline: each feature divided by its fixed threshold; a ratio >= 1 is a flag."""
    out = p.copy()
    out["r_gap"] = out["mirror_gap"].abs() / float(cfg["gap_threshold"])
    out["r_wgt"] = out["weight_gap"].abs() / float(cfg["weight_gap_threshold"])
    out["r_uv"] = out[["uv_z_exp", "uv_z_imp"]].abs().max(axis=1, skipna=True) / float(cfg["uv_z_threshold"])
    out["rule_score"] = out[["r_gap", "r_wgt", "r_uv"]].max(axis=1, skipna=True).fillna(0.0)
    out["rule_flag"] = out["rule_score"] >= 1.0
    return out


def feature_matrix(p: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    X = p[FEATURES].copy()
    cols = list(FEATURES)
    for c in FEATURES:
        miss = X[c].isna()
        if miss.any():
            X[c + "_missing"] = miss.astype(float)
            cols.append(c + "_missing")
        X[c] = X[c].fillna(0.0)
    return X[cols].values, cols


def iforest(p: pd.DataFrame, cfg: dict, seed: int = 0) -> tuple[pd.DataFrame, IsolationForest, list[str]]:
    X, cols = feature_matrix(p)
    m = IsolationForest(n_estimators=int(cfg.get("iforest_trees", 300)),
                        contamination=float(cfg.get("iforest_contamination", 0.05)), random_state=seed).fit(X)
    out = p.copy()
    out["if_score"] = -m.score_samples(X)
    out["if_flag"] = m.predict(X) == -1
    return out, m, cols


def explain_iforest(p: pd.DataFrame, model: IsolationForest, cols: list[str], rows: pd.Index) -> pd.Series:
    """Top contributing features for the given rows: SHAP if available, else robust deviation."""
    X, _ = feature_matrix(p)
    sub = X[p.index.get_indexer(rows)]
    try:
        import shap
        vals = shap.TreeExplainer(model).shap_values(sub)
        method = "SHAP"
        contrib = -np.asarray(vals)          # negative SHAP on score_samples = pushes toward anomaly
    except Exception as e:  # shap missing or unsupported: fall back, and say so
        log.info("SHAP unavailable (%s); using robust deviations", type(e).__name__)
        med = np.median(X, axis=0)
        mad = np.median(np.abs(X - med), axis=0) * MAD_K
        contrib = np.abs(sub - med) / np.where(mad > 0, mad, 1.0)
        method = "deviation"
    texts = []
    for row in contrib:
        order = np.argsort(row)[::-1][:2]
        texts.append(f"{method}: " + ", ".join(f"{cols[j]} ({row[j]:+.2f})" for j in order))
    return pd.Series(texts, index=rows)


# ------------------------------------------------------------------ explanations
def _usd(v: float) -> str:
    if not np.isfinite(v):
        return "n/a"
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(v) >= div:
            return f"${v / div:,.1f}{suf}"
    return f"${v:,.0f}"


def explain(r: pd.Series, cfg: dict) -> str:
    """Plain-language reasons for one flagged pair, built only from the numbers in the row."""
    c = float(cfg["cif_fob_factor"])
    who = r["partner_iso"] or str(r["partner"])
    reasons = []
    if r.get("r_gap", 0) >= 1:
        if r["direction"] == "uae_export":
            s = (f"{who} reports imports from UAE of {_usd(r['value_imp'])}; UAE reports exports + re-exports "
                 f"of {_usd(r['value_exp'])} (x{1 + c:.2f} CIF/FOB = {_usd((1 + c) * r['value_exp'])})")
        else:
            s = (f"UAE reports imports from {who} of {_usd(r['value_imp'])}; {who} reports exports to UAE "
                 f"of {_usd(r['value_exp'])} (x{1 + c:.2f} CIF/FOB = {_usd((1 + c) * r['value_exp'])})")
        reasons.append(f"{s}: importer side is {np.exp(r['mirror_gap']):.2f}x the expected value")
    if r.get("r_wgt", 0) >= 1 and np.isfinite(r["weight_gap"]):
        reasons.append(f"net weight differs {np.exp(r['weight_gap']):.2f}x between the two reports "
                       f"({r['wgt_imp']:,.0f} kg importer vs {r['wgt_exp']:,.0f} kg exporter)")
    if r.get("r_uv", 0) >= 1:
        for side, lab in (("exp", "exporter"), ("imp", "importer")):
            z = r.get(f"uv_z_{side}")
            if z is not None and np.isfinite(z) and abs(z) >= float(cfg["uv_z_threshold"]):
                unit = "kg" if r.get("uv_basis") == "kg" else "unit"
                reasons.append(f"{lab}'s unit value {_usd(r[f'uv_{side}'])}/{unit} is {z:+.1f} robust SD from "
                               f"the global median {_usd(r['uv_median'])}/{unit} for HS {r['hs6']} in {r['year']}")
    return "; ".join(reasons)


def innocent(r: pd.Series) -> str:
    """The most plausible benign explanation(s) for the pattern, to check before suspecting anything."""
    out = []
    g = r["mirror_gap"]
    if r["direction"] == "uae_export":
        if np.isfinite(r.get("rx_share", np.nan)) and r["rx_share"] > 0.5:
            out.append(f"{r['rx_share']:.0%} of the UAE value is re-exports; partners often record such goods "
                       "under the country of origin, not the UAE")
        if g > 0:
            out.append("goods shipped via UAE free zones may leave outside UAE customs statistics while the "
                       "partner records the UAE as consignor")
        elif g < 0:
            out.append("partner may attribute UAE re-exports to the original producing country")
    else:
        if g > 0:
            out.append("UAE may record origin while the partner recorded a different destination "
                       "(transshipment through a third country)")
        elif g < 0:
            out.append("goods declared to the UAE may enter a free zone and never be recorded as UAE imports")
    if abs(g) > 0.4:
        out.append("freight/insurance far above 10% (CIF/FOB) or a shipment straddling the year end")
    if np.isfinite(r.get("weight_gap", np.nan)) and abs(r["weight_gap"]) > 0.4:
        out.append("one side's net weight may be estimated by Comtrade" if (r.get("wgt_est_exp") or
                   r.get("wgt_est_imp")) else "different quantity units or a partial-shipment report")
    if r.get("r_uv", 0) >= 1:
        out.append("product mix inside one HS6 code (premium vs basic models) or a classification difference")
    return "; ".join(dict.fromkeys(out)) or "no single benign explanation stands out; review the source records"


# ------------------------------------------------------------------ evaluation on real flows
def inject(p: pd.DataFrame, size: float, share: float, rng: np.random.Generator,
           cif_fob: float) -> tuple[pd.DataFrame, np.ndarray]:
    """Distort the importer-reported value of a random share of pairs by (1+size) up or down.

    Up = over-invoiced import (value moved out of the importing country); down = under-invoiced.
    Weights are left alone, as in real misinvoicing where only the price is falsified.
    Returns the distorted pairs and the boolean label of which rows were distorted.
    """
    q = p.copy()
    n = len(q)
    k = max(1, int(round(share * n)))
    idx = rng.choice(n, k, replace=False)
    up = rng.random(k) < 0.5
    factor = np.where(up, 1 + size, 1 / (1 + size))
    y = np.zeros(n, dtype=bool)
    y[idx] = True
    q.loc[q.index[idx], "value_imp"] = q["value_imp"].values[idx] * factor
    q["mirror_gap"] = np.log(q["value_imp"] / ((1 + cif_fob) * q["value_exp"]))
    # importer unit value moves with the value; its z moves by log(factor) / (1.4826 * MAD)
    shift = np.zeros(n)
    shift[idx] = np.log(factor)
    if "uv_imp" in q:
        q["uv_imp"] = q["uv_imp"] * np.exp(shift)
        q["uv_z_imp"] = q["uv_z_imp"] + shift / (MAD_K * q["uv_log_mad"])
    return q, y


def evaluate_injection(p: pd.DataFrame, cfg: dict, seed: int = 0) -> pd.DataFrame:
    """Recall, precision and PR-AUC vs injection size for rules and Isolation Forest.

    Precision here is a LOWER BOUND: real flows that are flagged but not injected count as
    false positives, although some of them may be genuine anomalies.
    """
    rows = []
    c = float(cfg["cif_fob_factor"])
    base = rules(p, cfg)
    pre_flag = base["rule_flag"].values
    for size in cfg["injection_sizes"]:
        for rep in range(int(cfg["injection_repeats"])):
            rng = np.random.default_rng(seed * 1000 + rep)
            q, y = inject(p, float(size), float(cfg["injection_share"]), rng, c)
            r = rules(q, cfg)
            f, _, _ = iforest(q, cfg, seed=rep)
            for name, flag, score in (("rules", r["rule_flag"].values, r["rule_score"].values),
                                      ("iforest", f["if_flag"].values, f["if_score"].values)):
                tp = int((flag & y).sum())
                fresh = y & ~pre_flag      # injected rows that rules did not already flag before injection
                rows.append({"size": size, "repeat": rep, "method": name, "n_pairs": len(q),
                             "n_injected": int(y.sum()),
                             "recall": tp / max(1, int(y.sum())),
                             "recall_on_unflagged": int((flag & fresh).sum()) / max(1, int(fresh.sum())),
                             "precision_lower_bound": tp / max(1, int(flag.sum())),
                             "flag_rate": float(flag.mean()),
                             "pr_auc": float(average_precision_score(y, score)),
                             "pr_auc_random": float(y.mean())})
    return pd.DataFrame(rows)


def summarise_injection(ev: pd.DataFrame) -> pd.DataFrame:
    g = ev.groupby(["method", "size"]).agg(
        recall=("recall", "mean"), recall_sd=("recall", "std"),
        recall_on_unflagged=("recall_on_unflagged", "mean"),
        precision_lb=("precision_lower_bound", "mean"), flag_rate=("flag_rate", "mean"),
        pr_auc=("pr_auc", "mean"), pr_auc_random=("pr_auc_random", "mean"),
        n_pairs=("n_pairs", "first"), n_injected=("n_injected", "first")).reset_index()
    return g


def case_study(p: pd.DataFrame, cfg: dict, k: int = 10, descriptions: Optional[dict] = None) -> pd.DataFrame:
    """Top-k flows by rule score on the real data (no injection), with reasons and benign explanations."""
    r = rules(p, cfg)
    top = r[r["rule_flag"]].sort_values("rule_score", ascending=False).head(k).copy()
    top["product"] = top["hs6"].map(descriptions or {}).fillna("")
    top["why_flagged"] = [explain(x, cfg) for _, x in top.iterrows()]
    top["benign_explanations"] = [innocent(x) for _, x in top.iterrows()]
    return top


# ------------------------------------------------------------------ end-to-end run
def run(out: Path, cfg_all: Optional[dict] = None, seed: int = 0) -> dict:
    """Pairs, flags, injection evaluation and case study from the cached Comtrade data."""
    from kashf import comtrade
    from kashf.reference import default_table

    cfg_all = cfg_all or load_yaml()
    cfg, ccfg = cfg_all["macro"], cfg_all["comtrade"]
    c = float(cfg["cif_fob_factor"])
    flows = comtrade.load_raw()
    dist = comtrade.global_distribution(flows, int(ccfg.get("min_reporters_for_reference", 5)))
    pairs = add_unit_value_z(build_pairs(flows, c), dist, c)
    elig = eligible(pairs, float(cfg["min_flow_usd"]))
    if elig.empty:
        raise ValueError("no mirror pairs above min_flow_usd; lower it in the config or pull more data")
    log.info("%d mirror pairs, %d eligible (both sides >= %s)", len(pairs), len(elig), _usd(cfg["min_flow_usd"]))

    r = rules(elig, cfg)
    f, model, cols = iforest(elig, cfg, seed)
    flagged = r.assign(if_score=f["if_score"], if_flag=f["if_flag"])
    desc = dict(default_table()[["hs6", "description"]].values)
    names = flows.dropna(subset=["description"]).drop_duplicates("hs6").set_index("hs6")["description"]
    for k, v in names.items():
        desc.setdefault(k, str(v)[:40])
    cs = case_study(elig, cfg, 10, desc)
    if len(cs):
        cs["iforest_explanation"] = explain_iforest(elig, model, cols, cs.index)
        cs["iforest_flag"] = f.loc[cs.index, "if_flag"].values

    ev = evaluate_injection(elig, cfg, seed)
    summ = summarise_injection(ev)

    out.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(out / "mirror_pairs.csv", index=False)
    flagged.to_csv(out / "flags.csv", index=False)
    ev.to_csv(out / "injection_runs.csv", index=False)
    summ.to_csv(out / "injection_summary.csv", index=False)
    cs.to_csv(out / "case_study.csv", index=False)
    stats = {"pairs": len(pairs), "eligible": len(elig), "years": sorted(elig["year"].unique().tolist()),
             "partners": int(elig["partner"].nunique()), "hs6": int(elig["hs6"].nunique()),
             "rule_flag_rate": float(r["rule_flag"].mean()), "if_flag_rate": float(f["if_flag"].mean()),
             "agree": float((r["rule_flag"] == f["if_flag"]).mean()),
             "median_abs_gap": float(elig["mirror_gap"].abs().median())}
    _write_md(stats, summ, cs, cfg, out / "macro_results.md")
    _figure(summ, out / "recall_vs_injection.png")
    return {"stats": stats, "summary": summ, "case_study": cs}


def _write_md(st: dict, summ: pd.DataFrame, cs: pd.DataFrame, cfg: dict, path: Path) -> None:
    L = ["# Macro layer results: REAL UN Comtrade mirror data", "",
         "Data source: UN Comtrade (annual, HS, total level), pulled with `python -m kashf.comtrade pull`. "
         "See docs/DATA_CARD.md for coverage and caveats.", "",
         f"- Mirror pairs: {st['pairs']:,} (eligible, both sides >= {_usd(cfg['min_flow_usd'])}: {st['eligible']:,})",
         f"- Years: {', '.join(map(str, st['years']))}; partners: {st['partners']}; HS6 codes: {st['hs6']}",
         f"- Median |log mirror gap|: {st['median_abs_gap']:.2f} "
         f"(sides typically differ by {np.exp(st['median_abs_gap']):.2f}x after the CIF/FOB adjustment)",
         f"- Flag rate on real data: rules {st['rule_flag_rate']:.1%}, Isolation Forest {st['if_flag_rate']:.1%}; "
         f"agreement {st['agree']:.1%}", "",
         "## Detection of injected misinvoicing (semi-synthetic: real flows + known distortion)", "",
         f"{cfg['injection_share']:.0%} of eligible pairs have the importer-reported value pushed up or down by the "
         f"stated size; mean over {cfg['injection_repeats']} repeats. Thresholds fixed in configs/default.yaml "
         "before the run (not tuned). Precision is a lower bound: naturally anomalous real flows count as false "
         "positives. 'Recall on unflagged' counts only injected pairs the rules did not already flag before "
         "injection.", "",
         "| Method | Distortion | Recall | Recall on unflagged | Precision (lower bound) | Flag rate | PR-AUC | PR-AUC (random) |",
         "|---|---|---|---|---|---|---|---|"]
    for _, x in summ.sort_values(["size", "method"]).iterrows():
        L.append(f"| {x['method']} | +/-{x['size']:.0%} | {x['recall']:.2f} | {x['recall_on_unflagged']:.2f} | "
                 f"{x['precision_lb']:.2f} | {x['flag_rate']:.1%} | {x['pr_auc']:.2f} | {x['pr_auc_random']:.2f} |")
    L += ["", "## Case study: top 10 flagged UAE flows on the real data", "",
          "Flags are reasons to look, not findings. Each row lists the benign explanations to rule out first.", ""]
    for i, (_, x) in enumerate(cs.iterrows(), 1):
        arrow = f"UAE -> {x['partner_iso']}" if x["direction"] == "uae_export" else f"{x['partner_iso']} -> UAE"
        L += [f"**{i}. {arrow}, HS {x['hs6']} {x.get('product', '')}, {x['year']}** "
              f"(rule score {x['rule_score']:.1f}; Isolation Forest {'flagged' if x.get('iforest_flag') else 'not flagged'})",
              f"- Why flagged: {x['why_flagged']}",
              f"- Isolation Forest: {x.get('iforest_explanation', 'n/a')}",
              f"- Check first: {x['benign_explanations']}", ""]
    path.write_text("\n".join(L) + "\n")


def _figure(summ: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5, 3), dpi=200)
    for m, col in (("rules", "#0E2A47"), ("iforest", "#2A9D8F")):
        d = summ[summ["method"] == m].sort_values("size")
        ax.plot(d["size"] * 100, d["recall"], marker="o", color=col, label=m)
    ax.set_xlabel("Injected distortion of importer value (%)")
    ax.set_ylabel("Recall")
    ax.set_ylim(0, 1.05)
    ax.set_title("Real Comtrade flows + injected misinvoicing", fontsize=9)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m kashf.macro")
    ap.add_argument("--out", default="results/macro")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    res = run(Path(a.out), seed=a.seed)
    log.info("wrote %s/macro_results.md", a.out)
    log.info("\n%s", res["summary"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
