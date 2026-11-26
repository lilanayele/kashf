"""Explainability measurements: deletion test and signal weighting."""

import numpy as np
import pandas as pd

from kashf.config import Settings
from kashf.explain_eval import deletion_test, noisy_or, signal_weights


def _best(rows):
    return pd.DataFrame(rows, columns=["invoice_no", "rule", "ws"])


def test_noisy_or_matches_eq3():
    assert noisy_or(np.array([])) == 0.0
    assert abs(noisy_or(np.array([0.5, 0.5])) - 0.75) < 1e-12


def test_deletion_single_signal_alert_always_removed():
    d = deletion_test(_best([("A", "r1", 0.9)]), thr=0.5, rng=np.random.default_rng(0))
    assert len(d) == 1 and d.loc[0, "drop_top"] and d.loc[0, "drop_random"] and d.loc[0, "top_alone"]


def test_deletion_redundant_evidence_survives():
    # two strong independent signals: dropping either leaves an alert
    d = deletion_test(_best([("A", "r1", 0.9), ("A", "r2", 0.8)]), thr=0.5, rng=np.random.default_rng(0))
    assert not d.loc[0, "drop_top"] and not d.loc[0, "drop_random"]


def test_deletion_top_vs_weak_signal():
    # strong signal carries the alert; the weak one does not
    rows = [("A", "strong", 0.6), ("A", "weak", 0.05)]
    d = deletion_test(_best(rows), thr=0.5, rng=np.random.default_rng(0))
    assert d.loc[0, "drop_top"]
    # below-threshold invoices are not alerts and are skipped
    assert deletion_test(_best([("B", "weak", 0.1)]), thr=0.5, rng=np.random.default_rng(0)).empty


def test_signal_weights_keeps_strongest_per_rule_and_applies_calibration():
    sig = pd.DataFrame({"invoice_no": ["A", "A", "A"], "detector": ["graph", "graph", "route"],
                        "rule": ["linked_parties", "linked_parties", "high_risk_party"],
                        "strength": [0.75, 0.5, 0.45], "value": [np.nan] * 3, "evidence": ["x"] * 3})
    s = Settings(calibration={"linked_parties": 0.9, "high_risk_party": 0.05})
    b = signal_weights(sig, s).set_index("rule")["ws"]
    assert len(b) == 2 and abs(b["linked_parties"] - 0.9) < 1e-9 and abs(b["high_risk_party"] - 0.05) < 1e-9
