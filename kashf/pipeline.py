"""Load a dataset, run every detector, score, and return the results."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd

from kashf import calibrate, reference
from kashf.config import Settings
from kashf.detectors import run_all
from kashf.scoring import score_entities, score_invoices

DEFAULT_CALIBRATION = Path(__file__).parent / "models" / "calibration.json"
DEFAULT_THRESHOLD = 0.44   # tuned on seed 0 with the shipped calibration (see results/summary.json)
TABLES = ("entities", "invoices", "transport_docs", "packing_lists")
DTYPES = {"hs6": str, "doc_no": str}


def load_dir(path: str | Path) -> dict[str, pd.DataFrame]:
    path = Path(path)
    t = {}
    for name in TABLES:
        f = path / f"{name}.csv"
        if not f.exists():
            raise FileNotFoundError(f"missing {f.name} in {path}")
        t[name] = pd.read_csv(f, dtype=DTYPES)
    lab = path / "labels.csv"
    if lab.exists():
        t["labels"] = pd.read_csv(lab)
    return t


@dataclass
class Result:
    signals: pd.DataFrame
    invoices: pd.DataFrame      # scored, sorted by score
    entities: pd.DataFrame      # company risk
    tables: dict


def analyse(tables: dict[str, pd.DataFrame], settings: Settings | None = None,
            ref: pd.DataFrame | None = None, only: set[str] | None = None) -> Result:
    if settings is None:
        s = Settings(alert_threshold=DEFAULT_THRESHOLD)
        if DEFAULT_CALIBRATION.exists():
            s = replace(s, calibration=calibrate.load(DEFAULT_CALIBRATION))
    else:
        s = settings
    ref = reference.default_table() if ref is None else ref
    sig = run_all(tables, ref, s, only=only)
    if s.calibration:
        sig = calibrate.apply(sig, s.calibration)   # evidence weights shown to analysts = calibrated
    scored = score_invoices(tables["invoices"], sig, s)
    ents = score_entities(scored, tables["entities"])
    return Result(sig, scored, ents, tables)
