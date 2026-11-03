"""Build a real reference price table from UN Comtrade (replaces the illustrative default).

Needs a free UN Comtrade account (Basic Individual tier: API access, up to 500 calls/day)
and its subscription key:

    export COMTRADE_KEY=...
    python scripts/fetch_comtrade.py --year 2024 --out data/reference_comtrade.csv
    kashf analyse data/demo --reference data/reference_comtrade.csv     (or pass ref= in Python)

For each HS code it pulls exports by all reporters to the world, computes the unit value
of each reporter (value / quantity, or value / net weight for kg-priced goods), and keeps
the median and the median absolute deviation of the log unit values.

NOTE: written against the Comtrade "data/v1/get" endpoint and field names (primaryValue,
qty, netWgt). It could not be tested from the build environment (no network access to
comtradeapi.un.org); check the current API documentation if a call fails.
"""

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kashf.reference import COLUMNS, default_table  # noqa: E402

URL = "https://comtradeapi.un.org/data/v1/get/C/A/HS"


def unit_values(hs6: str, year: int, per_kg: bool, key: str) -> list[float]:
    r = requests.get(URL, params={"cmdCode": hs6, "period": year, "flowCode": "X", "partnerCode": 0},
                     headers={"Ocp-Apim-Subscription-Key": key}, timeout=60)
    r.raise_for_status()
    vals = []
    for row in r.json().get("data", []):
        v = row.get("primaryValue") or 0
        q = (row.get("netWgt") if per_kg else row.get("qty")) or 0
        if v > 0 and q > 0:
            vals.append(v / q)
    return vals


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--out", default="data/reference_comtrade.csv")
    a = ap.parse_args()
    key = os.environ.get("COMTRADE_KEY")
    if not key:
        sys.exit("set COMTRADE_KEY to your UN Comtrade subscription key")
    base = default_table()
    rows = []
    for r in base.itertuples(index=False):
        uv = unit_values(r.hs6, a.year, r.unit == "kg", key)
        time.sleep(1.2)
        if len(uv) < 5:
            print(f"{r.hs6}: only {len(uv)} reporters, keeping illustrative value")
            rows.append(r._asdict())
            continue
        logs = [math.log(x) for x in uv]
        med = statistics.median(logs)
        mad = statistics.median(abs(x - med) for x in logs)
        rows.append({**r._asdict(), "ref_usd": round(math.exp(med), 4), "log_mad": round(max(mad, 0.05), 4)})
        print(f"{r.hs6} {r.description}: median ${math.exp(med):,.2f}/{r.unit} from {len(uv)} reporters")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows)[COLUMNS].to_csv(a.out, index=False)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
