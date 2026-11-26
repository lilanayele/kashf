# Kashf invoice-layer results (SYNTHETIC invoices)

Data: synthetic invoices from kashf.generate (not real trade). Reference prices: data/reference_comtrade.csv. Real-data results are in results/macro/.

Thresholds tuned on seed 0; mean ± sd over held-out seeds [1, 2, 3, 4, 5] (20,000 invoices each).

## Overall

| Configuration | Precision | Recall | F1 | False-alarm rate | Alerts / 1,000 | Avg. precision |
|---|---|---|---|---|---|---|
| kashf_full | 0.861 ± 0.012 | 0.673 ± 0.004 | 0.755 ± 0.005 | 0.46% ± 0.05 | 31.8 | 0.754 ± 0.009 |
| kashf_heuristic | 0.683 ± 0.019 | 0.679 ± 0.008 | 0.681 ± 0.010 | 1.34% ± 0.12 | 40.5 | 0.712 ± 0.008 |
| minus_price | 0.943 ± 0.007 | 0.558 ± 0.010 | 0.701 ± 0.008 | 0.14% ± 0.02 | 24.0 | 0.613 ± 0.009 |
| minus_route | 0.868 ± 0.016 | 0.670 ± 0.005 | 0.756 ± 0.006 | 0.43% ± 0.06 | 31.4 | 0.747 ± 0.009 |
| minus_documents | 0.764 ± 0.018 | 0.425 ± 0.009 | 0.546 ± 0.011 | 0.56% ± 0.05 | 22.6 | 0.465 ± 0.010 |
| minus_graph | 0.830 ± 0.017 | 0.411 ± 0.005 | 0.550 ± 0.007 | 0.36% ± 0.04 | 20.2 | 0.512 ± 0.013 |
| price_only | 0.605 ± 0.031 | 0.164 ± 0.008 | 0.257 ± 0.013 | 0.45% ± 0.04 | 11.0 | 0.193 ± 0.011 |
| checklist | 0.057 ± 0.002 | 0.710 ± 0.014 | 0.106 ± 0.003 | 49.73% ± 1.12 | 505.9 | 0.052 ± 0.002 |
| isolation_forest | 0.143 ± 0.015 | 0.239 ± 0.015 | 0.178 ± 0.014 | 6.14% ± 0.68 | 68.6 | 0.096 ± 0.006 |

## Recall by typology

| Configuration | over_invoicing | under_invoicing | phantom_shipment | multiple_invoicing | misdescription | circular_trading | shell_cluster |
|---|---|---|---|---|---|---|---|
| kashf_full | 0.25 | 0.08 | 0.67 | 1.00 | 0.78 | 1.00 | 1.00 |
| kashf_heuristic | 0.25 | 0.14 | 0.72 | 1.00 | 0.72 | 1.00 | 1.00 |
| minus_price | 0.00 | 0.00 | 0.67 | 1.00 | 0.33 | 1.00 | 1.00 |
| minus_route | 0.25 | 0.06 | 0.67 | 1.00 | 0.78 | 1.00 | 1.00 |
| minus_documents | 0.25 | 0.17 | 0.00 | 0.00 | 0.67 | 1.00 | 1.00 |
| minus_graph | 0.25 | 0.08 | 0.67 | 1.00 | 0.78 | 0.00 | 0.01 |
| price_only | 0.25 | 0.17 | 0.00 | 0.00 | 0.67 | 0.00 | 0.01 |
| checklist | 0.84 | 0.78 | 0.65 | 0.53 | 0.97 | 0.62 | 0.56 |
| isolation_forest | 0.12 | 0.07 | 0.69 | 0.04 | 0.59 | 0.07 | 0.06 |

## Evidence attribution (share of true alerts whose evidence names the planted mechanism)

- kashf_full: 1.000 ± 0.000
- kashf_heuristic: 1.000 ± 0.001
- minus_price: 1.000 ± 0.000
- minus_route: 1.000 ± 0.000
- minus_documents: 1.000 ± 0.000
- minus_graph: 1.000 ± 0.000

## Kashf recall vs. size of price distortion (over- and under-invoicing)

| Distortion vs benchmark | Invoices | Recall |
|---|---|---|
| 1-1.5x | 142 | 0.00 |
| 1.5-2x | 136 | 0.00 |
| 2-3x | 212 | 0.01 |
| 3-4x | 153 | 0.14 |
| 4-6x | 193 | 0.18 |
| 6-10x | 165 | 0.42 |
| >10x | 199 | 0.36 |

Thresholds: kashf_full = 0.361, kashf_heuristic = 0.700, minus_price = 0.862, minus_route = 0.501, minus_documents = 0.327, minus_graph = 0.361, price_only = 0.327, checklist = 0.500, isolation_forest = 0.508
