"""AMLworld mapping and evaluation on a tiny hand-made sample (the real files are not in the repo)."""

from pathlib import Path

import numpy as np

from kashf.amlworld import load, prf, run, to_invoices, usd_rates

HEADER = "Timestamp,From Bank,Account,To Bank,Account,Amount Received,Receiving Currency,Amount Paid,Payment Currency,Payment Format,Is Laundering"
ROWS = [  # a 3-account USD cycle (laundering), a Euro conversion, and normal noise
    "2022/09/01 10:00,1,A,2,B,1000.00,US Dollar,1000.00,US Dollar,ACH,1",
    "2022/09/02 10:00,2,B,3,C,990.00,US Dollar,990.00,US Dollar,ACH,1",
    "2022/09/03 10:00,3,C,1,A,985.00,US Dollar,985.00,US Dollar,ACH,1",
    "2022/09/01 11:00,4,D,5,E,500.00,Euro,585.00,US Dollar,Wire,0",
    "2022/09/04 12:00,5,E,4,D,20.00,US Dollar,20.00,US Dollar,Cheque,0",
    "2022/09/05 12:00,6,F,6,F,70.00,US Dollar,70.00,US Dollar,Reinvestment,0",
]
PATTERNS = """BEGIN LAUNDERING ATTEMPT - CYCLE:  Max 3 hops
2022/09/01 10:00,1,A,2,B,1000.00,US Dollar,1000.00,US Dollar,ACH,1
2022/09/02 10:00,2,B,3,C,990.00,US Dollar,990.00,US Dollar,ACH,1
2022/09/03 10:00,3,C,1,A,985.00,US Dollar,985.00,US Dollar,ACH,1
END LAUNDERING ATTEMPT - CYCLE
"""


def _files(tmp: Path):
    t, p = tmp / "t.csv", tmp / "p.txt"
    t.write_text(HEADER + "\n" + "\n".join(ROWS) + "\n")
    p.write_text(PATTERNS)
    return t, p


def test_load_and_mapping(tmp_path):
    df = load(*_files(tmp_path))
    assert (df["typology"] == "cycle").sum() == 3 and df["y"].sum() == 3
    inv = to_invoices(df)
    assert inv.loc[0, "seller_id"] == "1:A" and inv.loc[0, "buyer_id"] == "2:B"   # value passes payer -> payee
    assert abs(usd_rates(df)["Euro"] - 1.17) < 1e-9


def test_run_finds_the_cycle(tmp_path):
    t, p = _files(tmp_path)
    r = run(t, p, tmp_path / "out")
    m = r["methods"]["kashf_cycle_as_shipped"]
    assert m["all"]["recall"] == 1.0 and m["all"]["precision"] == 1.0
    assert (tmp_path / "out" / "amlworld.md").exists()


def test_prf():
    out = prf(np.array([True, True, False]), np.array([True, False, True]))
    assert out["precision"] == 0.5 and out["recall"] == 0.5
