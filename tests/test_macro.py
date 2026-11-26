"""Tests for kashf.comtrade and kashf.macro on a tiny HAND-MADE fixture (no network).

The fixture imitates the shape of Comtrade's getFinalData output. Its numbers are invented
for testing only and are never used for results.
"""

import json
import math

import numpy as np
import pandas as pd
import pytest

from kashf import comtrade, macro

CFG = {"cif_fob_factor": 0.10, "min_flow_usd": 100_000, "gap_threshold": math.log(1.5),
       "weight_gap_threshold": math.log(1.5), "uv_z_threshold": 3.0, "iforest_trees": 50,
       "iforest_contamination": 0.1, "injection_sizes": [0.1, 1.0], "injection_share": 0.2,
       "injection_repeats": 2}
PARTNERS = [(276, "DEU"), (356, "IND"), (156, "CHN"), (682, "SAU"), (826, "GBR"), (840, "USA"),
            (392, "JPN"), (410, "KOR"), (586, "PAK"), (50, "BGD"), (764, "THA"), (704, "VNM")]
HS = {"851713": ("u", 200.0, 0.4), "710813": ("kg", 60000.0, 2.0)}   # unit, price, kg per unit (phones)


def _row(rep, rep_iso, par, par_iso, flow, hs, value, qty, wgt, year):
    return {"period": year, "reporterCode": rep, "reporterISO": rep_iso, "reporterDesc": rep_iso,
            "partnerCode": par, "partnerISO": par_iso, "partnerDesc": par_iso, "flowCode": flow,
            "cmdCode": hs, "cmdDesc": hs, "primaryValue": value, "qty": qty, "qtyUnitAbbr": HS[hs][0],
            "netWgt": wgt, "isQtyEstimated": False, "isNetWgtEstimated": False, "isReported": True,
            "partner2Code": 0, "customsCode": "C00", "motCode": 0}


@pytest.fixture()
def raw_frames():
    rng = np.random.default_rng(0)
    uae, mir, world = [], [], []
    for year in (2022, 2023):
        for hs, (unit, price, kpu) in HS.items():
            for code, iso in PARTNERS + [(124, "CAN"), (36, "AUS"), (250, "FRA")]:
                q = 1e4 * rng.uniform(1, 5)
                p = price * np.exp(rng.normal(0, 0.2))
                w = q * kpu if unit == "u" else q
                world.append(_row(code, iso, 0, "W00", "X", hs, q * p, q if unit == "u" else w, w, year))
            for code, iso in PARTNERS:
                q = 5e3 * rng.uniform(1, 3)
                v = q * price * np.exp(rng.normal(0, 0.05))
                w = q * kpu if unit == "u" else q
                qq = q if unit == "u" else w
                # UAE exports, partner imports (CIF ~ +10%)
                uae.append(_row(784, "ARE", code, iso, "X", hs, 0.6 * v, 0.6 * qq, 0.6 * w, year))
                uae.append(_row(784, "ARE", code, iso, "RX", hs, 0.4 * v, 0.4 * qq, 0.4 * w, year))
                gap = 3.0 if (code == 276 and hs == "851713" and year == 2023) else 1.0   # one planted gap
                mir.append(_row(code, iso, 784, "ARE", "M", hs, 1.1 * v * gap, qq, w, year))
                # UAE imports from partner, partner exports to UAE
                uae.append(_row(784, "ARE", code, iso, "M", hs, 1.1 * v, qq, w, year))
                mir.append(_row(code, iso, 784, "ARE", "X", hs, v, qq, w, year))
    return {"uae": pd.DataFrame(uae), "mirror": pd.DataFrame(mir), "world": pd.DataFrame(world)}


@pytest.fixture()
def flows(raw_frames, tmp_path):
    for name, df in raw_frames.items():
        df.to_parquet(tmp_path / f"{name}_2023.parquet", index=False)
    return comtrade.load_raw(tmp_path)


def test_mirror_gap_and_planted_pair(flows):
    pairs = macro.build_pairs(flows, 0.10)
    assert set(pairs["direction"]) == {"uae_export", "uae_import"}
    ex = pairs[pairs["direction"] == "uae_export"]
    planted = ex[(ex["partner"] == 276) & (ex["hs6"] == "851713") & (ex["year"] == 2023)]
    assert len(planted) == 1
    # X + RX summed on the UAE side; partner reports 3x the CIF-adjusted value
    assert planted["mirror_gap"].iloc[0] == pytest.approx(math.log(3.0), abs=1e-9)
    others = ex.drop(planted.index)
    assert others["mirror_gap"].abs().max() < 1e-9       # CIF factor exactly cancels in the fixture
    assert ex["rx_share"].round(6).eq(0.4).all()


def test_unit_value_z_uses_global_distribution(flows):
    dist = comtrade.global_distribution(flows, min_reporters=5)
    assert set(dist["basis"]) == {"unit", "kg"}
    pairs = macro.add_unit_value_z(macro.build_pairs(flows), dist)
    assert pairs["uv_z_exp"].notna().all()
    assert pairs["uv_z_exp"].abs().median() < 2           # fixture prices are near the global median


def test_rules_flag_planted_pair_and_explain(flows):
    dist = comtrade.global_distribution(flows)
    pairs = macro.eligible(macro.add_unit_value_z(macro.build_pairs(flows), dist), CFG["min_flow_usd"])
    r = macro.rules(pairs, CFG)
    top = r.sort_values("rule_score", ascending=False).iloc[0]
    assert (top["partner"], top["hs6"], top["year"], top["direction"]) == (276, "851713", 2023, "uae_export")
    assert top["rule_flag"]
    text = macro.explain(top, CFG)
    assert "DEU reports imports from UAE" in text and "3.00x" in text
    assert "free zones" in macro.innocent(top)          # rx_share 0.4 is below the 50% re-export note


def test_injection_shifts_gap_and_recall_grows_with_size(flows):
    dist = comtrade.global_distribution(flows)
    pairs = macro.eligible(macro.add_unit_value_z(macro.build_pairs(flows), dist), CFG["min_flow_usd"])
    q, y = macro.inject(pairs, 1.0, 0.25, np.random.default_rng(1), 0.10)
    d = (q["mirror_gap"] - pairs["mirror_gap"]).abs()
    assert np.allclose(d[y], math.log(2.0)) and np.allclose(d[~y], 0)
    zshift = (q["uv_z_imp"] - pairs["uv_z_imp"]).abs()
    assert np.allclose(zshift[y], math.log(2.0) / (macro.MAD_K * pairs.loc[y, "uv_log_mad"]))
    summ = macro.summarise_injection(macro.evaluate_injection(pairs, CFG))
    rr = summ[summ["method"] == "rules"].set_index("size")["recall"]
    assert rr[1.0] >= rr[0.1] and rr[1.0] == 1.0          # 100% distortion is always above ln(1.5)


def test_fetch_caches_logs_retries_and_redacts(tmp_path, monkeypatch):
    monkeypatch.setattr(comtrade, "RAW", tmp_path)
    monkeypatch.setattr(comtrade, "CALL_LOG", tmp_path / "calls.jsonl")
    monkeypatch.setattr(comtrade, "QUOTA", tmp_path / ".quota.json")
    monkeypatch.setattr(comtrade.time, "sleep", lambda s: None)
    key = "SECRETKEY123"
    calls = {"n": 0}

    def flaky(k, **params):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError(f"HTTP 429: too many requests for url ?subscription-key={k}")
        return pd.DataFrame([_row(784, "ARE", 276, "DEU", "X", "851713", 1e6, 5e3, 2e3, 2023)])

    cfg = {"daily_call_budget": 10, "max_retries": 3, "seconds_between_calls": 0}
    df = comtrade.fetch("uae_2023", period="2023", cmd="851713", flow="X", reporter="784", partner=None,
                        key=key, cfg=cfg, caller=flaky)
    assert len(df) == 1 and calls["n"] == 2
    again = comtrade.fetch("uae_2023", period="2023", cmd="851713", flow="X", reporter="784", partner=None,
                           key=key, cfg=cfg, caller=flaky)
    assert len(again) == 1 and calls["n"] == 2              # served from cache, no new call
    logtxt = (tmp_path / "calls.jsonl").read_text()
    assert key not in logtxt and "***" in logtxt
    assert [json.loads(x)["status"] for x in logtxt.splitlines()] == ["error", "ok"]


def test_fetch_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setattr(comtrade, "RAW", tmp_path)
    monkeypatch.setattr(comtrade, "CALL_LOG", tmp_path / "calls.jsonl")
    monkeypatch.setattr(comtrade, "QUOTA", tmp_path / ".quota.json")

    def denied(k, **params):
        raise RuntimeError(f"HTTP 401: bad key {k}")

    with pytest.raises(comtrade.ComtradeError) as e:
        comtrade.fetch("x", period="2023", cmd="1", flow="X", reporter="784", partner=None, key="K9",
                       cfg={"max_retries": 3, "seconds_between_calls": 0}, caller=denied)
    assert "K9" not in str(e.value)
    with pytest.raises(comtrade.ComtradeError):
        comtrade.fetch("y", period="2023", cmd="1", flow="X", reporter="784", partner=None, key="K9",
                       cfg={"daily_call_budget": 0}, caller=denied)


def test_reference_never_falls_back(flows):
    with pytest.raises(comtrade.ComtradeError, match="not enough real Comtrade data"):
        comtrade.build_reference(flows, {"min_reporters_for_reference": 5})
    ref = comtrade.build_reference(flows, {"min_reporters_for_reference": 5}, allow_partial=True)
    assert set(ref["hs6"]) == {"851713", "710813"}           # only codes with data, no illustrative rows
    phones = ref.set_index("hs6").loc["851713"]
    assert phones["unit"] == "unit" and 150 < phones["ref_usd"] < 260
    assert phones["kg_per_unit"] == pytest.approx(0.4)


def test_macro_api(flows, tmp_path):
    from fastapi.testclient import TestClient
    from kashf.api import create_app
    dist = comtrade.global_distribution(flows)
    pairs = macro.eligible(macro.add_unit_value_z(macro.build_pairs(flows), dist), CFG["min_flow_usd"])
    r = macro.rules(pairs, CFG)
    f, _, _ = macro.iforest(pairs, CFG)
    r.assign(if_flag=f["if_flag"]).to_csv(tmp_path / "flags.csv", index=False)
    c = TestClient(create_app(macro_dir=tmp_path))
    o = c.get("/api/macro/options").json()
    assert "851713" in o["hs6"] and o["flagged"] >= 1
    d = c.get("/api/macro", params={"hs6": "851713", "partner": 276}).json()
    flagged = [x for x in d["rows"] if x["rule_flag"]]
    assert flagged and "DEU reports imports from UAE" in flagged[0]["why"]
    assert TestClient(create_app(macro_dir=tmp_path / "none")).get("/api/macro/options").status_code == 404
