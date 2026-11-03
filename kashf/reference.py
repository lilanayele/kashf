"""Reference unit-price table (the benchmark the price detector compares against).

The default table is ILLUSTRATIVE: plausible order-of-magnitude unit values for
goods commonly re-exported through the UAE, chosen for this prototype. It is not
UN Comtrade data. Replace it with real values using scripts/fetch_comtrade.py
(needs a free UN Comtrade account) — the detector code does not change.

Columns
  hs6            HS 2017 6-digit product code
  description    short product name
  unit           "unit" (priced per piece) or "kg" (priced per kilogram)
  ref_usd        median unit value in USD
  log_mad        median absolute deviation of log unit value (price dispersion)
  kg_per_unit    typical gross weight of one unit (1.0 for kg-priced goods)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT = [
    # hs6,    description,                      unit,   ref_usd, log_mad, kg_per_unit
    ("851713", "Smartphones",                    "unit",  180.0,   0.30,    0.35),
    ("847130", "Laptops",                        "unit",  450.0,   0.30,    2.5),
    ("850440", "Power supplies / adapters",      "unit",   15.0,   0.35,    0.5),
    ("901890", "Medical instruments",            "unit",  120.0,   0.40,    1.2),
    ("870323", "Passenger cars 1.5-3.0L",        "unit", 18000.0,  0.35, 1450.0),
    ("940360", "Wooden furniture",               "unit",  150.0,   0.35,   30.0),
    ("610910", "Cotton T-shirts",                "unit",    3.0,   0.30,    0.2),
    ("330300", "Perfumes",                       "unit",   25.0,   0.40,    0.4),
    ("710813", "Gold, semi-manufactured",        "kg",  80000.0,   0.08,    1.0),
    ("711319", "Gold jewellery",                 "kg",  90000.0,   0.15,    1.0),
    ("870899", "Vehicle parts",                  "kg",     12.0,   0.35,    1.0),
    ("300490", "Medicines, packaged",            "kg",     40.0,   0.40,    1.0),
    ("392690", "Plastic articles",               "kg",      4.0,   0.30,    1.0),
    ("721420", "Steel bars",                     "kg",      0.7,   0.20,    1.0),
    ("520100", "Raw cotton",                     "kg",      1.8,   0.20,    1.0),
    ("100630", "Rice, milled",                   "kg",      0.6,   0.20,    1.0),
    ("170199", "Sugar, refined",                 "kg",      0.5,   0.20,    1.0),
    ("090240", "Black tea",                      "kg",      3.0,   0.30,    1.0),
    ("080410", "Dates",                          "kg",      2.0,   0.30,    1.0),
    ("271019", "Petroleum oils, lubricants",     "kg",      0.8,   0.25,    1.0),
]
COLUMNS = ["hs6", "description", "unit", "ref_usd", "log_mad", "kg_per_unit"]


def default_table() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT, columns=COLUMNS)


def load(path: str | Path | None = None) -> pd.DataFrame:
    if path is None:
        return default_table()
    df = pd.read_csv(path, dtype={"hs6": str})
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"reference table missing columns: {sorted(missing)}")
    return df[COLUMNS]
