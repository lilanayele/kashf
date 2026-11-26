# Reviewer fixes: summary

Every number below is read from a results file (named in each section). **REAL** = UN Comtrade data; **SYNTHETIC** = Kashf's own generator; **INDEPENDENT SYNTHETIC** = IBM AMLworld.

## 3. Explainability: defined and measured (`results/explainability.md`)

Definition: an alert is explainable when it lists the specific evidence (values, benchmark, rule) that produced it, and removing that evidence removes the alert.

- SYNTHETIC, evidence attribution: lowest typology 0.995 (partly by construction).
- SYNTHETIC, deletion test (4,480 alerts): dropping the strongest signal removes the alert in 90.6% of cases vs 75.6% for a random signal; multi-signal alerts 78.2% vs 43.3%.
- REAL, macro: SHAP top feature belongs to a rule that fired for 97.1% of 378 doubly flagged pairs (random 36.3%).
- User study: protocol only (`docs/user_study.md`), results table empty. Nothing has been run.

## 4. Route typologies and fuzzy entity resolution (`results/results.md`, SYNTHETIC)

- Full Kashf F1 0.762; without the route detector 0.727 (gain 0.035 >= 0.01, so route stays in the score).
- Transshipment via a FATF-listed jurisdiction: recall 0.00 -> 0.51; U-turn 0.03 -> 0.17.
- Name-variant shells: recall 0.03 (exact matching) -> 0.87 (fuzzy); F1 0.714 -> 0.762.
- The benchmark is harder than before (10 typologies, legitimate look-alikes), so full-system F1 fell from the earlier 0.814 to 0.762. The shipped calibration and alert threshold were refit to match.

## 1. External validation on real data (`results/external_validation.md`, REAL; not ground truth)

- Published reports (SWISSAID 2024, 2025; FATF-style citations in `data/external_validation.csv`) name 24 (partner, year) gold flows; 10 exist as eligible mirror pairs (the rest: partner did not report to Comtrade, or a side below the value filter).
- kashf_rules: flags 4/4 documented mirror discrepancies and 0/6 transit-hub flows; median best rank 4962 of 9,727; P@10 within gold imports 0.00 (random 0.042).
- isolation_forest: flags 4/4 documented mirror discrepancies and 0/6 transit-hub flows; median best rank 5000 of 9,727; P@10 within gold imports 0.10 (random 0.042).
- gfi_gap: flags 4/4 documented mirror discrepancies and 2/6 transit-hub flows; median best rank 361 of 9,727; P@10 within gold imports 0.30 (random 0.042).
- iqr_filter: flags 0/4 documented mirror discrepancies and 0/6 transit-hub flows; median best rank 4572 of 9,727; P@10 within gold imports 0.00 (random 0.042).
- Reading: Kashf flags every documented mirror discrepancy that is in the data, but ranks them below the GFI-style dollar gap, because its peer-relative scores normalise away the sheer size of gold flows.
- Public FATF/Egmont cases (`results/public_cases.md`, reconstructed): evidence surfaced in 4/4 visible schemes, alerts in 1/4; both payment-side blind spots correctly produce nothing.

## 2. Independent benchmark and stronger shift test

INDEPENDENT SYNTHETIC, IBM AMLworld HI-Small (`results/amlworld.md`): 5,078,345 transfers, 5,177 laundering. Only the circular-trade rule applies.

- kashf_cycle_as_shipped: precision 0.880, recall 0.008, F1 0.017 (cycle-pattern recall 0.01).
- kashf_cycle_adapted: precision 0.952, recall 0.039, F1 0.074 (cycle-pattern recall 0.52).
- fan_out_degree_k14: precision 0.002, recall 0.247, F1 0.004 (cycle-pattern recall 0.02).
- fan_in_degree_k12: precision 0.013, recall 0.183, F1 0.024 (cycle-pattern recall 0.02).
- timefree_cycle_3to5: precision 0.139, recall 0.057, F1 0.081 (cycle-pattern recall 0.30).
- random_same_count: precision 0.000, recall 0.000, F1 0.000 (cycle-pattern recall 0.00).
- Reading: as shipped the rule almost never fires (AMLworld cycles change currency within a day and run up to 10 hops). Adapted to transfer data (timestamps, USD amounts, 10 hops; not tuned on labels) it finds about half of cycle-pattern transfers at high precision, more than a time-free cycle check. Overall recall stays low because most AMLworld laundering is not cyclic.

SYNTHETIC stress test (`results/robustness.md`): same generator F1 0.764; noise shift 0.647; different typology mechanics 0.720 (over-/under-invoicing recall 0.12/0.06). The alternative mechanics were written by the same author without running the detectors first: a stress test, not independent data.

## 5. Published-method baselines

REAL flows with injected distortion (`results/macro/injection_summary.csv`), recall at the same flag rate as the Kashf rules (top-k):

| Distortion | Kashf rules | GFI-style gap | IQR filter | Isolation Forest (5% flagged) |
|---|---|---|---|---|
| x2 | 0.134 | 0.099 | 0.171 | 0.071 |
| x5 | 0.287 | 0.113 | 0.308 | 0.141 |
| x10 | 0.453 | 0.122 | 0.408 | 0.214 |

- The IQR filter's own rule (any unit value outside [Q1, Q3]) flags 54.7% of real pairs; at a matched flag rate it is level with or better than the Kashf rules at moderate distortions (it sees exactly the unit value the injection changes). The GFI-style dollar gap is close to random on this test.
- SYNTHETIC invoices: IQR price filter F1 0.134 at 51.7% false alarms, vs Kashf 0.762 and Kashf price detector alone 0.334.

