"""Scenarios reconstructed from public FATF/Egmont case boxes (tests/cases/*/case.json).

For schemes visible in trade records, the rule named in the case must fire (the evidence surfaces).
Whether the calibrated score also crosses the alert threshold is reported in results/public_cases.md,
not asserted, because it depends on the calibration fitted to the synthetic generator.
For payment-side schemes (blind spots), no rule may claim to have found them.
"""

import json
from pathlib import Path

import pytest

from kashf.pipeline import analyse, load_dir

CASES = sorted(p.parent for p in (Path(__file__).parent / "cases").glob("*/case.json"))


def test_cases_exist_and_are_labelled():
    assert 5 <= len(CASES) <= 10
    for d in CASES:
        m = json.loads((d / "case.json").read_text())
        assert m["label"] == "reconstructed from public reports"
        assert "fatf-gafi.org" in m["source"] and m["box"] and m["page"]


@pytest.mark.parametrize("d", CASES, ids=[d.name for d in CASES])
def test_case(d):
    m = json.loads((d / "case.json").read_text())
    r = analyse(load_dir(d))
    fired = set(r.signals["rule"])
    if m["expect"] == "blind_spot":
        assert not r.invoices["alert"].any()
    else:
        assert set(m["rules"]) <= fired, f"{d.name}: expected {m['rules']}, got {sorted(fired)}"
