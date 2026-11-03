"""The four Kashf detectors.

Each detector returns a list of Signal rows:
    invoice_no, detector, rule, strength (0..1), evidence (plain-English, with the numbers)

Signals are deliberately explainable: every one names the values that triggered it,
so an analyst can confirm or dismiss it without rerunning anything.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict, dataclass

import networkx as nx
import numpy as np
import pandas as pd

from kashf.config import Settings


@dataclass
class Signal:
    invoice_no: str
    detector: str
    rule: str
    strength: float
    evidence: str
    value: float = float("nan")   # the statistic behind the signal (e.g. robust z), used for calibration


def _money(x: float) -> str:
    return f"${x:,.2f}" if x < 100 else f"${x:,.0f}"


# =========================================================== 1. price benchmark
def price_detector(inv: pd.DataFrame, ref: pd.DataFrame, s: Settings) -> list[Signal]:
    """Robust z-score of the declared unit price against reference unit values:
        z = (ln p - ln median_ref) / (1.4826 * MAD(ln p_ref))"""
    r = ref.set_index("hs6")
    out: list[Signal] = []
    for row in inv.itertuples(index=False):
        if row.hs6 not in r.index or row.unit_price_usd <= 0:
            continue
        med, mad = r.at[row.hs6, "ref_usd"], r.at[row.hs6, "log_mad"]
        z = (math.log(row.unit_price_usd) - math.log(med)) / (1.4826 * mad)
        if abs(z) < s.price_z:
            continue
        ratio = row.unit_price_usd / med
        strength = float(min(0.97, 0.55 + 0.1 * (abs(z) - s.price_z)))
        kind = "over" if z > 0 else "under"
        out.append(Signal(row.invoice_no, "price", f"{kind}_priced", strength, value=z, evidence=
                          f"Declared {_money(row.unit_price_usd)}/{row.unit} for HS {row.hs6} "
                          f"({r.at[row.hs6, 'description']}) vs reference median {_money(med)} — "
                          f"{ratio:.2f}× the benchmark (robust z = {z:+.1f})."))
    return out


# =========================================================== 2. route
def route_detector(inv: pd.DataFrame, s: Settings) -> list[Signal]:
    out: list[Signal] = []
    hr = set(s.high_risk)
    for row in inv.itertuples(index=False):
        legs = str(row.route).split(">")
        ends = {legs[0], legs[-1]} & hr
        transit = set(legs[1:-1]) & hr
        if ends:
            out.append(Signal(row.invoice_no, "route", "high_risk_party", 0.45,
                              f"Counterparty located in high-risk jurisdiction {', '.join(sorted(ends))}."))
        if transit:
            out.append(Signal(row.invoice_no, "route", "high_risk_transit", 0.35,
                              f"Goods transit high-risk jurisdiction {', '.join(sorted(transit))} (route {row.route})."))
        mids = legs[1:-1]
        seen = [c for i, c in enumerate(mids) if c in mids[:i] or c in (legs[0], legs[-1])]
        if seen:
            out.append(Signal(row.invoice_no, "route", "route_loop", 0.6,
                              f"Route passes through {seen[0]} twice ({row.route}) with no commercial reason recorded."))
        if len(legs) - 1 >= s.max_legs:
            out.append(Signal(row.invoice_no, "route", "excess_legs", 0.3,
                              f"{len(legs) - 1} legs for an {row.origin}→{row.destination} shipment ({row.route})."))
    return out


# =========================================================== 3. documents
def document_detector(inv: pd.DataFrame, docs: pd.DataFrame, packing: pd.DataFrame,
                      ref: pd.DataFrame, s: Settings) -> list[Signal]:
    out: list[Signal] = []
    d = docs.set_index("doc_no") if len(docs) else pd.DataFrame()
    pk = packing.set_index("invoice_no")
    r = ref.set_index("hs6")
    shared = inv.dropna(subset=["doc_no"]).groupby("doc_no")["invoice_no"].apply(list)
    shared = {k: v for k, v in shared.items() if len(v) > 1}

    for row in inv.itertuples(index=False):
        inv_date = pd.Timestamp(row.date)
        if not isinstance(row.doc_no, str) or row.doc_no not in d.index:
            out.append(Signal(row.invoice_no, "documents", "no_transport_doc", 0.7,
                              "No bill of lading or air waybill matches this invoice."))
        else:
            doc = d.loc[row.doc_no]
            dep = pd.Timestamp(doc["departure_date"])
            lag = (dep - inv_date).days
            if lag > s.doc_late_days or lag < -s.doc_early_days:
                out.append(Signal(row.invoice_no, "documents", "implausible_dates", 0.8,
                                  f"{doc['doc_type'].replace('_', ' ').title()} {row.doc_no} departs "
                                  f"{dep.date()}, {lag:+d} days from the invoice date {inv_date.date()}."))
            if doc["carrier_or_vessel"] == "UNKNOWN":
                out.append(Signal(row.invoice_no, "documents", "unknown_vessel", 0.6,
                                  f"Transport document {row.doc_no} names no identifiable vessel."))
            q_gap = abs(doc["quantity"] - row.quantity) / max(row.quantity, 1e-9)
            if q_gap > s.qty_tolerance:
                out.append(Signal(row.invoice_no, "documents", "quantity_mismatch", float(min(0.8, 0.4 + q_gap)),
                                  f"Invoice quantity {row.quantity:,.1f} vs {doc['quantity']:,.1f} on "
                                  f"{row.doc_no} ({q_gap:.0%} difference)."))
            w_gap = abs(doc["gross_weight_kg"] - row.declared_weight_kg) / max(row.declared_weight_kg, 1e-9)
            if w_gap > s.weight_tolerance:
                out.append(Signal(row.invoice_no, "documents", "weight_mismatch", float(min(0.85, 0.5 + w_gap / 2)),
                                  f"Invoice weight {row.declared_weight_kg:,.1f} kg vs {doc['gross_weight_kg']:,.1f} kg "
                                  f"on {row.doc_no} ({w_gap:.0%} difference)."))
            if row.doc_no in shared:
                others = [x for x in shared[row.doc_no] if x != row.invoice_no]
                out.append(Signal(row.invoice_no, "documents", "doc_reused", 0.9,
                                  f"Transport document {row.doc_no} is also cited by {', '.join(others)} — "
                                  f"the same goods appear to be invoiced more than once."))
        if row.invoice_no in pk.index:
            p = pk.loc[row.invoice_no]
            if abs(p["quantity"] - row.quantity) / max(row.quantity, 1e-9) > s.qty_tolerance:
                out.append(Signal(row.invoice_no, "documents", "packing_mismatch", 0.5,
                                  f"Packing list quantity {p['quantity']:,.1f} differs from invoice {row.quantity:,.1f}."))
        if row.hs6 in r.index and r.at[row.hs6, "unit"] == "unit" and row.quantity > 0:
            kpu = row.declared_weight_kg / row.quantity
            typical = r.at[row.hs6, "kg_per_unit"]
            ratio = kpu / typical
            if ratio > s.unit_weight_ratio or ratio < 1 / s.unit_weight_ratio:
                out.append(Signal(row.invoice_no, "documents", "implausible_unit_weight", 0.75,
                                  f"{kpu:,.2f} kg per unit declared for HS {row.hs6} "
                                  f"({r.at[row.hs6, 'description']}); typical is {typical:,.2f} kg — "
                                  f"goods may be misdescribed."))
    return out


# =========================================================== 4. counterparty graph
def link_graph(ent: pd.DataFrame, s: Settings) -> tuple[nx.Graph, dict]:
    """Entities linked by shared director, phone, address or bank account.
    Identifiers shared by >= hub_identifier_size entities (free-zone business centres,
    registered-agent phone lines) are treated as hubs and ignored."""
    g = nx.Graph()
    g.add_nodes_from(ent["entity_id"])
    hubs: dict[str, int] = {}
    for col, label in (("director_id", "director"), ("phone", "phone"), ("address", "address"),
                       ("bank_account", "bank account")):
        for val, grp in ent.groupby(col)["entity_id"]:
            ids = list(grp)
            if len(ids) < 2:
                continue
            if len(ids) >= s.hub_identifier_size:
                hubs[f"{label}: {val}"] = len(ids)
                continue
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    g.add_edge(ids[i], ids[j], via=f"{label} {val}")
    return g, hubs


def graph_detector(inv: pd.DataFrame, ent: pd.DataFrame, s: Settings) -> list[Signal]:
    out: list[Signal] = []
    g, _ = link_graph(ent, s)
    comp = {}
    for i, c in enumerate(nx.connected_components(g)):
        for n in c:
            comp[n] = (i, len(c))

    for row in inv.itertuples(index=False):
        a, b = row.seller_id, row.buyer_id
        if g.has_edge(a, b):
            out.append(Signal(row.invoice_no, "graph", "linked_parties", 0.75,
                              f"Seller {a} and buyer {b} share a {g.edges[a, b]['via']} — a related party "
                              f"presented as independent."))
        elif a in comp and comp[a][0] == comp.get(b, (None,))[0] and comp[a][1] > 1:
            path = nx.shortest_path(g, a, b)
            out.append(Signal(row.invoice_no, "graph", "linked_cluster", 0.55,
                              f"Seller and buyer belong to one cluster of {comp[a][1]} companies linked by shared "
                              f"identifiers (path {' – '.join(path)})."))
    out.extend(_cycles(inv, s))
    return out


def _cycles(inv: pd.DataFrame, s: Settings) -> list[Signal]:
    """Circular trading: the same goods (HS code, similar quantity) travel seller→buyer
    around a loop of companies and return to the start, each hop within cycle_hop_days."""
    out: list[Signal] = []
    flagged: dict[str, str] = {}
    df = inv[["invoice_no", "date", "seller_id", "buyer_id", "hs6", "quantity"]].copy()
    df["t"] = (pd.to_datetime(df["date"]) - pd.Timestamp("1970-01-01")).dt.days
    for hs, grp in df.groupby("hs6"):
        rows = grp.to_dict("records")
        by_seller = defaultdict(list)
        for r in rows:
            by_seller[r["seller_id"]].append(r)

        def nxt(r):
            for c in by_seller.get(r["buyer_id"], []):
                if 0 < c["t"] - r["t"] <= s.cycle_hop_days and \
                        abs(c["quantity"] - r["quantity"]) <= s.cycle_qty_tolerance * r["quantity"]:
                    yield c

        for start in rows:
            stack = [(start, [start])]
            while stack:
                cur, path = stack.pop()
                if len(path) > s.cycle_max_len:
                    continue
                for c in nxt(cur):
                    if c["buyer_id"] == start["seller_id"] and len(path) + 1 >= 3:
                        loop = path + [c]
                        names = " → ".join([x["seller_id"] for x in loop] + [start["seller_id"]])
                        span = loop[-1]["t"] - loop[0]["t"]
                        for x in loop:
                            flagged.setdefault(x["invoice_no"], f"Same goods (HS {hs}, quantity "
                                               f"~{start['quantity']:,.0f}) moved around the loop {names} "
                                               f"within {span} days and returned to the first company.")
                    elif c["invoice_no"] not in {p["invoice_no"] for p in path}:
                        stack.append((c, path + [c]))
    for inv_no, ev in flagged.items():
        out.append(Signal(inv_no, "graph", "circular_trade", 0.85, ev))
    return out


# =========================================================== run all
def run_all(t: dict[str, pd.DataFrame], ref: pd.DataFrame, s: Settings,
            only: set[str] | None = None) -> pd.DataFrame:
    inv = t["invoices"]
    sig: list[Signal] = []
    if only is None or "price" in only:
        sig += price_detector(inv, ref, s)
    if only is None or "route" in only:
        sig += route_detector(inv, s)
    if only is None or "documents" in only:
        sig += document_detector(inv, t["transport_docs"], t["packing_lists"], ref, s)
    if only is None or "graph" in only:
        sig += graph_detector(inv, t["entities"], s)
    cols = ["invoice_no", "detector", "rule", "strength", "evidence", "value"]
    return pd.DataFrame([asdict(x) for x in sig], columns=cols)
