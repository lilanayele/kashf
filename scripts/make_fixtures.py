"""Trim saved real UN Comtrade responses into small test fixtures (tests/fixtures/comtrade/).

    python scripts/make_fixtures.py ~/Downloads        # folder holding kashf_*.json

Keeps 2023 only, three HS6 codes with different quantity units (smartphones per unit, gold per kg,
furniture with many Comtrade-estimated quantities), a few partners on the UAE/mirror side and every
40 reporters per code on the world side (the reference table needs >= 5). A few hundred records in total:
real data, small enough to commit and to run offline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CODES = {"851713", "710813", "940360"}
PARTNERS = {"IND", "SAU", "DEU", "CHN", "GBR", "USA", "OMN", "PAK", "ZAF", "CHE"}
OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "comtrade"


def trim(src: Path, name: str, keep) -> int:
    obj = json.loads((src / f"kashf_{name}.json").read_text())
    from kashf.comtrade import KEEP     # only the fields Kashf reads, to keep fixtures small
    rows = [{k: r.get(k) for k in KEEP} for r in obj["data"]
            if str(r["cmdCode"]).zfill(6) in CODES and keep(r)]
    params = {k: v for k, v in (obj.get("params") or {}).items() if "key" not in k.lower()}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"kashf_{name}.json").write_text(json.dumps(
        {"query": name, "params": params, "pulled": obj.get("pulled"), "data": rows}, separators=(",", ":")))
    return len(rows)


def _first_per_code(k: int):
    seen: dict = {}

    def keep(r) -> bool:
        c = str(r["cmdCode"]).zfill(6)
        seen[c] = seen.get(c, 0) + 1
        return seen[c] <= k
    return keep


def main(src: str) -> None:
    s = Path(src).expanduser()
    n = {"uae_2023": trim(s, "uae_2023", lambda r: r.get("partnerISO") in PARTNERS),
         "mirror_2023": trim(s, "mirror_2023", lambda r: r.get("reporterISO") in PARTNERS),
         "world_2023": trim(s, "world_2023", _first_per_code(40))}
    print(n)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "~/Downloads")
