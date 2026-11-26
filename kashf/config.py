"""Settings. All thresholds are read from configs/default.yaml (or a YAML file you pass).

Thresholds marked (tuned) in the YAML are re-chosen on the tuning seed by kashf.evaluate.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Optional, Union

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "default.yaml"


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
    high_risk: tuple[str, ...] = ("XA", "XB", "XC")
    max_legs: int = 4
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
        if "high_risk" in sec:
            sec["high_risk"] = tuple(sec["high_risk"])
        sec.update(overrides)
        return cls(**sec)
