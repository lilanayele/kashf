"""Refresh configs/fatf_lists.yaml from the FATF website (run after each FATF plenary).

    python scripts/update_fatf_lists.py <call-for-action URL> <increased-monitoring URL> [--write]

Fetches both statements, finds every jurisdiction name it knows (NAMES below; add a name if the
FATF lists a new one), and prints the lists with a diff against the current file. With --write it
updates the file. It fails loudly if a page cannot be fetched or no jurisdictions are found; it never
keeps old entries silently. Review the diff by hand: page wording changes, and a name mentioned
only in passing (e.g. "removed from the list") must not be counted.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import requests
import yaml

CFG = Path(__file__).resolve().parent.parent / "configs" / "fatf_lists.yaml"
NAMES = {
    "Democratic People's Republic of Korea": "KP", "DPRK": "KP", "Iran": "IR", "Myanmar": "MM",
    "Algeria": "DZ", "Angola": "AO", "Bolivia": "BO", "Bosnia and Herzegovina": "BA", "Bulgaria": "BG",
    "Burkina Faso": "BF", "Cameroon": "CM", "Côte d'Ivoire": "CI", "Croatia": "HR",
    "Democratic Republic of the Congo": "CD", "Haiti": "HT", "Iraq": "IQ", "Kenya": "KE", "Kuwait": "KW",
    "Lao PDR": "LA", "Lebanon": "LB", "Mali": "ML", "Monaco": "MC", "Mozambique": "MZ", "Namibia": "NA",
    "Nepal": "NP", "Nigeria": "NG", "Papua New Guinea": "PG", "Philippines": "PH", "Senegal": "SN",
    "South Africa": "ZA", "South Sudan": "SS", "Syria": "SY", "Tanzania": "TZ", "Venezuela": "VE",
    "Vietnam": "VN", "Viet Nam": "VN", "Virgin Islands (UK)": "VG", "British Virgin Islands": "VG", "Yemen": "YE",
}


def headings(url: str) -> list[str]:
    """Jurisdiction names that appear as section headings (h2-h4) on the FATF statement page."""
    r = requests.get(url, timeout=60, headers={"User-Agent": "kashf-fatf-list-updater"})
    r.raise_for_status()
    heads = re.findall(r"<h[2-4][^>]*>(.*?)</h[2-4]>", r.text, flags=re.S | re.I)
    text = [re.sub(r"<[^>]+>|&nbsp;", " ", h).strip() for h in heads]
    found = []
    for t in text:
        for name, code in NAMES.items():
            if t.lower() == name.lower() and code not in found:
                found.append(code)
    if not found:
        sys.exit(f"STOP: no known jurisdiction headings found on {url}; update NAMES or parse by hand")
    return found


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cfa_url, im_url, write = sys.argv[1], sys.argv[2], "--write" in sys.argv
    old = yaml.safe_load(CFG.read_text())
    cfa, im = headings(cfa_url), headings(im_url)
    inv = {v: k for k, v in NAMES.items()}
    print("call for action:", cfa, "| was:", sorted(old["call_for_action"]))
    print("increased monitoring:", im, "| was:", sorted(old["increased_monitoring"]))
    print("added:", sorted(set(cfa + im) - set(old["call_for_action"]) - set(old["increased_monitoring"])),
          "removed:", sorted(set(old["call_for_action"]) | set(old["increased_monitoring"]) - set(cfa + im)))
    if write:
        new = {"as_of": input("statement date (YYYY-MM-DD): ").strip(), "checked": date.today().isoformat(),
               "sources": {"call_for_action": cfa_url, "increased_monitoring": im_url},
               "call_for_action": {c: old["call_for_action"].get(c, {"name": inv[c], "measure": "CHECK"})
                                   for c in cfa},
               "increased_monitoring": {c: inv[c] for c in im}}
        CFG.write_text(yaml.safe_dump(new, sort_keys=False, allow_unicode=True))
        print("wrote", CFG, "- review measures marked CHECK")


if __name__ == "__main__":
    main()
