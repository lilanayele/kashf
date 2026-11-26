"""Published-method baselines, implemented from their published descriptions.

Macro layer (mirror pairs, kashf.macro):
  * gfi_gap      GFI-style partner-country value gap (Global Financial Integrity, "Trade misinvoicing:
                 mirror analysis methodology", https://gfintegrity.org/research/trade-misinvoicing-mirror-analysis/):
                 keep pairs where both sides report non-zero values and volumes in the same unit; gross
                 misinvoicing = |importer value on FOB basis - exporter value| in USD. Differences from GFI:
                 a flat CIF/FOB margin instead of GFI's regression, and no volume-discrepancy weighting
                 (GFI's weighting formula is not given in the page text). GFI publishes an aggregate
                 estimate, not a flag; as a screen we rank pairs by the dollar gap and flag the top k.
  * iqr_filter   Interquartile-range price filter (de Boyrie, Pak & Zdanowicz, J. Financial Crime
                 12(2):123-130, doi:10.1108/13590790510624972; Zdanowicz, Rev. Law Econ. 5(2), 2009):
                 a unit price is abnormal when it lies outside the inter-quartile range of prices for the
                 same product. Here: the importer's or exporter's unit value vs the quartiles of all
                 reporters' exports of that HS6 in that year. Score = distance outside [Q1, Q3] in IQR units.

Invoice layer (kashf.evaluate): iqr_price_scores applies the same filter to invoice unit prices
against the reference table. For a log-normal price distribution Q1/Q3 = median * exp(-/+ 0.6745 sigma),
and sigma = 1.4826 * MAD, so the quartiles are median * exp(-/+ log_mad) (0.6745 * 1.4826 = 1.000).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def top_k(score: np.ndarray, k: int) -> np.ndarray:
    s = np.nan_to_num(np.asarray(score, dtype=float), nan=-np.inf)
    flag = np.zeros(len(s), dtype=bool)
    if k > 0:
        flag[np.argsort(-s, kind="stable")[:k]] = True
    return flag & np.isfinite(s) & (s > 0)


def gfi_gap(p: pd.DataFrame, cif_fob: float) -> np.ndarray:
    ok = (p["value_imp"] > 0) & (p["value_exp"] > 0) & (p["qty_imp"] > 0) & (p["qty_exp"] > 0)
    gap = (p["value_imp"] / (1 + cif_fob) - p["value_exp"]).abs()
    return np.where(ok, gap, 0.0)


def iqr_filter(p: pd.DataFrame) -> np.ndarray:
    if "uv_log_q1" not in p:
        raise ValueError("pairs lack uv_log_q1/uv_log_q3; rebuild them with kashf.macro (global quartiles)")
    q1, q3 = p["uv_log_q1"].values, p["uv_log_q3"].values
    iqr = np.maximum(q3 - q1, 1e-6)
    out = np.zeros(len(p))
    for side in ("imp", "exp"):
        luv = np.log(p[f"uv_{side}"].values.astype(float))
        d = np.maximum(luv - q3, q1 - luv) / iqr
        out = np.fmax(out, np.where(np.isfinite(d), d, 0.0))
    return np.maximum(out, 0.0)


def iqr_price_scores(inv: pd.DataFrame, ref: pd.DataFrame) -> pd.Series:
    r = ref.set_index("hs6")
    med = np.log(inv["hs6"].map(r["ref_usd"]).astype(float))
    lm = inv["hs6"].map(r["log_mad"]).astype(float).clip(lower=1e-6)
    d = (np.log(inv["unit_price_usd"].astype(float)) - med).abs() - lm   # distance outside [Q1, Q3] in log units
    return pd.Series(np.maximum(d / (2 * lm), 0.0).fillna(0.0).values, index=inv["invoice_no"])
