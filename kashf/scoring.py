"""Combine detector signals into one explainable risk score per invoice and per company.

Invoice score (noisy-OR): the strongest signal per rule counts once, each detector
can be weighted, and the result stays in [0, 1]:

    score = 1 - Π_k (1 - w_d(k) · s_k)

An invoice becomes an alert when score >= alert_threshold. Every alert keeps the
list of signals that produced it, ordered by strength — that list IS the explanation.
"""

from __future__ import annotations

import pandas as pd

from kashf.config import Settings


def score_invoices(inv: pd.DataFrame, sig: pd.DataFrame, s: Settings) -> pd.DataFrame:
    base = inv[["invoice_no", "date", "seller_id", "buyer_id", "hs6", "description", "value_usd", "route"]].copy()
    if sig.empty:
        base["score"], base["n_signals"], base["detectors"], base["top_reason"] = 0.0, 0, "", ""
        base["alert"] = False
        return base
    sg = sig.copy()
    if s.calibration:
        from kashf.calibrate import apply
        sg = apply(sg, s.calibration)
    sg["w"] = sg["detector"].map(s.weights).fillna(1.0)
    sg["ws"] = (sg["w"] * sg["strength"]).clip(0, 0.999)
    best = sg.sort_values("ws", ascending=False).drop_duplicates(["invoice_no", "rule"])
    agg = best.groupby("invoice_no").agg(
        p_clean=("ws", lambda x: float((1 - x).prod())),
        n_signals=("rule", "count"),
        detectors=("detector", lambda x: ", ".join(sorted(set(x)))),
        top_reason=("evidence", "first"),
    ).reset_index()
    agg["score"] = (1 - agg["p_clean"]).round(4)
    out = base.merge(agg.drop(columns="p_clean"), on="invoice_no", how="left")
    out["score"] = out["score"].fillna(0.0)
    out["n_signals"] = out["n_signals"].fillna(0).astype(int)
    out[["detectors", "top_reason"]] = out[["detectors", "top_reason"]].fillna("")
    out["alert"] = out["score"] >= s.alert_threshold
    return out.sort_values("score", ascending=False).reset_index(drop=True)


def score_entities(scored: pd.DataFrame, ent: pd.DataFrame) -> pd.DataFrame:
    """Company risk = share and value of its invoices that are alerts (as seller or buyer)."""
    long = pd.concat([
        scored[["invoice_no", "seller_id", "score", "alert", "value_usd"]].rename(columns={"seller_id": "entity_id"}),
        scored[["invoice_no", "buyer_id", "score", "alert", "value_usd"]].rename(columns={"buyer_id": "entity_id"}),
    ], ignore_index=True)
    long["alert_value"] = long["value_usd"].where(long["alert"], 0.0)
    g = long.groupby("entity_id").agg(invoices=("invoice_no", "nunique"), alerts=("alert", "sum"),
                                      max_score=("score", "max"), alert_value_usd=("alert_value", "sum"))
    g["alert_share"] = (g["alerts"] / g["invoices"]).round(3)
    return ent.merge(g.reset_index(), on="entity_id", how="left").fillna(
        {"invoices": 0, "alerts": 0, "max_score": 0.0, "alert_value_usd": 0.0, "alert_share": 0.0}
    ).sort_values(["alerts", "max_score"], ascending=False).reset_index(drop=True)
