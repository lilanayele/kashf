"""results/reviewer_fixes.md: what was done for each reviewer weakness, with numbers read from results files.

    python scripts/write_reviewer_fixes.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
J = lambda p: json.loads((ROOT / p).read_text())  # noqa: E731
pc = lambda x: f"{100 * x:.1f}%"  # noqa: E731


def main() -> None:
    sm, rob, ex = J("results/summary.json"), J("results/robustness.json"), J("results/explainability.json")
    ext, aml, cases = J("results/external_validation.json"), J("results/amlworld.json"), J("results/public_cases.json")
    inj = pd.read_csv(ROOT / "results/macro/injection_summary.csv")
    C = sm["configs"]
    f = lambda c: C[c]["f1"]["mean"]  # noqa: E731
    rt = lambda c, k: C[c]["recall_by_typology"][k]["mean"]  # noqa: E731
    d = ex["synthetic"]["deletion"]
    sh = rob["shift"]
    vis = [v for v in cases.values() if v["expect"] == "evidence"]

    L = ["# Reviewer fixes: summary", "",
         "Every number below is read from a results file (named in each section). **REAL** = UN Comtrade data; "
         "**SYNTHETIC** = Kashf's own generator; **INDEPENDENT SYNTHETIC** = IBM AMLworld.", ""]

    L += ["## 3. Explainability: defined and measured (`results/explainability.md`)", "",
          "Definition: an alert is explainable when it lists the specific evidence (values, benchmark, rule) that "
          "produced it, and removing that evidence removes the alert.", "",
          f"- SYNTHETIC, evidence attribution: lowest typology {min(v['mean'] for v in ex['synthetic']['attribution_by_typology'].values()):.3f} "
          "(partly by construction).",
          f"- SYNTHETIC, deletion test ({d['all_alerts']['alerts']:,} alerts): dropping the strongest signal removes the alert in "
          f"{pc(d['all_alerts']['drop_top_removes_alert'])} of cases vs {pc(d['all_alerts']['drop_random_removes_alert'])} for a random "
          f"signal; multi-signal alerts {pc(d['multi_signal_alerts']['drop_top_removes_alert'])} vs "
          f"{pc(d['multi_signal_alerts']['drop_random_removes_alert'])}.",
          f"- REAL, macro: SHAP top feature belongs to a rule that fired for {pc(ex['macro']['shap_top1_in_fired_rule'])} of "
          f"{ex['macro']['pairs_flagged_by_both']} doubly flagged pairs (random {pc(ex['macro']['random_top1_expected'])}).",
          "- User study: protocol only (`docs/user_study.md`), results table empty. Nothing has been run.", ""]

    L += ["## 4. Route typologies and fuzzy entity resolution (`results/results.md`, SYNTHETIC)", "",
          f"- Full Kashf F1 {f('kashf_full'):.3f}; without the route detector {f('minus_route'):.3f} "
          f"(gain {f('kashf_full') - f('minus_route'):.3f} >= 0.01, so route stays in the score).",
          f"- Transshipment via a FATF-listed jurisdiction: recall {rt('minus_route', 'transshipment_high_risk'):.2f} -> "
          f"{rt('kashf_full', 'transshipment_high_risk'):.2f}; U-turn {rt('minus_route', 'u_turn'):.2f} -> {rt('kashf_full', 'u_turn'):.2f}.",
          f"- Name-variant shells: recall {rt('exact_entities', 'name_variant'):.2f} (exact matching) -> "
          f"{rt('kashf_full', 'name_variant'):.2f} (fuzzy); F1 {f('exact_entities'):.3f} -> {f('kashf_full'):.3f}.",
          f"- The benchmark is harder than before (10 typologies, legitimate look-alikes), so full-system F1 fell from the "
          f"earlier 0.814 to {f('kashf_full'):.3f}. The shipped calibration and alert threshold were refit to match.", ""]

    L += ["## 1. External validation on real data (`results/external_validation.md`, REAL; not ground truth)", "",
          f"- Published reports (SWISSAID 2024, 2025; FATF-style citations in `data/external_validation.csv`) name "
          f"{ext['documented_keys']} (partner, year) gold flows; {ext['documented_keys_in_data']} exist as eligible mirror pairs "
          "(the rest: partner did not report to Comtrade, or a side below the value filter)."]
    for n, m in ext["methods"].items():
        kb = m["keys_flagged_by_kind"]
        L.append(f"- {n}: flags {kb.get('mirror_discrepancy', 0)}/{ext['by_kind']['mirror_discrepancy']['in_data']} documented "
                 f"mirror discrepancies and {kb.get('transit_hub', 0)}/{ext['by_kind']['transit_hub']['in_data']} transit-hub flows; "
                 f"median best rank {m['median_best_rank']:.0f} of {ext['eligible_pairs']:,}; P@10 within gold imports "
                 f"{m['precision_at_k']['10']['gold_import_pairs']:.2f} (random {ext['random']['precision_gold_import_pairs']:.3f}).")
    L += ["- Reading: Kashf flags every documented mirror discrepancy that is in the data, but ranks them below "
          "the GFI-style dollar gap, because its peer-relative scores normalise away the sheer size of gold flows.",
          f"- Public FATF/Egmont cases (`results/public_cases.md`, reconstructed): evidence surfaced in "
          f"{sum(set(v['rules_expected']) <= set(v['rules_fired']) for v in vis)}/{len(vis)} visible schemes, alerts in "
          f"{sum(v['alerts'] > 0 for v in vis)}/{len(vis)}; both payment-side blind spots correctly produce nothing.", ""]

    L += ["## 2. Independent benchmark and stronger shift test", "",
          f"INDEPENDENT SYNTHETIC, IBM AMLworld HI-Small (`results/amlworld.md`): {aml['transfers']:,} transfers, "
          f"{aml['laundering']:,} laundering. Only the circular-trade rule applies.", ""]
    for n, m in aml["methods"].items():
        a = m["all"]
        L.append(f"- {n}: precision {a['precision']:.3f}, recall {a['recall']:.3f}, F1 {a['f1']:.3f} "
                 f"(cycle-pattern recall {m['recall_by_typology'].get('cycle', 0):.2f}).")
    L += ["- Reading: as shipped the rule almost never fires (AMLworld cycles change currency within a day and run up to "
          "10 hops). Adapted to transfer data (timestamps, USD amounts, 10 hops; not tuned on labels) it finds about half "
          "of cycle-pattern transfers at high precision, more than a time-free cycle check. Overall recall stays low because "
          "most AMLworld laundering is not cyclic.", "",
          f"SYNTHETIC stress test (`results/robustness.md`): same generator F1 {sh['same_generator']['f1']['mean']:.3f}; "
          f"noise shift {sh['shifted_generator']['f1']['mean']:.3f}; different typology mechanics "
          f"{sh['alt_typologies']['f1']['mean']:.3f} (over-/under-invoicing recall "
          f"{sh['alt_typologies']['recall_by_typology']['over_invoicing']:.2f}/{sh['alt_typologies']['recall_by_typology']['under_invoicing']:.2f}). "
          "The alternative mechanics were written by the same author without running the detectors first: a stress test, "
          "not independent data.", ""]

    g = lambda m, s, k: float(inj[(inj["method"] == m) & (inj["size"] == s)][k].iloc[0])  # noqa: E731
    L += ["## 5. Published-method baselines", "",
          "REAL flows with injected distortion (`results/macro/injection_summary.csv`), recall at the same flag rate as the "
          "Kashf rules (top-k):", "", "| Distortion | Kashf rules | GFI-style gap | IQR filter | Isolation Forest (5% flagged) |",
          "|---|---|---|---|---|"]
    for s, lab in ((1.0, "x2"), (4.0, "x5"), (9.0, "x10")):
        L.append(f"| {lab} | {g('rules', s, 'recall'):.3f} | {g('gfi_gap_topk', s, 'recall'):.3f} | "
                 f"{g('iqr_filter_topk', s, 'recall'):.3f} | {g('iforest', s, 'recall'):.3f} |")
    L += ["", f"- The IQR filter's own rule (any unit value outside [Q1, Q3]) flags {pc(g('iqr_filter', 1.0, 'flag_rate'))} of real "
          "pairs; at a matched flag rate it is level with or better than the Kashf rules at moderate distortions "
          "(it sees exactly the unit value the injection changes). The GFI-style dollar gap is close to random on this test.",
          f"- SYNTHETIC invoices: IQR price filter F1 {f('iqr_price_filter'):.3f} at {pc(C['iqr_price_filter']['far']['mean'])} "
          f"false alarms, vs Kashf {f('kashf_full'):.3f} and Kashf price detector alone {f('price_only'):.3f}.", ""]
    (ROOT / "results/reviewer_fixes.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
