import math

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from kashf import calibrate, reference
from kashf.config import Settings
from kashf.detectors import (document_detector, graph_detector, link_graph, price_detector,
                             route_detector, run_all)
from kashf.generate import Config, generate
from kashf.pipeline import analyse
from kashf.report import invoice_case, to_html
from kashf.scoring import score_invoices

REF = reference.default_table()


@pytest.fixture(scope="module")
def world():
    return generate(Config(seed=42, n_invoices=3000))


def inv(**kw):
    base = dict(invoice_no="INV-1", date="2025-03-01", seller_id="A", buyer_id="B", hs6="851713",
                description="Smartphones", quantity=100.0, unit="unit", unit_price_usd=180.0, value_usd=18000.0,
                declared_weight_kg=35.0, origin="AE", destination="IN", route="AE>IN", doc_no="BL-1")
    base.update(kw)
    return pd.DataFrame([base])


def doc(**kw):
    base = dict(doc_no="BL-1", doc_type="bill_of_lading", carrier_or_vessel="MSC Aurora", departure_date="2025-03-05",
                quantity=100.0, gross_weight_kg=35.0, port_load="AE", port_discharge="IN")
    base.update(kw)
    return pd.DataFrame([base])


PACK = pd.DataFrame([{"invoice_no": "INV-1", "quantity": 100.0, "net_weight_kg": 33.0}])


# ---------------------------------------------------------------- generator
def test_generator_is_reproducible_and_labelled(world):
    again = generate(Config(seed=42, n_invoices=3000))
    pd.testing.assert_frame_equal(world["invoices"], again["invoices"])
    typ = set(world["labels"]["typology"])
    assert {"none", "over_invoicing", "phantom_shipment", "circular_trading", "shell_cluster"} <= typ


def test_labels_are_not_in_invoice_table(world):
    assert "typology" not in world["invoices"].columns


# ---------------------------------------------------------------- price
def test_price_flags_over_and_under_with_numbers():
    s = Settings()
    hi = price_detector(inv(unit_price_usd=1800.0), REF, s)
    lo = price_detector(inv(unit_price_usd=18.0), REF, s)
    ok = price_detector(inv(unit_price_usd=190.0), REF, s)
    assert hi[0].rule == "over_priced" and "10.00×" in hi[0].evidence
    assert lo[0].rule == "under_priced" and lo[0].value < 0
    assert ok == []


# ---------------------------------------------------------------- route
def test_route_loop_and_high_risk():
    s = Settings()
    rules = {x.rule for x in route_detector(inv(route="AE>OM>IN>OM>XA", destination="XA"), s)}
    assert {"route_loop", "high_risk_party"} <= rules
    assert route_detector(inv(route="AE>AE", destination="AE"), s) == []   # domestic is not a loop


# ---------------------------------------------------------------- documents
def test_clean_documents_raise_nothing():
    assert document_detector(inv(), doc(), PACK, REF, Settings()) == []


def test_missing_and_reused_documents():
    two = pd.concat([inv(), inv(invoice_no="INV-2", buyer_id="C")])
    pk = pd.concat([PACK, PACK.assign(invoice_no="INV-2")])
    rules = [x.rule for x in document_detector(two, doc(), pk, REF, Settings())]
    assert rules.count("doc_reused") == 2
    miss = document_detector(inv(doc_no=None), doc(), PACK, REF, Settings())
    assert miss[0].rule == "no_transport_doc"


def test_phantom_dates_weight_and_unit_weight():
    s = Settings()
    r = {x.rule for x in document_detector(inv(), doc(departure_date="2025-10-01", carrier_or_vessel="UNKNOWN",
                                                       gross_weight_kg=3.0), PACK, REF, s)}
    assert {"implausible_dates", "unknown_vessel", "weight_mismatch"} <= r
    heavy = document_detector(inv(declared_weight_kg=900.0), doc(gross_weight_kg=900.0), PACK, REF, s)
    assert any(x.rule == "implausible_unit_weight" for x in heavy)


# ---------------------------------------------------------------- graph
def test_shared_director_links_parties_but_business_centre_does_not():
    ents = pd.DataFrame([
        {"entity_id": "A", "director_id": "P1", "phone": "1", "address": "x", "bank_account": "a"},
        {"entity_id": "B", "director_id": "P1", "phone": "2", "address": "y", "bank_account": "b"},
        *[{"entity_id": f"Z{i}", "director_id": f"Q{i}", "phone": f"z{i}", "address": "Business Centre 1",
           "bank_account": f"z{i}"} for i in range(8)],
    ])
    g, hubs = link_graph(ents, Settings())
    assert g.has_edge("A", "B") and not g.has_edge("Z0", "Z1")
    assert any("Business Centre 1" in h for h in hubs)
    sig = graph_detector(inv(seller_id="A", buyer_id="B"), ents, Settings())
    assert sig[0].rule == "linked_parties" and "P1" in sig[0].evidence


def test_circular_trade_found():
    rows = [inv(invoice_no=f"I{i}", seller_id=s, buyer_id=b, date=d)
            for i, (s, b, d) in enumerate([("A", "B", "2025-01-01"), ("B", "C", "2025-01-10"), ("C", "A", "2025-01-20")])]
    ents = pd.DataFrame([{"entity_id": e, "director_id": e, "phone": e, "address": e, "bank_account": e} for e in "ABC"])
    sig = graph_detector(pd.concat(rows), ents, Settings())
    assert sorted(x.invoice_no for x in sig if x.rule == "circular_trade") == ["I0", "I1", "I2"]


# ---------------------------------------------------------------- scoring + calibration
def test_noisy_or_and_threshold():
    sig = pd.DataFrame([{"invoice_no": "INV-1", "detector": "price", "rule": "over_priced", "strength": 0.5,
                         "evidence": "e", "value": 5.0},
                        {"invoice_no": "INV-1", "detector": "documents", "rule": "weight_mismatch", "strength": 0.5,
                         "evidence": "f", "value": math.nan}])
    sc = score_invoices(inv(), sig, Settings(alert_threshold=0.7))
    assert sc.loc[0, "score"] == pytest.approx(0.75) and bool(sc.loc[0, "alert"])


def test_calibration_is_smoothed_precision():
    sig = pd.DataFrame({"invoice_no": ["a", "b", "c", "d"], "detector": "documents", "rule": "no_transport_doc",
                        "strength": 0.7, "evidence": "", "value": math.nan})
    lab = pd.DataFrame({"invoice_no": list("abcd"), "typology": ["phantom_shipment", "none", "none", "none"]})
    assert calibrate.fit(sig, lab)["no_transport_doc"] == pytest.approx((1 + 1) / (4 + 2))
    assert calibrate.rule_key("over_priced", 4.4) == "over_priced|z4-5"


# ---------------------------------------------------------------- end to end
def test_pipeline_finds_planted_cases(world):
    r = analyse({k: v for k, v in world.items() if k != "labels"})
    lab = world["labels"].set_index("invoice_no")["typology"]
    alerts = r.invoices[r.invoices["alert"]]
    hit = alerts["invoice_no"].map(lab)
    assert (hit != "none").mean() > 0.6          # most alerts are real
    for t in ("circular_trading", "shell_cluster", "multiple_invoicing", "misdescription"):
        assert set(lab[lab == t].index) <= set(alerts["invoice_no"]) | set(), t


def test_case_summary_and_html(world):
    r = analyse({k: v for k, v in world.items() if k != "labels"})
    top = r.invoices.iloc[0]["invoice_no"]
    md = invoice_case(r, top)
    assert "Red flags found" in md and "STR" in md
    assert "<h1>" in to_html(md)


def test_api(tmp_path, world):
    from kashf.api import create_app
    from kashf.generate import save
    save(world, tmp_path)
    c = TestClient(create_app(tmp_path))
    s = c.get("/api/summary").json()
    assert s["invoices"] == len(world["invoices"]) and s["alerts"] > 0
    a = c.get("/api/alerts?limit=5").json()
    d = c.get(f"/api/invoice/{a[0]['invoice_no']}").json()
    assert d["signals"] and "typology" not in d["invoice"]
    assert c.get(f"/api/network/{d['invoice']['seller_id']}").json()["nodes"]
    assert "Case summary" in c.get(f"/api/case/{a[0]['invoice_no']}").text
