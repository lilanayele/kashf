# Kashf evaluation results

Thresholds tuned on seed 0; mean ± sd over held-out seeds [1, 2, 3, 4, 5] (20,000 invoices each).

## Overall

| Configuration | Precision | Recall | F1 | False-alarm rate | Alerts / 1,000 | Avg. precision |
|---|---|---|---|---|---|---|
| kashf_full | 0.876 ± 0.012 | 0.759 ± 0.008 | 0.814 ± 0.009 | 0.45% ± 0.05 | 35.2 | 0.845 ± 0.005 |
| kashf_heuristic | 0.774 ± 0.009 | 0.789 ± 0.012 | 0.781 ± 0.007 | 0.98% ± 0.06 | 41.4 | 0.797 ± 0.008 |
| minus_price | 0.935 ± 0.008 | 0.560 ± 0.011 | 0.700 ± 0.009 | 0.17% ± 0.02 | 24.3 | 0.611 ± 0.009 |
| minus_route | 0.876 ± 0.012 | 0.759 ± 0.008 | 0.814 ± 0.009 | 0.45% ± 0.05 | 35.2 | 0.842 ± 0.005 |
| minus_documents | 0.842 ± 0.015 | 0.513 ± 0.007 | 0.638 ± 0.009 | 0.41% ± 0.04 | 24.8 | 0.569 ± 0.008 |
| minus_graph | 0.859 ± 0.016 | 0.500 ± 0.010 | 0.632 ± 0.011 | 0.35% ± 0.04 | 23.6 | 0.609 ± 0.012 |
| price_only | 0.574 ± 0.015 | 0.313 ± 0.009 | 0.405 ± 0.011 | 0.98% ± 0.04 | 22.1 | 0.311 ± 0.009 |
| checklist | 0.117 ± 0.006 | 0.562 ± 0.038 | 0.194 ± 0.010 | 17.89% ± 0.97 | 194.5 | 0.084 ± 0.006 |
| isolation_forest | 0.167 ± 0.005 | 0.227 ± 0.021 | 0.192 ± 0.009 | 4.80% ± 0.47 | 55.3 | 0.116 ± 0.004 |

## Recall by typology

| Configuration | over_invoicing | under_invoicing | phantom_shipment | multiple_invoicing | misdescription | circular_trading | shell_cluster |
|---|---|---|---|---|---|---|---|
| kashf_full | 0.43 | 0.28 | 0.67 | 1.00 | 1.00 | 1.00 | 1.00 |
| kashf_heuristic | 0.52 | 0.36 | 0.70 | 1.00 | 1.00 | 1.00 | 1.00 |
| minus_price | 0.00 | 0.00 | 0.69 | 1.00 | 0.33 | 1.00 | 1.00 |
| minus_route | 0.43 | 0.28 | 0.67 | 1.00 | 1.00 | 1.00 | 1.00 |
| minus_documents | 0.43 | 0.28 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 |
| minus_graph | 0.43 | 0.28 | 0.67 | 1.00 | 1.00 | 0.01 | 0.01 |
| price_only | 0.62 | 0.44 | 0.00 | 0.00 | 1.00 | 0.03 | 0.03 |
| checklist | 0.89 | 0.81 | 0.42 | 0.16 | 1.00 | 0.28 | 0.31 |
| isolation_forest | 0.11 | 0.08 | 0.61 | 0.03 | 0.55 | 0.08 | 0.10 |

## Evidence attribution (share of true alerts whose evidence names the planted mechanism)

- kashf_full: 1.000 ± 0.000
- kashf_heuristic: 1.000 ± 0.000
- minus_price: 1.000 ± 0.000
- minus_route: 1.000 ± 0.000
- minus_documents: 1.000 ± 0.000
- minus_graph: 1.000 ± 0.000

## Kashf recall vs. size of price distortion (over- and under-invoicing)

| Distortion vs benchmark | Invoices | Recall |
|---|---|---|
| 1-1.5x | 76 | 0.00 |
| 1.5-2x | 113 | 0.00 |
| 2-3x | 272 | 0.11 |
| 3-4x | 206 | 0.31 |
| 4-6x | 254 | 0.40 |
| 6-10x | 205 | 0.77 |
| >10x | 74 | 0.97 |

Thresholds: kashf_full = 0.442, kashf_heuristic = 0.710, minus_price = 0.321, minus_route = 0.442, minus_documents = 0.565, minus_graph = 0.442, price_only = 0.236, checklist = 0.500, isolation_forest = 0.524
