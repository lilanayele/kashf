# Kashf invoice-layer results (SYNTHETIC invoices)

Data: synthetic invoices from kashf.generate (not real trade). Reference prices: data/reference_comtrade.csv. Real-data results are in results/macro/.

Thresholds tuned on seed 0; mean ± sd over held-out seeds [1, 2, 3, 4, 5] (20,000 invoices each).

## Overall

| Configuration | Precision | Recall | F1 | False-alarm rate | Alerts / 1,000 | Avg. precision |
|---|---|---|---|---|---|---|
| kashf_full | 0.876 ± 0.009 | 0.606 ± 0.007 | 0.717 ± 0.005 | 0.52% ± 0.05 | 39.7 | 0.748 ± 0.005 |
| kashf_heuristic | 0.614 ± 0.008 | 0.616 ± 0.011 | 0.615 ± 0.008 | 2.36% ± 0.07 | 57.5 | 0.638 ± 0.009 |
| minus_price | 0.956 ± 0.005 | 0.515 ± 0.008 | 0.669 ± 0.007 | 0.14% ± 0.02 | 30.9 | 0.653 ± 0.005 |
| minus_route | 0.898 ± 0.007 | 0.547 ± 0.006 | 0.679 ± 0.003 | 0.38% ± 0.03 | 34.9 | 0.625 ± 0.003 |
| minus_documents | 0.841 ± 0.015 | 0.422 ± 0.007 | 0.562 ± 0.004 | 0.49% ± 0.06 | 28.8 | 0.544 ± 0.003 |
| minus_graph | 0.827 ± 0.014 | 0.355 ± 0.004 | 0.497 ± 0.005 | 0.45% ± 0.04 | 24.6 | 0.503 ± 0.006 |
| exact_entities | 0.855 ± 0.010 | 0.542 ± 0.006 | 0.664 ± 0.006 | 0.56% ± 0.04 | 36.4 | 0.682 ± 0.006 |
| price_only | 0.298 ± 0.018 | 0.192 ± 0.017 | 0.234 ± 0.018 | 2.74% ± 0.05 | 36.8 | 0.174 ± 0.009 |
| checklist | 0.072 ± 0.002 | 0.643 ± 0.007 | 0.130 ± 0.004 | 50.26% ± 1.21 | 510.7 | 0.067 ± 0.002 |
| iqr_price_filter | 0.069 ± 0.002 | 0.621 ± 0.018 | 0.125 ± 0.004 | 50.76% ± 0.39 | 514.1 | 0.208 ± 0.010 |
| isolation_forest | 0.172 ± 0.011 | 0.239 ± 0.013 | 0.200 ± 0.009 | 7.03% ± 0.57 | 80.0 | 0.122 ± 0.006 |

## Recall by typology

| Configuration | over_invoicing | under_invoicing | phantom_shipment | multiple_invoicing | misdescription | circular_trading | shell_cluster | transshipment_high_risk | u_turn | name_variant |
|---|---|---|---|---|---|---|---|---|---|---|
| kashf_full | 0.26 | 0.06 | 0.68 | 1.00 | 0.78 | 1.00 | 1.00 | 0.49 | 0.08 | 0.84 |
| kashf_heuristic | 0.28 | 0.18 | 1.00 | 1.00 | 0.77 | 1.00 | 1.00 | 0.13 | 0.22 | 0.68 |
| minus_price | 0.00 | 0.00 | 0.67 | 1.00 | 0.33 | 1.00 | 1.00 | 0.48 | 0.00 | 0.84 |
| minus_route | 0.25 | 0.06 | 0.67 | 1.00 | 0.78 | 1.00 | 1.00 | 0.00 | 0.02 | 0.84 |
| minus_documents | 0.26 | 0.08 | 0.00 | 0.00 | 0.67 | 1.00 | 1.00 | 0.49 | 0.08 | 0.84 |
| minus_graph | 0.26 | 0.08 | 0.68 | 1.00 | 0.78 | 0.00 | 0.01 | 0.49 | 0.08 | 0.01 |
| exact_entities | 0.26 | 0.08 | 0.68 | 1.00 | 0.78 | 1.00 | 1.00 | 0.49 | 0.08 | 0.03 |
| price_only | 0.46 | 0.17 | 0.02 | 0.03 | 0.86 | 0.08 | 0.06 | 0.03 | 0.08 | 0.07 |
| checklist | 0.84 | 0.78 | 0.65 | 0.53 | 0.97 | 0.62 | 0.56 | 0.48 | 0.54 | 0.42 |
| iqr_price_filter | 0.82 | 0.78 | 0.47 | 0.52 | 0.95 | 0.48 | 0.55 | 0.47 | 0.56 | 0.58 |
| isolation_forest | 0.14 | 0.09 | 0.69 | 0.05 | 0.62 | 0.07 | 0.07 | 0.51 | 0.04 | 0.01 |

## Evidence attribution (share of true alerts whose evidence names the planted mechanism)

- kashf_full: 1.000 ± 0.001
- kashf_heuristic: 0.999 ± 0.001
- minus_price: 1.000 ± 0.000
- minus_route: 1.000 ± 0.001
- minus_documents: 1.000 ± 0.001
- minus_graph: 1.000 ± 0.001

## Kashf recall vs. size of price distortion (over- and under-invoicing)

| Distortion vs benchmark | Invoices | Recall |
|---|---|---|
| 1-1.5x | 142 | 0.00 |
| 1.5-2x | 136 | 0.00 |
| 2-3x | 212 | 0.01 |
| 3-4x | 153 | 0.12 |
| 4-6x | 193 | 0.18 |
| 6-10x | 165 | 0.42 |
| >10x | 199 | 0.35 |

Thresholds: kashf_full = 0.365, kashf_heuristic = 0.672, minus_price = 0.476, minus_route = 0.517, minus_documents = 0.364, minus_graph = 0.336, exact_entities = 0.336, price_only = 0.139, checklist = 0.500, iqr_price_filter = 0.000, isolation_forest = 0.495
