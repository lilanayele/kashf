"""External validation set and its scoring (no network, no raw data)."""

from pathlib import Path

import numpy as np
import pandas as pd

from kashf.baselines import gfi_gap, iqr_filter, iqr_price_scores, top_k
from kashf.external import evaluate, load_set

ROOT = Path(__file__).resolve().parent.parent


def test_external_set_has_sources():
    d = pd.read_csv(ROOT / "data/external_validation.csv", dtype=str)
    assert len(d) >= 5
    assert d["url"].str.startswith("https://").all() and d["publisher"].notna().all()
    assert set(d["kind"]) <= {"mirror_discrepancy", "transit_hub", "partner_not_reporting"}


def _pairs():
    rows = []
    for i, (p, y, hs, s) in enumerate([("MLI", 2021, "710812", 9.0), ("GHA", 2022, "710812", 1.5),
                                       ("FRA", 2022, "851713", 5.0), ("DEU", 2021, "851713", 0.1)]):
        rows.append({"direction": "uae_import", "partner_iso": p, "year": y, "hs6": hs, "rule_score": s,
                     "rule_flag": s >= 1, "if_score": 0.5, "if_flag": False, "value_imp": 1e6 * (i + 1),
                     "value_exp": 1e5, "qty_imp": 10.0, "qty_exp": 10.0})
    return pd.DataFrame(rows)


def test_evaluate_ranks_documented_pairs():
    ext = pd.DataFrame([{"id": "X", "kind": "mirror_discrepancy", "hs6": "710812", "partner_iso": "MLI", "year": 2021,
                         "direction": "uae_import", "source": "t"},
                        {"id": "Y", "kind": "transit_hub", "hs6": "710812", "partner_iso": "TGO", "year": 2022,
                         "direction": "uae_import", "source": "t"}])
    r = evaluate(_pairs(), ext, 0.1)
    assert r["documented_keys"] == 2 and r["documented_keys_in_data"] == 1
    k = r["methods"]["kashf_rules"]
    assert k["keys_flagged"] == 1 and k["per_key"][0]["best_rank"] == 1


def test_load_set_expands_lists():
    e = load_set(ROOT / "data/external_validation.csv")
    assert {"hs6", "partner_iso", "year"} <= set(e.columns) and e["year"].between(2000, 2030).all()


def test_baselines():
    p = _pairs()
    g = gfi_gap(p, 0.1)
    assert g[3] > g[0] > 0
    assert top_k(np.array([0.0, 3.0, 1.0]), 1).tolist() == [False, True, False]
    q = p.assign(uv_imp=[100.0, 1.0, 1.0, 1.0], uv_exp=[1.0] * 4, uv_log_q1=[0.0] * 4, uv_log_q3=[np.log(2)] * 4)
    s = iqr_filter(q)
    assert s[0] > 0 and s[1] == 0
    inv = pd.DataFrame({"invoice_no": ["a", "b"], "hs6": ["851713"] * 2, "unit_price_usd": [180.0, 1800.0]})
    ref = pd.DataFrame({"hs6": ["851713"], "ref_usd": [180.0], "log_mad": [0.3]})
    sc = iqr_price_scores(inv, ref)
    assert sc["a"] == 0 and sc["b"] > 0
