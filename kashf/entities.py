"""Entity resolution for the counterparty graph.

Company records from different sources spell the same thing differently:
"Gulf Star Gen. Trdg L.L.C" vs "Gulf Star General Trading LLC", "+971 50 123 4567" vs
"00971501234567". Exact matching misses these links. This module normalises names, phones
and addresses and finds near-duplicate names with rapidfuzz.

Linking rules (Settings.entity_resolution = "fuzzy"):
  * phone:   same digits after normalisation (leading 00 / + removed)       -> link
  * address: same text after normalisation (case, punctuation, abbreviations) -> link
  * name:    name similarity >= name_similarity AND same country AND
             address similarity >= address_similarity AND the same numbers in both
             addresses (unit/office/area), and the address is not a shared hub   -> link
A similar name alone never links two companies: many unrelated firms share trading names.
"""

from __future__ import annotations

import re
from typing import Iterable

import pandas as pd

# abbreviation -> full form (applied to whole tokens after lower-casing and stripping punctuation)
_ABBREV = {
    "gen": "general", "genl": "general", "trdg": "trading", "trd": "trading", "tradg": "trading",
    "comm": "commodities", "ent": "enterprises", "elec": "electronics", "intl": "international",
    "co": "company", "corp": "corporation", "svcs": "services", "hldg": "holdings", "hldgs": "holdings",
    "off": "office", "bldg": "building", "blg": "building", "ind": "industrial", "st": "street",
    "rd": "road", "fl": "floor", "no": "", "nr": "",
}
# legal-form suffixes dropped from names (after punctuation is removed, "l.l.c" becomes "llc")
_LEGAL = {"llc", "fze", "fzco", "fzc", "fzllc", "ltd", "limited", "plc", "inc", "pvt", "est", "establishment"}


def _tokens(text: str) -> list[str]:
    t = str(text or "").lower()
    t = re.sub(r"(?<=\w)\.(?=\w)", "", t)       # l.l.c -> llc, f.z.e -> fze
    t = re.sub(r"[^\w\s]", " ", t)               # punctuation and hyphens -> space
    return [_ABBREV.get(w, w) for w in t.split()]


def normalise_name(name: str) -> str:
    toks = [w for w in _tokens(name) if w and w not in _LEGAL]
    return " ".join(toks)


def normalise_address(addr: str) -> str:
    return " ".join(w for w in _tokens(addr) if w)


def normalise_phone(phone: str) -> str:
    d = re.sub(r"\D", "", str(phone or ""))
    return d[2:] if d.startswith("00") else d


def _pairs(ids: list[str]) -> Iterable[tuple[str, str]]:
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            yield ids[i], ids[j]


def links(ent: pd.DataFrame, mode: str = "fuzzy", name_similarity: float = 90.0,
          address_similarity: float = 85.0, hub_size: int = 6) -> tuple[list[tuple[str, str, str]], dict]:
    """(a, b, via) links between entities, plus identifiers ignored as hubs (shared by >= hub_size)."""
    e = ent.copy()
    for c in ("name", "country", "phone", "address", "director_id", "bank_account"):
        if c not in e:
            e[c] = None                                   # uploads may lack optional columns
    fuzzy = mode == "fuzzy"
    e["_phone"] = e["phone"].map(normalise_phone) if fuzzy else e["phone"].astype(str)
    e["_address"] = e["address"].map(normalise_address) if fuzzy else e["address"].astype(str)
    out: list[tuple[str, str, str]] = []
    hubs: dict[str, int] = {}
    for col, label, show in (("director_id", "director", "director_id"), ("_phone", "phone", "phone"),
                             ("_address", "address", "address"), ("bank_account", "bank account", "bank_account")):
        for _, grp in e[e[col].notna() & (e[col].astype(str).str.strip() != "")].groupby(col):
            if len(grp) < 2:
                continue
            shown = sorted(set(grp[show].astype(str)))
            desc = shown[0] if len(shown) == 1 else " / ".join(f"“{x}”" for x in shown[:3])
            if len(grp) >= hub_size:
                hubs[f"{label}: {shown[0]}"] = len(grp)
                continue
            variant = " (same after normalising formats)" if len(shown) > 1 else ""
            for a, b in _pairs(list(grp["entity_id"])):
                out.append((a, b, f"{label} {desc}{variant}"))
    if fuzzy:
        counts = e["_address"].value_counts()
        e = e[e["_address"].map(counts) < hub_size]          # business centres say nothing about control
        out += _name_links(e, name_similarity, address_similarity)
    return out, hubs


def _name_links(e: pd.DataFrame, name_sim: float, addr_sim: float) -> list[tuple[str, str, str]]:
    from rapidfuzz import fuzz

    e = e.assign(_name=e["name"].map(normalise_name))
    e["_block"] = e["_name"].str.split().str[0].fillna("")   # compare only names sharing a first word
    out = []
    for (_, _), grp in e.groupby(["country", "_block"]):
        if len(grp) < 2:
            continue
        rows = grp.to_dict("records")
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                ns = fuzz.token_sort_ratio(a["_name"], b["_name"])
                if ns < name_sim:
                    continue
                if re.findall(r"\d+", a["_address"]) != re.findall(r"\d+", b["_address"]):
                    continue
                as_ = fuzz.token_sort_ratio(a["_address"], b["_address"])
                if as_ < addr_sim:
                    continue
                out.append((a["entity_id"], b["entity_id"],
                            f"near-identical name and address (“{a['name']}” vs “{b['name']}”, "
                            f"name {ns:.0f}%, address {as_:.0f}% similar)"))
    return out
