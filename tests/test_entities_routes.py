"""Fuzzy entity resolution, U-turn rule and the new generator typologies."""

import pandas as pd

from kashf.config import Settings
from kashf.detectors import link_graph, route_detector
from kashf.entities import links, normalise_address, normalise_name, normalise_phone
from kashf.generate import Config, generate


def test_normalisers():
    assert normalise_name("Gulf Star Gen. Trdg L.L.C") == normalise_name("Gulf Star General Trading LLC") \
        == "gulf star general trading"
    assert normalise_name("Blue-Dhow Comm. FZE") == "blue dhow commodities"
    assert normalise_phone("00971501234567") == normalise_phone("+971 50 123 4567") \
        == normalise_phone("+971-50-1234567") == "971501234567"
    assert normalise_address("Off. 312 Al-Qusais Ind. Area 4, Dubai") == \
        normalise_address("OFFICE 312, AL QUSAIS INDUSTRIAL AREA 4 DUBAI")


def _ent(rows):
    return pd.DataFrame(rows, columns=["entity_id", "name", "country", "address", "phone", "director_id",
                                       "bank_account"])


def test_formatted_phone_links_only_when_fuzzy():
    e = _ent([("E1", "Alpha Trading LLC", "AE", "Unit 1, Building 2, Dubai", "+971 50 123 4567", "P1", "A1"),
              ("E2", "Beta Metals FZE", "AE", "Unit 9, Building 8, Dubai", "00971501234567", "P2", "A2")])
    assert links(e, "exact")[0] == []
    lk = links(e, "fuzzy")[0]
    assert len(lk) == 1 and "phone" in lk[0][2]


def test_similar_name_alone_does_not_link():
    # same trading name, different addresses: common for unrelated firms
    e = _ent([("E1", "Gulf Star General Trading LLC", "AE", "Unit 5, Building 10, Dubai", "+971 50 111 1111", "P1", "A1"),
              ("E2", "Gulf Star Gen. Trdg FZE", "AE", "Unit 77, Building 300, Dubai", "+971 55 222 2222", "P2", "A2")])
    assert links(e, "fuzzy")[0] == []


def test_similar_name_and_address_links():
    e = _ent([("E1", "Gulf Star General Trading LLC", "AE", "Office 312, Al Qusais Industrial Area 4, Dubai",
               "+971 50 111 1111", "P1", "A1"),
              ("E2", "Gulf-Star Gen. Trdg F.Z.E", "AE", "Off 312 Al Qusais Ind Area 4 Dubai UAE", "+971 55 222 2222", "P2", "A2")])
    lk = links(e, "fuzzy")[0]
    assert len(lk) == 1 and "near-identical" in lk[0][2]


def test_u_turn_rule():
    inv = pd.DataFrame([
        {"invoice_no": "X1", "date": "2025-01-01", "seller_id": "U1", "buyer_id": "F1", "hs6": "851713",
         "quantity": 100, "unit_price_usd": 200.0, "origin": "AE", "destination": "IN", "route": "AE>IN"},
        {"invoice_no": "M1", "date": "2025-02-01", "seller_id": "F1", "buyer_id": "U2", "hs6": "851713",
         "quantity": 101, "unit_price_usd": 380.0, "origin": "IN", "destination": "AE", "route": "IN>AE"},
        {"invoice_no": "M2", "date": "2025-09-01", "seller_id": "F1", "buyer_id": "U2", "hs6": "851713",
         "quantity": 100, "unit_price_usd": 380.0, "origin": "IN", "destination": "AE", "route": "IN>AE"},
    ])
    sig = route_detector(inv, Settings(high_risk=("IR",)))
    hit = {x.invoice_no for x in sig if x.rule == "u_turn"}
    assert hit == {"X1", "M1"}            # M2 is outside u_turn_days


def test_generator_plants_new_typologies_and_fuzzy_recovers_name_variants():
    t = generate(Config(seed=3, n_invoices=4000))
    lab = t["labels"].set_index("invoice_no")["typology"]
    for k in ("transshipment_high_risk", "u_turn", "name_variant"):
        assert (lab == k).sum() > 0
    inv = t["invoices"].set_index("invoice_no")
    nv = inv.loc[lab.index[lab == "name_variant"]]
    for mode, expect_most in (("exact", False), ("fuzzy", True)):
        g, _ = link_graph(t["entities"], Settings(entity_resolution=mode))
        import networkx as nx
        comp = {n: i for i, c in enumerate(nx.connected_components(g)) for n in c}
        same = (nv["seller_id"].map(comp) == nv["buyer_id"].map(comp)).mean()
        assert (same > 0.8) == expect_most
