"""Synthetic UAE trade world with planted trade-based money laundering (TBML).

Produces four tables, like the records a trading company would hand to a
compliance reviewer, plus a separate ground-truth label table:

    entities         companies: UAE mainland / free zone and foreign counterparties
    invoices         one row per commercial invoice (seller, buyer, HS code, qty, price, route)
    transport_docs   bills of lading (sea) and air waybills (air), keyed by doc_no
    packing_lists    quantity and net weight per invoice
    labels           invoice_no -> typology ("none" for clean trade)   [never shown to detectors]

Clean trade is deliberately noisy so the evaluation is not trivial:
premium-priced and clearance-priced legitimate goods, legitimate transshipment
through regional hubs, legitimate trade with high-risk jurisdictions, free-zone
business centres where many unrelated companies share an address, related-party
groups, short shipments and missing paperwork.

Seven typologies are planted (FATF/Egmont 2020 and 2021 indicators):
    over_invoicing, under_invoicing, phantom_shipment, multiple_invoicing,
    misdescription, circular_trading, shell_cluster
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from kashf.reference import default_table

PARTNERS = ["IN", "CN", "PK", "SA", "OM", "IQ", "KE", "ET", "TR", "GB", "DE", "US", "HK", "SG", "EG"]
HIGH_RISK = ["XA", "XB", "XC"]  # illustrative high-risk jurisdictions (see config.py)
HUBS = ["OM", "SA", "SG", "HK", "IN"]
VESSELS = ["MSC Aurora", "Maersk Halifax", "CMA CGM Tigris", "Hapag Al Zubara", "COSCO Pride",
           "ONE Harmony", "Evergreen Ever Gentle", "Yang Ming Wish", "MSC Gulsun", "Maersk Essen"]
FREEZONE_CENTRES = ["Business Centre 1, JAFZA South", "Business Centre 2, JAFZA North",
                    "Smart Desk Tower, DMCC JLT", "Flexi Hub, Dubai South",
                    "Executive Suites, Hamriyah FZ"]

_W1 = ["Al Noor", "Gulf Star", "Desert Rose", "Blue Dhow", "Falcon", "Oasis", "Pearl Coast", "Crescent",
       "Golden Sands", "Silk Route", "Marina", "Horizon", "Emirates Link", "Arabian Peak", "Seven Seas",
       "Palm Line", "Zenith", "Atlas", "Meridian", "Sapphire", "Dune", "Harbour", "Oryx", "Saffron"]
_W2 = ["General Trading", "Commodities", "Logistics", "Impex", "Electronics", "Metals", "Foodstuff",
       "Auto Parts", "Textiles", "Holdings", "Supplies", "Enterprises"]
_SUFFIX = {"uae_mainland": "LLC", "uae_freezone": "FZE", "foreign": "Ltd"}


@dataclass
class Config:
    seed: int = 0
    n_invoices: int = 20000
    n_uae: int = 150
    n_foreign: int = 300
    typology_rate: float = 0.006      # per planted invoice-level typology
    n_rings: int = 12                  # circular trading rings
    n_shell_clusters: int = 10
    start: date = date(2025, 1, 1)


class World:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        self.ref = default_table().set_index("hs6")
        self.entities: list[dict] = []
        self.invoices: list[dict] = []
        self.docs: list[dict] = []
        self.packing: list[dict] = []
        self.labels: list[dict] = []
        self._inv = 0
        self._doc = 0
        self._ent = 0
        self._person = 0

    # ------------------------------------------------------------- entities
    def _phone(self, country: str) -> str:
        cc = {"AE": "+971"}.get(country, "+" + str(self.rng.integers(20, 99)))
        return f"{cc} {self.rng.integers(10, 99)} {self.rng.integers(100, 999)} {self.rng.integers(1000, 9999)}"

    def _new_person(self) -> str:
        self._person += 1
        return f"P{self._person:05d}"

    def add_entity(self, kind: str, country: str, *, address=None, director=None, phone=None) -> str:
        self._ent += 1
        eid = f"E{self._ent:04d}"
        name = f"{self.rng.choice(_W1)} {self.rng.choice(_W2)} {_SUFFIX[kind]}"
        if address is None:
            if kind == "uae_freezone" and self.rng.random() < 0.6:
                address = str(self.rng.choice(FREEZONE_CENTRES))  # legitimately shared
            else:
                address = f"Unit {self.rng.integers(1, 999)}, Building {self.rng.integers(1, 400)}, " + \
                          ("Dubai" if country == "AE" else f"City-{country}")
        self.entities.append({
            "entity_id": eid, "name": name, "kind": kind, "country": country, "address": address,
            "phone": phone or self._phone(country), "director_id": director or self._new_person(),
            "bank_account": f"ACC{self._ent:06d}",
        })
        return eid

    def build_entities(self) -> None:
        c = self.cfg
        for i in range(c.n_uae):
            self.add_entity("uae_mainland" if i % 2 else "uae_freezone", "AE")
        for _ in range(c.n_foreign):
            country = str(self.rng.choice(HIGH_RISK if self.rng.random() < 0.05 else PARTNERS))
            self.add_entity("foreign", country)
        self.uae = [e["entity_id"] for e in self.entities if e["country"] == "AE"]
        self.foreign = [e["entity_id"] for e in self.entities if e["country"] != "AE"]
        self.country = {e["entity_id"]: e["country"] for e in self.entities}

    # ------------------------------------------------------------- helpers
    def _date(self) -> date:
        return self.cfg.start + timedelta(days=int(self.rng.integers(0, 365)))

    def _route(self, origin: str, dest: str, loop: bool = False) -> str:
        hubs = [h for h in HUBS if h not in (origin, dest)]
        r = self.rng.random()
        mid: list[str] = []
        if r > 0.70:
            mid.append(str(self.rng.choice(hubs)))
        if r > 0.95:
            mid.append(str(self.rng.choice([h for h in hubs if h not in mid])))
        if loop:
            mid = [str(self.rng.choice(hubs)), str(self.rng.choice(PARTNERS)), origin]
        return ">".join([origin, *mid, dest])

    def _quantity(self, hs6: str) -> float:
        unit = self.ref.loc[hs6, "unit"]
        ref = self.ref.loc[hs6, "ref_usd"]
        if unit == "kg":
            base = 20.0 if ref > 10000 else 8000.0  # gold in kilos, bulk goods in tonnes
            return float(round(base * np.exp(self.rng.normal(0, 0.9)), 1))
        base = 6.0 if ref > 5000 else (40.0 if ref > 100 else 1500.0)
        return float(max(1, round(base * np.exp(self.rng.normal(0, 0.9)))))

    def _price(self, hs6: str) -> float:
        sd = self.ref.loc[hs6, "log_mad"] * 1.4826
        return float(self.ref.loc[hs6, "ref_usd"] * np.exp(self.rng.normal(0, sd)))

    def _weight(self, hs6: str, qty: float) -> float:
        kpu = self.ref.loc[hs6, "kg_per_unit"]
        if self.ref.loc[hs6, "unit"] == "kg":
            return float(qty * (1 + self.rng.uniform(0.01, 0.05)))
        return float(qty * kpu * np.exp(self.rng.normal(0, 0.08)))

    def _pick_parties(self) -> tuple[str, str]:
        r = self.rng.random()
        if r < 0.5:
            return str(self.rng.choice(self.uae)), str(self.rng.choice(self.foreign))
        if r < 0.9:
            return str(self.rng.choice(self.foreign)), str(self.rng.choice(self.uae))
        a, b = self.rng.choice(self.uae, 2, replace=False)
        return str(a), str(b)

    # ------------------------------------------------------------- invoices
    def add_invoice(self, seller: str, buyer: str, hs6: str, *, qty=None, unit_price=None, when=None,
                    route=None, label="none", doc="normal", doc_no=None, declared_hs6=None,
                    weight=None) -> dict:
        self._inv += 1
        inv_no = f"INV-2025-{self._inv:06d}"
        qty = self._quantity(hs6) if qty is None else qty
        unit_price = self._price(hs6) if unit_price is None else unit_price
        when = when or self._date()
        o, d = self.country[seller], self.country[buyer]
        route = route or self._route(o, d)
        weight = self._weight(hs6, qty) if weight is None else weight
        mode = "air" if (self.ref.loc[hs6, "ref_usd"] > 5000 and self.ref.loc[hs6, "unit"] == "kg") \
            or self.rng.random() < 0.08 else "sea"
        inv = {
            "invoice_no": inv_no, "date": when.isoformat(), "seller_id": seller, "buyer_id": buyer,
            "hs6": declared_hs6 or hs6, "description": self.ref.loc[declared_hs6 or hs6, "description"],
            "quantity": qty, "unit": self.ref.loc[declared_hs6 or hs6, "unit"],
            "unit_price_usd": round(unit_price, 4), "value_usd": round(qty * unit_price, 2),
            "declared_weight_kg": round(weight, 1), "origin": o, "destination": d, "route": route,
            "doc_no": None,
        }
        # transport document
        if doc == "missing":
            pass
        elif doc_no is not None:  # re-uses an existing document (multiple invoicing)
            inv["doc_no"] = doc_no
        else:
            self._doc += 1
            dn = f"{'BL' if mode == 'sea' else 'AWB'}-{self._doc:07d}"
            dep = when + timedelta(days=int(self.rng.integers(-5, 25)))
            dq, dw = qty, weight * (1 + self.rng.normal(0, 0.015))
            vessel = str(self.rng.choice(VESSELS)) if mode == "sea" else "Air cargo"
            if doc == "short":          # legitimate short shipment
                dq = round(qty * self.rng.uniform(0.85, 0.95), 1)
                dw = dw * dq / qty
            elif doc == "rounding":     # within tolerance
                dq = round(qty * self.rng.uniform(0.99, 1.01), 1)
            elif doc == "bad_dates":    # phantom: paperwork that cannot match a real voyage
                dep = when + timedelta(days=int(self.rng.integers(150, 300)))
                vessel = "UNKNOWN"
            elif doc == "bad_weight":   # phantom: nowhere near the declared cargo
                dw = weight * self.rng.uniform(0.05, 0.3)
            self.docs.append({
                "doc_no": dn, "doc_type": "bill_of_lading" if mode == "sea" else "air_waybill",
                "carrier_or_vessel": vessel, "departure_date": dep.isoformat(), "quantity": dq,
                "gross_weight_kg": round(dw, 1), "port_load": route.split(">")[0],
                "port_discharge": route.split(">")[-1],
            })
            inv["doc_no"] = dn
        self.packing.append({"invoice_no": inv_no, "quantity": qty,
                             "net_weight_kg": round(weight * self.rng.uniform(0.9, 0.97), 1)})
        self.invoices.append(inv)
        self.labels.append({"invoice_no": inv_no, "typology": label})
        return inv

    def _hs(self) -> str:
        return str(self.rng.choice(self.ref.index))

    # ------------------------------------------------------------- clean trade
    def clean(self, n: int) -> None:
        for _ in range(n):
            s, b = self._pick_parties()
            hs = self._hs()
            price = self._price(hs)
            r = self.rng.random()
            if r < 0.03:                 # premium / branded goods: legitimately expensive
                price *= self.rng.uniform(1.4, 2.6)
            elif r < 0.05:               # clearance stock: legitimately cheap
                price *= self.rng.uniform(0.45, 0.75)
            d = self.rng.random()
            doc = "missing" if d < 0.005 else "short" if d < 0.01 else "rounding" if d < 0.03 else "normal"
            self.add_invoice(s, b, hs, unit_price=price, doc=doc)

    def related_party_groups(self, n_groups: int = 5) -> None:
        """Legitimate groups: two companies with the same owner trading normally (disclosed)."""
        for _ in range(n_groups):
            director = self._new_person()
            a = self.add_entity("uae_mainland", "AE", director=director)
            b = self.add_entity("foreign", str(self.rng.choice(PARTNERS)), director=director)
            self.country.update({a: "AE", b: self.entities[-1]["country"]})
            for _ in range(int(self.rng.integers(3, 6))):
                self.add_invoice(a, b, self._hs())

    # ------------------------------------------------------------- typologies
    def plant(self) -> None:
        c, n = self.cfg, int(self.cfg.n_invoices * self.cfg.typology_rate)
        for _ in range(n):  # over-invoicing: moves value from buyer to seller
            s, b = self._pick_parties()
            hs = self._hs()
            self.add_invoice(s, b, hs, unit_price=self._price(hs) * self.rng.uniform(1.8, 8.0),
                             label="over_invoicing")
        for _ in range(n):  # under-invoicing
            s, b = self._pick_parties()
            hs = self._hs()
            self.add_invoice(s, b, hs, unit_price=self._price(hs) * self.rng.uniform(0.12, 0.55),
                             label="under_invoicing")
        for i in range(n):  # phantom shipments
            s, b = self._pick_parties()
            kind = ["missing", "bad_dates", "bad_weight"][i % 3]
            self.add_invoice(s, b, self._hs(), label="phantom_shipment", doc=kind)
        for _ in range(n // 2):  # multiple invoicing: same goods, same B/L, two buyers
            s, b1 = self._pick_parties()
            hs = self._hs()
            first = self.add_invoice(s, b1, hs, label="multiple_invoicing")
            b2 = str(self.rng.choice([e for e in (self.foreign + self.uae) if e not in (s, b1)]))
            when = date.fromisoformat(first["date"]) + timedelta(days=int(self.rng.integers(0, 20)))
            self.add_invoice(s, b2, hs, qty=first["quantity"], unit_price=first["unit_price_usd"],
                             when=when, label="multiple_invoicing", doc_no=first["doc_no"],
                             weight=first["declared_weight_kg"])
        for _ in range(n):  # misdescription: electronics declared as cheap plastic or textiles
            s, b = self._pick_parties()
            true_hs = str(self.rng.choice(["851713", "847130", "901890"]))
            qty_units = self._quantity(true_hs)
            value = qty_units * self._price(true_hs)
            weight = self._weight(true_hs, qty_units)
            if self.rng.random() < 0.5:
                decl, qty = "392690", round(weight, 1)              # declared per kg as plastics
            else:
                decl, qty = "610910", qty_units                      # declared as T-shirts
            self.add_invoice(s, b, true_hs, qty=qty, unit_price=value / qty, declared_hs6=decl,
                             weight=weight, label="misdescription")
        self._rings(c.n_rings)
        self._shells(c.n_shell_clusters)

    def _rings(self, k: int) -> None:
        for _ in range(k):
            size = int(self.rng.integers(3, 5))
            members = [str(self.rng.choice(self.uae))] + \
                      [str(x) for x in self.rng.choice(self.foreign, size - 1, replace=False)]
            hs = self._hs()
            qty = self._quantity(hs)
            price = self._price(hs)
            for _ in range(int(self.rng.integers(2, 4))):  # the loop is repeated
                when = self._date()
                for i in range(size):
                    s, b = members[i], members[(i + 1) % size]
                    price *= self.rng.uniform(1.0, 1.12)
                    when = when + timedelta(days=int(self.rng.integers(3, 15)))
                    self.add_invoice(s, b, hs, qty=qty, unit_price=price, when=when,
                                     label="circular_trading")

    def _shells(self, k: int) -> None:
        for _ in range(k):
            r = self.rng.random()
            shared = {"director": self._new_person()} if r < 0.6 else \
                     {"phone": self._phone("AE")} if r < 0.85 else \
                     {"address": f"Office {self.rng.integers(100, 999)}, Al Qusais Industrial Area 4, Dubai"}
            size = int(self.rng.integers(3, 6))
            members = []
            for j in range(size):
                kind = "uae_freezone" if j % 2 == 0 else "foreign"
                country = "AE" if kind != "foreign" else str(self.rng.choice(PARTNERS + HIGH_RISK))
                eid = self.add_entity(kind, country,
                                      director=shared.get("director"), phone=shared.get("phone"),
                                      address=shared.get("address"))
                self.country[eid] = country
                members.append(eid)
            for _ in range(int(self.rng.integers(8, 16))):
                s, b = self.rng.choice(members, 2, replace=False)
                hs = self._hs()
                self.add_invoice(str(s), str(b), hs, unit_price=self._price(hs) * self.rng.uniform(1.0, 1.6),
                                 label="shell_cluster")

    # ------------------------------------------------------------- output
    def tables(self) -> dict[str, pd.DataFrame]:
        inv = pd.DataFrame(self.invoices)
        lab = pd.DataFrame(self.labels)
        order = self.rng.permutation(len(inv))       # shuffle so labels can't be guessed by position
        inv, lab = inv.iloc[order].reset_index(drop=True), lab.iloc[order].reset_index(drop=True)
        return {"entities": pd.DataFrame(self.entities), "invoices": inv,
                "transport_docs": pd.DataFrame(self.docs), "packing_lists": pd.DataFrame(self.packing),
                "labels": lab}


def generate(cfg: Config | None = None) -> dict[str, pd.DataFrame]:
    cfg = cfg or Config()
    w = World(cfg)
    w.build_entities()
    w.related_party_groups()
    w.plant()
    planted = len(w.invoices)
    w.clean(max(0, cfg.n_invoices - planted))
    return w.tables()


def save(tables: dict[str, pd.DataFrame], out: str | Path) -> None:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a synthetic UAE trade dataset with planted TBML")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--out", default="data/synthetic/seed0")
    a = ap.parse_args()
    t = generate(Config(seed=a.seed, n_invoices=a.n))
    save(t, a.out)
    vc = t["labels"]["typology"].value_counts()
    print(f"wrote {len(t['invoices'])} invoices, {len(t['entities'])} entities -> {a.out}\n{vc.to_string()}")


if __name__ == "__main__":
    main()
