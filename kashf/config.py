"""Detector settings. Thresholds marked (tuned) are set on the tuning seed by kashf.evaluate."""

from dataclasses import dataclass, field


@dataclass
class Settings:
    # price benchmark
    price_z: float = 2.0                 # |robust z| at which a line is flagged (calibration weighs it)
    # route
    high_risk: tuple[str, ...] = ("XA", "XB", "XC")   # illustrative; load the current FATF lists in production
    max_legs: int = 4
    # documents
    qty_tolerance: float = 0.03          # invoice vs transport-document quantity
    weight_tolerance: float = 0.15       # invoice vs transport-document gross weight
    doc_late_days: int = 120             # departure this long after the invoice is implausible
    doc_early_days: int = 30
    unit_weight_ratio: float = 4.0       # declared kg/unit vs typical kg/unit for the HS code
    # counterparty graph
    hub_identifier_size: int = 6         # an address/phone shared by this many entities = business centre, ignored
    cycle_max_len: int = 5
    cycle_hop_days: int = 60
    cycle_qty_tolerance: float = 0.10
    # scoring
    alert_threshold: float = 0.5         # (tuned) combined score at which an invoice becomes an alert
    calibration: dict | None = None      # rule -> calibrated strength, from kashf.calibrate (None = heuristic)
    weights: dict = field(default_factory=lambda: {"price": 1.0, "route": 1.0, "documents": 1.0, "graph": 1.0})
