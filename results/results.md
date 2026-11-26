# Kashf invoice-layer results (SYNTHETIC invoices)

Data: synthetic invoices from kashf.generate (not real trade). Reference prices: illustrative (kashf/reference.py). Real-data results are in results/macro/.

Thresholds tuned on seed 0; mean ± sd over held-out seeds [1, 2, 3, 4, 5] (20,000 invoices each).

## Overall

| Configuration | Precision | Recall | F1 | False-alarm rate | Alerts / 1,000 | Avg. precision |
|---|---|---|---|---|---|---|
| kashf_full | 0.876 ± 0.012 | 0.759 ± 0.008 | 0.814 ± 0.009 | 0.45% ± 0.05 | 35.2 | 0.847 ± 0.005 |
| kashf_heuristic | 0.907 ± 0.016 | 0.642 ± 0.016 | 0.752 ± 0.012 | 0.28% ± 0.06 | 28.8 | 0.776 ± 0.010 |
| minus_price | 0.942 ± 0.008 | 0.557 ± 0.010 | 0.700 ± 0.008 | 0.14% ± 0.02 | 24.0 | 0.613 ± 0.008 |
| minus_route | 0.876 ± 0.012 | 0.759 ± 0.008 | 0.814 ± 0.009 | 0.45% ± 0.05 | 35.2 | 0.842 ± 0.005 |
| minus_documents | 0.842 ± 0.015 | 0.513 ± 0.007 | 0.638 ± 0.009 | 0.41% ± 0.04 | 24.8 | 0.574 ± 0.007 |
| minus_graph | 0.859 ± 0.016 | 0.500 ± 0.010 | 0.632 ± 0.011 | 0.35% ± 0.04 | 23.6 | 0.613 ± 0.010 |
| price_only | 0.574 ± 0.015 | 0.313 ± 0.009 | 0.405 ± 0.011 | 0.98% ± 0.04 | 22.1 | 0.311 ± 0.009 |
| checklist | 0.086 ± 0.006 | 0.633 ± 0.027 | 0.151 ± 0.009 | 28.51% ± 1.17 | 299.2 | 0.069 ± 0.005 |
| isolation_forest | 0.213 ± 0.015 | 0.221 ± 0.013 | 0.216 ± 0.012 | 3.47% ± 0.29 | 42.3 | 0.123 ± 0.006 |

## Recall by typology

| Configuration | over_invoicing | under_invoicing | phantom_shipment | multiple_invoicing | misdescription | circular_trading | shell_cluster |
|---|---|---|---|---|---|---|---|
| kashf_full | 0.43 | 0.28 | 0.67 | 1.00 | 1.00 | 1.00 | 1.00 |
| kashf_heuristic | 0.31 | 0.18 | 0.68 | 1.00 | 1.00 | 1.00 | 0.35 |
| minus_price | 0.00 | 0.00 | 0.67 | 1.00 | 0.33 | 1.00 | 1.00 |
| minus_route | 0.43 | 0.28 | 0.67 | 1.00 | 1.00 | 1.00 | 1.00 |
| minus_documents | 0.43 | 0.28 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 |
| minus_graph | 0.43 | 0.28 | 0.67 | 1.00 | 1.00 | 0.01 | 0.01 |
| price_only | 0.62 | 0.44 | 0.00 | 0.00 | 1.00 | 0.03 | 0.03 |
| checklist | 0.91 | 0.83 | 0.51 | 0.28 | 1.00 | 0.46 | 0.40 |
| isolation_forest | 0.12 | 0.07 | 0.62 | 0.03 | 0.61 | 0.03 | 0.02 |

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

Thresholds: kashf_full = 0.442, kashf_heuristic = 0.849, minus_price = 0.862, minus_route = 0.442, minus_documents = 0.565, minus_graph = 0.442, price_only = 0.236, checklist = 0.500, isolation_forest = 0.530
