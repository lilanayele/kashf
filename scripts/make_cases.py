"""Build tests/cases/: small scenarios RECONSTRUCTED FROM PUBLIC REPORTS (not real records).

Each case is a handful of invoices written to follow the scheme a public FATF/Egmont case box
describes, using the generator's CSV schema. Names, IDs, dates, quantities and prices are invented;
only the mechanism comes from the source. Each case states what Kashf is expected to do, including
schemes it cannot see by design (payment-side typologies), so the tests document blind spots too.

Source for all cases: FATF and Egmont Group, "Trade-Based Money Laundering: Trends and Developments",
FATF, Paris, December 2020 (box numbers and pages below), verified at
https://www.fatf-gafi.org/en/publications/Methodsandtrends/Trade-based-money-laundering-trends-and-developments.html

    python scripts/make_cases.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "tests" / "cases"
SRC = ("FATF and Egmont Group (2020), Trade-Based Money Laundering: Trends and Developments, FATF, Paris. "
       "https://www.fatf-gafi.org/en/publications/Methodsandtrends/Trade-based-money-laundering-trends-and-developments.html")
REF = {"851713": ("Smartphones", "unit", 180.0, 0.35), "870323": ("Passenger cars 1.5-3.0L", "unit", 18000.0, 1450.0),
       "080410": ("Dates", "kg", 2.0, 1.0)}


_PHONE = iter(range(1000, 9999))


def ent(eid, name, country, kind="foreign", director=None, phone=None, address=None):
    return {"entity_id": eid, "name": name, "kind": kind, "country": country,
            "address": address or f"{eid} Street 1, City-{country}", "phone": phone or f"+99 55 {next(_PHONE)} 0000",
            "director_id": director or f"P-{eid}", "bank_account": f"ACC-{eid}"}


class Case:
    def __init__(self):
        self.ents, self.inv, self.docs, self.pack = [], [], [], []
        self.n = 0

    def invoice(self, seller, buyer, hs, qty, price, date, origin, dest, route=None, doc=True, dep_days=5):
        self.n += 1
        desc, unit, _, kpu = REF[hs]
        no = f"CASE-{self.n:04d}"
        w = qty * kpu if unit == "unit" else qty * 1.02
        doc_no = f"BL-C{self.n:05d}" if doc else None
        self.inv.append({"invoice_no": no, "date": date, "seller_id": seller, "buyer_id": buyer, "hs6": hs,
                         "description": desc, "quantity": qty, "unit": unit, "unit_price_usd": price,
                         "value_usd": round(qty * price, 2), "declared_weight_kg": round(w, 1), "origin": origin,
                         "destination": dest, "route": route or f"{origin}>{dest}", "doc_no": doc_no})
        if doc:
            dep = (pd.Timestamp(date) + pd.Timedelta(days=dep_days)).date().isoformat()
            self.docs.append({"doc_no": doc_no, "doc_type": "bill_of_lading", "carrier_or_vessel": "MSC Aurora",
                              "departure_date": dep, "quantity": qty, "gross_weight_kg": round(w * 1.01, 1),
                              "port_load": origin, "port_discharge": dest})
        self.pack.append({"invoice_no": no, "quantity": qty, "net_weight_kg": round(w * 0.95, 1)})

    def save(self, name, meta):
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(self.ents).to_csv(d / "entities.csv", index=False)
        pd.DataFrame(self.inv).to_csv(d / "invoices.csv", index=False)
        cols = ["doc_no", "doc_type", "carrier_or_vessel", "departure_date", "quantity", "gross_weight_kg",
                "port_load", "port_discharge"]
        pd.DataFrame(self.docs, columns=cols).to_csv(d / "transport_docs.csv", index=False)
        pd.DataFrame(self.pack).to_csv(d / "packing_lists.csv", index=False)
        (d / "case.json").write_text(json.dumps({"label": "reconstructed from public reports", "source": SRC, **meta},
                                                indent=2))


def main() -> None:
    # 1. Box 2.8 (p. 24, Australia): electronics exported to South East Asia / Middle East at undervalued prices
    c = Case()
    c.ents += [ent("AU001", "Southern Devices Pty Ltd", "AU"), ent("SG001", "Lion Gate Trading Pte", "SG"),
               ent("AE001", "Harbour Electronics FZE", "AE", kind="uae_freezone")]
    for i, (b, d) in enumerate([("SG001", "SG"), ("AE001", "AE"), ("SG001", "SG"), ("AE001", "AE")]):
        c.invoice("AU001", b, "851713", 400, 36.0 + i, f"2025-0{i + 2}-10", "AU", d)
    c.save("box2_8_undervalued_electronics", {
        "box": "2.8", "page": 24, "country": "Australia",
        "what_happened": "Drug proceeds were layered through Australian accounts and used to buy small portable "
                         "electronics that were exported to South East Asia and the Middle East at undervalued prices.",
        "reconstruction": "4 smartphone export invoices priced at about 0.2x the reference median.",
        "expect": "evidence", "rules": ["under_priced"]})

    # 2. Box 2.6 (p. 22, Spain/Italy): luxury vehicles with fake paper trails through VAT chains
    c = Case()
    c.ents += [ent("IT001", "Auto Lusso Srl", "IT"), ent("DE001", "Rhein Motors GmbH", "DE"),
               ent("ES001", "Costa Vehiculos SL", "ES"), ent("IT002", "Nord Import Srl", "IT")]
    chain = [("IT001", "DE001", "IT", "DE"), ("DE001", "ES001", "DE", "ES"), ("ES001", "IT002", "ES", "IT"),
             ("IT002", "IT001", "IT", "IT")]
    for rnd in range(2):
        for k, (s, b, o, d) in enumerate(chain):
            c.invoice(s, b, "870323", 6, 52000.0 + 1500 * k, f"2025-{3 + 3 * rnd:02d}-{3 + 7 * k:02d}", o, d)
    c.save("box2_6_vehicle_chain", {
        "box": "2.6", "page": 22, "country": "Spain, Italy (Europol)",
        "what_happened": "Criminal cash bought luxury vehicles in Germany; companies created fake paper trails for "
                         "sales and VAT chains.",
        "reconstruction": "The same 6 cars invoiced around a chain of 4 companies that returns to the first, twice.",
        "expect": "evidence", "rules": ["circular_trade"]})

    # 3. Box 2.13 (pp. 34-35, Italy): vehicle firms suspected of a false-invoicing network, exports to the Middle East
    c = Case()
    c.ents += [ent("IT101", "Fratelli Auto Srl", "IT"), ent("JO101", "Levant Import Export Co", "JO"),
               ent("LB101", "Cedar Trading Sarl", "LB")]
    for i, b in enumerate(["JO101", "LB101", "JO101"]):
        c.invoice("IT101", b, "870323", 4, 19000.0, f"2025-05-{10 + i:02d}", "IT", b[:2], doc=False)
    c.save("box2_13_false_invoices", {
        "box": "2.13", "page": 34, "country": "Italy",
        "what_happened": "Accounts of two brothers running motor-vehicle firms showed activity first suspected as a "
                         "false-invoicing network; vehicle-sale proceeds went to Middle Eastern import/export companies.",
        "reconstruction": "Export invoices for cars with no matching bill of lading (invoices without shipments). "
                          "This is an interpretation of 'false invoicing'; the box gives no document details.",
        "expect": "evidence", "rules": ["no_transport_doc"]})

    # 4. Box 2.11 (p. 32, New Zealand): fruit exporters paid by shell companies in high-risk jurisdictions
    c = Case()
    c.ents += [ent("NZ201", "Kiwi Orchards Ltd", "NZ"), ent("VG201", "Bluewater Holdings Ltd", "VG")]
    for i in range(3):
        c.invoice("NZ201", "VG201", "080410", 2000, 2.1, f"2025-0{i + 4}-02", "NZ", "VG")
    c.save("box2_11_high_risk_shell_buyer", {
        "box": "2.11", "page": 32, "country": "New Zealand",
        "what_happened": "Fruit exporters received payments from accounts of shell companies in high-risk "
                         "jurisdictions against fraudulent invoices.",
        "reconstruction": "Fairly priced fruit (HS 080410) sold to a shell in a FATF-listed jurisdiction (VG). The "
                          "third-party payments and fake invoice wording are not in invoice data.",
        "expect": "evidence", "rules": ["high_risk_party"]})

    # 5. Box 4.7 (p. 52, Germany): two sales partners with the same beneficial owner, third-party payments
    c = Case()
    c.ents += [ent("DE301", "Autowerk AG", "DE"), ent("XX301", "Partner A LLC", "KZ", director="UBO-1"),
               ent("XX302", "Partner B LLC", "KZ", director="UBO-1")]
    for i, b in enumerate(["XX301", "XX302", "XX301", "XX302"]):
        c.invoice("DE301", b, "870323", 10, 18500.0, f"2025-06-{3 + i:02d}", "DE", "KZ")
    c.save("box4_7_shared_ubo_third_party_payments", {
        "box": "4.7", "page": 52, "country": "Germany",
        "what_happened": "Two sales partners of car manufacturers received third-party payments from unknown accounts "
                         "(over EUR 80 million); both partners had the same ultimate beneficial owner.",
        "reconstruction": "Normal invoices to two buyers that share a director. Kashf links parties only when they "
                          "trade with each other, and payments are not in the data.",
        "expect": "blind_spot", "rules": []})

    # 6. Box 2.9 (p. 28, United States): Black Market Peso Exchange with a complicit electronics exporter
    c = Case()
    c.ents += [ent("US401", "Miami Electronics Inc", "US"), ent("CO401", "Andes Distribuciones SAS", "CO"),
               ent("CO402", "Pacifico Importadora SAS", "CO")]
    for i, b in enumerate(["CO401", "CO402", "CO401"]):
        c.invoice("US401", b, "851713", 300, 182.0 + i, f"2025-07-{5 + i:02d}", "US", "CO")
    c.save("box2_9_bmpe", {
        "box": "2.9", "page": 28, "country": "United States",
        "what_happened": "Drug cash was paid to a complicit US merchant exporting consumer electronics; Colombian "
                         "importers paid pesos to money brokers, so no cash crossed the border.",
        "reconstruction": "Fairly priced, fully documented electronics exports. The laundering is in who pays, "
                          "which invoice data does not show.",
        "expect": "blind_spot", "rules": []})
    print(f"wrote {len(list(OUT.glob('*/case.json')))} cases to {OUT}")


if __name__ == "__main__":
    main()
