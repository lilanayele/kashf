"""Settings. All thresholds are read from configs/default.yaml (or a YAML file you pass).

Thresholds marked (tuned) in the YAML are re-chosen on the tuning seed by kashf.evaluate.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Optional, Union

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "default.yaml"


FATF_LISTS = Path(__file__).resolve().parent.parent / "configs" / "fatf_lists.yaml"


def fatf_lists(path: Optional[Union[str, Path]] = None) -> dict[str, Any]:
    """FATF call-for-action and increased-monitoring lists (configs/fatf_lists.yaml), with their date."""
    import yaml

    p = Path(path) if path else FATF_LISTS
    d = yaml.safe_load(p.read_text())
    for k in ("as_of", "sources", "call_for_action", "increased_monitoring"):
        if not d.get(k):
            raise ValueError(f"{p.name} is missing '{k}'")
    return d


def fatf_high_risk(path: Optional[Union[str, Path]] = None) -> tuple[str, ...]:
    d = fatf_lists(path)
    return tuple(sorted(set(d["call_for_action"]) | set(d["increased_monitoring"])))


def load_yaml(path: Optional[Union[str, Path]] = None) -> dict[str, Any]:
    """Load the YAML config: the given path, else $KASHF_CONFIG, else configs/default.yaml at the repo root."""
    import yaml

    p = Path(path) if path else Path(os.environ.get("KASHF_CONFIG", DEFAULT_CONFIG))
    if not p.exists():
        raise FileNotFoundError(f"config not found: {p}")
    return yaml.safe_load(p.read_text()) or {}


@dataclass
class Settings:
    # price benchmark
    price_z: float = 2.0
    # route
    high_risk: tuple[str, ...] = ("XA", "XB", "XC")   # placeholder; from_yaml loads the real FATF lists
    high_risk_note: str = ""              # e.g. "FATF lists as of 2026-10-30", shown in evidence
    max_legs: int = 4
    u_turn_days: int = 90                 # export from AE and re-import from the same party within this window
    # documents
    qty_tolerance: float = 0.03
    weight_tolerance: float = 0.15
    doc_late_days: int = 120
    doc_early_days: int = 30
    unit_weight_ratio: float = 4.0
    # counterparty graph
    hub_identifier_size: int = 6
    cycle_max_len: int = 5
    cycle_hop_days: int = 60
    cycle_qty_tolerance: float = 0.10
    cycle_max_expansions: int = 200_000
    entity_resolution: str = "fuzzy"      # "exact" = identifiers must match as written; "fuzzy" = kashf.entities
    name_similarity: float = 90.0         # rapidfuzz token_sort_ratio (0-100) for near-identical names
    address_similarity: float = 85.0      # rapidfuzz token_set_ratio (0-100) required alongside a name match
    # scoring
    alert_threshold: float = 0.5          # (tuned) combined score at which an invoice becomes an alert
    calibration: Optional[dict] = None    # rule -> calibrated strength, from kashf.calibrate (None = heuristic)
    weights: dict = field(default_factory=lambda: {"price": 1.0, "route": 1.0, "documents": 1.0, "graph": 1.0})

    @classmethod
    def from_yaml(cls, path: Optional[Union[str, Path]] = None, **overrides: Any) -> "Settings":
        """Settings from the `invoice:` section of the YAML config, with optional overrides."""
        sec = dict(load_yaml(path).get("invoice", {}))
        known = {f.name for f in fields(cls)}
        unknown = set(sec) - known
        if unknown:
            raise ValueError(f"unknown invoice settings in config: {sorted(unknown)}")
        if sec.get("high_risk") == "fatf":
            sec["high_risk"] = fatf_high_risk()
            sec["high_risk_note"] = f"FATF lists as of {fatf_lists()['as_of']}"
        elif "high_risk" in sec:
            sec["high_risk"] = tuple(sec["high_risk"])
        sec.update(overrides)
        return cls(**sec)
