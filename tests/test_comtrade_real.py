"""kashf.comtrade on REAL UN Comtrade responses (trimmed, offline).

tests/fixtures/comtrade/ holds small slices of real 2023 API responses (HS 851713 smartphones,
710813 semi-manufactured gold, 940360 wooden furniture), made by scripts/make_fixtures.py.
No test here calls the live API.
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kashf import comtrade, macro

FIX = Path(__file__).parent / "fixtures" / "comtrade"


@pytest.fixture()
def raw(tmp_path, monkeypatch):
    monkeypatch.setattr(comtrade, "RAW", tmp_path)
    monkeypatch.setattr(comtrade, "CALL_LOG", tmp_path / "calls.jsonl")
    done = comtrade.import_saved(sorted(FIX.glob("kashf_*.json")))
    return tmp_path, done


def test_fixtures_are_small_real_and_keyless():
    files = sorted(FIX.glob("kashf_*.json"))
    assert {f.stem for f in files} == {"kashf_uae_2023", "kashf_mirror_2023", "kashf_world_2023"}
    for f in files:
        txt = f.read_text()
        assert "subscription" not in txt.lower()
        rows = json.loads(txt)["data"]
        assert 0 < len(rows) < 500
        assert set(comtrade.REQUIRED) <= set(rows[0])


def test_import_matches_real_schema_and_logs(raw):
    path, done = raw
    assert done == {"uae_2023": 83, "mirror_2023": 53, "world_2023": 120}
    df = pd.read_parquet(path / "uae_2023.parquet")
    assert set(df["flowCode"]) <= {"X", "RX", "M", "RM"}
    assert df["cmdCode"].str.len().eq(6).all()
    assert set(df["partner2Code"]) == {0} and set(df["customsCode"]) == {"C00"}
    log = [json.loads(x) for x in (path / "calls.jsonl").read_text().splitlines()]
    assert {r["query"] for r in log} == set(done) and all(r["via"] == "import" for r in log)


def test_estimated_quantities_and_odd_units_are_excluded(raw):
    path, _ = raw
    flows = comtrade.load_raw(path)
    raw_rows = pd.concat([pd.read_parquet(f) for f in path.glob("*.parquet")])
    est = raw_rows["isQtyEstimated"].astype(bool) & raw_rows["qty"].notna()
    assert est.sum() > 0                                   # the real data does contain estimates
    assert flows["qty"].notna().sum() <= (~est).sum()      # ... and none of them survive
    for hs, g in flows[flows["qty"].notna()].groupby("hs6"):
        assert g["qty_unit"].str.lower().nunique() == 1    # one quantity unit per HS6 after harmonising


def test_reference_from_real_rows_is_plausible(raw):
    path, _ = raw
    ref = comtrade.build_reference(comtrade.load_raw(path), {"min_reporters_for_reference": 5},
                                   allow_partial=True).set_index("hs6")
    assert set(ref.index) == {"851713", "710813", "940360"}        # others left out, never filled in
    assert ref.loc["851713", "unit"] == "unit" and 50 < ref.loc["851713", "ref_usd"] < 1500
    assert ref.loc["710813", "unit"] == "kg" and 10_000 < ref.loc["710813", "ref_usd"] < 100_000
    assert (ref["log_mad"] >= 0.05).all()


def test_real_mirror_pairs_have_both_directions_and_finite_gaps(raw):
    path, _ = raw
    flows = comtrade.load_raw(path)
    pairs = macro.add_unit_value_z(macro.build_pairs(flows), comtrade.global_distribution(flows, 5))
    assert set(pairs["direction"]) == {"uae_export", "uae_import"}
    assert np.isfinite(pairs["mirror_gap"]).all()
    assert not (pairs["mirror_gap"] == 0).all()
    r = macro.rules(pairs, {"baseline": "relative", "gap_z_threshold": 3.0, "gap_threshold": math.log(1.5),
                            "weight_gap_threshold": math.log(1.5), "uv_z_threshold": 3.0})
    assert r["rule_score"].notna().all()


def test_postprocess_rejects_a_changed_schema():
    bad = pd.DataFrame([{"period": 2023, "reporterCode": 784, "cmdCode": "851713"}])
    with pytest.raises(comtrade.ComtradeError, match="schema changed"):
        comtrade._postprocess(bad, "x")


def _fixture_rows(name):
    return json.loads((FIX / f"kashf_{name}.json").read_text())["data"]


def _write(tmp, name, rows):
    p = tmp / f"kashf_{name}.json"
    p.write_text(json.dumps({"query": name, "data": rows}))
    return p


def test_empty_response_is_cached_and_skipped(raw, tmp_path):
    path, _ = raw
    comtrade.import_saved([_write(tmp_path, "uae_2024", [])])      # the UAE had not reported 2024
    assert pd.read_parquet(path / "uae_2024.parquet").empty
    flows = comtrade.load_raw(path)
    assert 2024 not in set(flows.loc[flows["source"] == "uae", "year"])


def test_all_empty_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setattr(comtrade, "RAW", tmp_path)
    monkeypatch.setattr(comtrade, "CALL_LOG", tmp_path / "calls.jsonl")
    comtrade.import_saved([_write(tmp_path, "uae_2023", [])])
    with pytest.raises(comtrade.ComtradeError, match="empty"):
        comtrade.load_raw(tmp_path)


def test_missing_quantities_fall_back_to_weight_or_are_left_out(raw, tmp_path):
    path, _ = raw
    rows = _fixture_rows("world_2023")
    for r in rows:
        if r["cmdCode"] == "851713":
            r["qty"] = None                       # smartphones priced per unit: no quantity at all
    comtrade.import_saved([_write(tmp_path, "world_2023", rows)])
    flows = comtrade.load_raw(path)
    with pytest.raises(comtrade.ComtradeError, match="851713"):
        comtrade.build_reference(flows, {"min_reporters_for_reference": 5})
    ref = comtrade.build_reference(flows, {"min_reporters_for_reference": 5}, allow_partial=True)
    assert "851713" not in set(ref["hs6"]) and "710813" in set(ref["hs6"])   # kg-priced gold still works


def test_suppressed_code_is_left_out_not_filled(raw, tmp_path):
    path, _ = raw
    # a reporter that suppresses HS6 detail simply has no rows for that code
    rows = [r for r in _fixture_rows("world_2023") if r["cmdCode"] != "940360"]
    comtrade.import_saved([_write(tmp_path, "world_2023", rows)])
    ref = comtrade.build_reference(comtrade.load_raw(path), {"min_reporters_for_reference": 5},
                                   allow_partial=True)
    assert "940360" not in set(ref["hs6"])
    assert not (ref["n_reporter_years"] == 0).any()


def test_persistent_rate_limit_gives_up_without_leaking_key(tmp_path, monkeypatch):
    monkeypatch.setattr(comtrade, "RAW", tmp_path)
    monkeypatch.setattr(comtrade, "CALL_LOG", tmp_path / "calls.jsonl")
    monkeypatch.setattr(comtrade, "QUOTA", tmp_path / ".quota.json")
    sleeps = []
    monkeypatch.setattr(comtrade.time, "sleep", sleeps.append)

    def limited(k, **params):
        raise RuntimeError(f'HTTP 429: {{"statusCode": 429, "message": "Rate limit is exceeded"}} key={k}')

    with pytest.raises(comtrade.ComtradeError, match="429") as e:
        comtrade.fetch("uae_2023", period="2023", cmd="851713", flow="X", reporter="784", partner=None,
                       key="SECRET42", cfg={"max_retries": 3, "seconds_between_calls": 1}, caller=limited)
    assert "SECRET42" not in str(e.value)
    assert sleeps == [2.0, 4.0]                     # exponential backoff between the 3 attempts
    assert "SECRET42" not in (tmp_path / "calls.jsonl").read_text()


def test_re_exports_reported_both_ways(raw):
    path, _ = raw
    flows = comtrade.load_raw(path)
    pairs = macro.build_pairs(flows)
    ex = pairs[pairs["direction"] == "uae_export"]
    assert (ex["value_exp_x_only"] <= ex["value_exp"] + 1e-6).all()
    both = ex.dropna(subset=["mirror_gap_x_only"])
    assert (both["mirror_gap_x_only"] >= both["mirror_gap"] - 1e-9).all()   # removing RX can only raise the gap
    assert pairs.loc[pairs["direction"] == "uae_import", "mirror_gap_x_only"].isna().all()
