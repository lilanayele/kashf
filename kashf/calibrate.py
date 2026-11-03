"""Per-rule calibration.

Hand-set signal strengths are a guess. Calibration replaces each rule's strength
with how often that rule was right on a labelled tuning set:

    strength(rule) = (TP + 1) / (fired + 2)          (Laplace-smoothed precision)

Price signals are calibrated per band of the robust z-score, because a price 2σ off
the benchmark means something very different from one 8σ off.

The explanation then reads naturally: "signals of this kind were laundering in 87%
of tuning cases". Calibrate on synthetic data for development; on a real deployment,
recalibrate on cases an analyst has already closed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

Z_BANDS = [(2, 3), (3, 4), (4, 5), (5, 7), (7, math.inf)]


def rule_key(rule: str, value: float) -> str:
    if rule in ("over_priced", "under_priced") and not math.isnan(value):
        z = abs(value)
        for lo, hi in Z_BANDS:
            if lo <= z < hi:
                return f"{rule}|z{lo}-{hi if hi != math.inf else 'inf'}"
    return rule


def fit(signals: pd.DataFrame, labels: pd.DataFrame, floor: float = 0.02, cap: float = 0.98) -> dict[str, float]:
    lab = labels.set_index("invoice_no")["typology"] != "none"
    sg = signals.copy()
    sg["key"] = [rule_key(r, v) for r, v in zip(sg["rule"], sg["value"])]
    sg = sg.drop_duplicates(["invoice_no", "key"])
    sg["pos"] = sg["invoice_no"].map(lab).fillna(False)
    g = sg.groupby("key")["pos"].agg(["sum", "count"])
    return {k: float(min(cap, max(floor, (r["sum"] + 1) / (r["count"] + 2)))) for k, r in g.iterrows()}


def apply(signals: pd.DataFrame, table: dict[str, float]) -> pd.DataFrame:
    sg = signals.copy()
    keys = [rule_key(r, v) for r, v in zip(sg["rule"], sg["value"])]
    sg["strength"] = [table.get(k, s) for k, s in zip(keys, sg["strength"])]
    return sg


def save(table: dict[str, float], path: str | Path) -> None:
    Path(path).write_text(json.dumps(dict(sorted(table.items())), indent=2))


def load(path: str | Path) -> dict[str, float]:
    return json.loads(Path(path).read_text())
