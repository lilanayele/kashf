# Explainability measurements

Definition: an alert is explainable when it lists the specific evidence (values, benchmark, rule) that produced it, and removing that evidence removes the alert.

## 1. Evidence attribution by typology (SYNTHETIC (kashf.generate), held-out seeds)

Share of true alerts whose evidence names the planted mechanism.

| Typology | Attribution | Seeds |
|---|---|---|
| over_invoicing | 1.000 | 5 |
| under_invoicing | 1.000 | 5 |
| phantom_shipment | 1.000 | 5 |
| multiple_invoicing | 1.000 | 5 |
| misdescription | 1.000 | 5 |
| circular_trading | 1.000 | 5 |
| shell_cluster | 1.000 | 5 |
| transshipment_high_risk | 1.000 | 5 |
| u_turn | 1.000 | 5 |
| name_variant | 0.995 | 5 |

## 2. Deletion test (SYNTHETIC (kashf.generate), held-out seeds, alert threshold 0.334)

| Alerts | n | Drop strongest signal -> no alert | Drop random signal -> no alert | Strongest signal alone is an alert |
|---|---|---|---|---|
| all alerts | 4,480 | 90.6% | 75.6% | 93.5% |
| multi signal alerts | 1,928 | 78.2% | 43.3% | 85.0% |
| true alerts | 3,899 | 89.3% | 73.8% | 97.3% |
| false alerts | 581 | 99.8% | 87.6% | 68.5% |

Single-signal alerts: 57.0% of all alerts (for these the strongest and the random signal are the same, and removing it always removes the alert).

## 3. Macro layer: SHAP vs rules (REAL (UN Comtrade), results/macro/flags.csv)

Pairs flagged by both the rules and the Isolation Forest: 378 (Isolation Forest flags reproduced exactly for 100.0% of pairs).

- SHAP top feature belongs to a rule that fired: 97.1%
- One of SHAP's top two features belongs to a rule that fired: 99.5%
- Expected top-1 agreement if SHAP picked a feature at random: 36.3%

No user study has been run; see docs/user_study.md for the protocol.
