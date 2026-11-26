"""Fill README's real-data section and write PITCH_NOTES.md from the result files.

    python scripts/write_notes.py

Every number comes from a results file written by the code; nothing is typed by hand.
Sections whose results do not exist yet say "pending" instead of showing a number.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MACRO = ROOT / "results" / "macro"
START, END = "<!-- REAL_RESULTS_START -->", "<!-- REAL_RESULTS_END -->"


def macro_md() -> str | None:
    f = MACRO / "macro_results.md"
    return f.read_text() if f.exists() else None


def robustness() -> dict:
    return json.loads((ROOT / "results" / "robustness.json").read_text())


def synthetic() -> dict:
    return json.loads((ROOT / "results" / "summary.json").read_text())["configs"]


def fill_readme() -> None:
    readme = ROOT / "README.md"
    s = readme.read_text()
    md = macro_md()
    if md:
        body = md.replace("# Macro layer results: REAL UN Comtrade mirror data", "").strip()
        body = re.sub(r"^## ", "#### ", body, flags=re.M)
        block = (f"{START}\n### Real-data results (UN Comtrade)\n\n"
                 "*Label: real (UN Comtrade) flows; detection rates use injected distortions on those real flows.*\n\n"
                 f"{body}\n{END}")
    else:
        block = (f"{START}\n### Real-data results (UN Comtrade)\n\n"
                 f"*Pending: run `bash scripts/run_real.sh` to fill this section.*\n{END}")
    if START in s:
        s = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, s, flags=re.S)
    else:
        anchor = "Data source, coverage and caveats:"
        s = s.replace(anchor, block + "\n\n" + anchor, 1)
    readme.write_text(s)


def pitch_notes() -> str:
    syn = synthetic()["kashf_full"]
    rb = robustness()["shift"]
    same, shifted = rb["same_generator"], rb["shifted_generator"]
    md = macro_md()
    summ = pd.read_csv(MACRO / "injection_summary.csv") if (MACRO / "injection_summary.csv").exists() else None
    cs = pd.read_csv(MACRO / "case_study.csv", dtype={"hs6": str}) if (MACRO / "case_study.csv").exists() else None
    stats = None
    if md:
        m = re.search(r"Mirror pairs: ([\d,]+) \(eligible, both sides >= ([^:]+): ([\d,]+)\)", md)
        y = re.search(r"Years: ([^;]+); partners: (\d+); HS6 codes: (\d+)", md)
        fr = re.search(r"Flag rate on real data: rules ([\d.]+%), Isolation Forest ([\d.]+%)", md)
        stats = {"pairs": m.group(1), "min": m.group(2), "eligible": m.group(3), "years": y.group(1),
                 "partners": y.group(2), "hs6": y.group(3), "rule_rate": fr.group(1), "if_rate": fr.group(2)}

    def inj(method: str, size: float, col: str) -> str:
        if summ is None:
            return "pending"
        r = summ[(summ["method"] == method) & (summ["size"].round(2) == round(size, 2))]
        return "pending" if r.empty else f"{r[col].iloc[0]:.2f}"

    P = "*pending: run scripts/run_real.sh*"
    L = ["# Kashf: pitch notes", "",
         "Every number below is copied by `scripts/write_notes.py` from a results file. "
         "Each is labelled **real (UN Comtrade)** or **synthetic**.", "",
         "## 5 bullets for judges", ""]
    if stats:
        L.append(f"1. **Real data.** Kashf compares what the UAE and its partners each reported for the same trade: "
                 f"{stats['pairs']} UAE x partner x product x year mirror pairs ({stats['eligible']} with both sides "
                 f">= {stats['min']}), {stats['partners']} partner countries, {stats['hs6']} HS6 products, years "
                 f"{stats['years']}. *real (UN Comtrade)*")
    else:
        L.append(f"1. **Real data.** Mirror pairs from UAE and partner reports to UN Comtrade. {P}")
    L.append("2. **Novel combination.** To my knowledge, no open tool combines country-level mirror statistics on "
             "real trade data with invoice-level evidence checks for one trader, with a benign explanation "
             "attached to every flag. (Say \"to my knowledge\", not \"first\".)")
    L.append(f"3. **Measured detection on real flows.** Known misinvoicing injected into real flows: rules recall "
             f"{inj('rules', 0.25, 'recall')} at ±25% and {inj('rules', 1.0, 'recall')} at ±100%; Isolation Forest "
             f"{inj('iforest', 0.25, 'recall')} / {inj('iforest', 1.0, 'recall')}. PR-AUC at ±50%: rules "
             f"{inj('rules', 0.5, 'pr_auc')}, IF {inj('iforest', 0.5, 'pr_auc')} (random = "
             f"{inj('rules', 0.5, 'pr_auc_random')}). *real flows + injected distortion*")
    L.append(f"4. **Invoice layer (synthetic) with an honest stress test.** F1 {syn['f1']['mean']:.2f} and false-alarm "
             f"rate {100 * syn['far']['mean']:.2f}% on the benchmark; on test data from a shifted generator F1 drops "
             f"{same['f1']['mean']:.2f} -> {shifted['f1']['mean']:.2f} and false alarms rise to "
             f"{100 * shifted['far']['mean']:.2f}%. *synthetic*")
    L.append("5. **Explainable, not accusatory.** Every alert shows the numbers behind it and the benign causes to "
             "rule out first (re-exports, free zones, CIF/FOB, timing, classification). Kashf ranks what to look at; "
             "a human decides.")
    L += ["", "## Top flagged real flows (for the demo)", ""]
    if cs is not None and len(cs):
        for _, r in cs.head(3).iterrows():
            arrow = f"UAE -> {r['partner_iso']}" if r["direction"] == "uae_export" else f"{r['partner_iso']} -> UAE"
            L.append(f"- **{arrow}, HS {r['hs6']} {r.get('product', '') if isinstance(r.get('product'), str) else ''}, "
                     f"{r['year']}**: {r['why_flagged']}  \n  Check first: {r['benign_explanations']}")
    else:
        L.append(P)
    L += ["", "## 3 honest limitations", "",
          "1. **No ground-truth labels on real data.** Real detection rates come from injected distortions; precision "
          "counts every natural anomaly as a false alarm, so it is a lower bound.",
          "2. **Mirror gaps have many innocent causes.** Re-exports, free zones, origin attribution, CIF/FOB and timing "
          "all create gaps; the 10% CIF/FOB margin is an assumption.",
          f"3. **The invoice layer is still synthetic**, and its weights do not fully transfer: F1 "
          f"{same['f1']['mean']:.2f} -> {shifted['f1']['mean']:.2f} under generator shift. It needs analyst-labelled "
          "real cases.",
          "", "## Likely questions", "",
          "**\"Is the gap just re-exports?\"** Often, yes, and Kashf says so. It reports the re-export share of every "
          "UAE flow and lists re-exports first among the benign explanations when it is above 50%. A flag means "
          "\"look here\", not \"laundering\". The interesting flows are the ones where re-exports, CIF/FOB and timing "
          "cannot explain the size of the gap.",
          "",
          "**\"Is your data real?\"** The macro layer: yes, UN Comtrade reports from the UAE and its partners "
          "(docs/DATA_CARD.md has the pull date and coverage). The invoice layer: no, synthetic, because real "
          "invoices with laundering labels are confidential. Its reference prices come from real Comtrade medians.",
          "",
          "**\"How do you avoid false accusations?\"** Three ways: the macro layer works on country x product "
          "aggregates, never on named companies; every flag carries its evidence and the innocent explanations to "
          "check first; and Kashf never files reports. The analyst and the MLRO decide. False-alarm rates are "
          "reported next to every recall figure.",
          "",
          "**\"Why not deep learning?\"** No labelled real data exists to train it, and analysts need evidence they "
          "can verify. An Isolation Forest is included as the ML comparison.",
          ""]
    return "\n".join(L)


def main() -> None:
    fill_readme()
    (ROOT / "PITCH_NOTES.md").write_text(pitch_notes())
    print("updated README.md and wrote PITCH_NOTES.md")


if __name__ == "__main__":
    main()
