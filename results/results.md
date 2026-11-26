# Kashf invoice-layer results (SYNTHETIC invoices)

Data: synthetic invoices from kashf.generate (not real trade). Reference prices: illustrative (kashf/reference.py). Real-data results are in results/macro/.

Thresholds tuned on seed 0; mean ± sd over held-out seeds [1, 2, 3, 4, 5] (20,000 invoices each).

## Overall

| Configuration | Precision | Recall | F1 | False-alarm rate | Alerts / 1,000 | Avg. precision |
|---|---|---|---|---|---|---|
| kashf_full | 0.863 ± 0.009 | 0.682 ± 0.009 | 0.762 ± 0.009 | 0.66% ± 0.05 | 45.2 | 0.817 ± 0.009 |
| kashf_heuristic | 0.667 ± 0.008 | 0.661 ± 0.011 | 0.664 ± 0.008 | 2.00% ± 0.08 | 56.6 | 0.694 ± 0.010 |
| minus_price | 0.957 ± 0.003 | 0.516 ± 0.008 | 0.671 ± 0.007 | 0.14% ± 0.01 | 30.8 | 0.653 ± 0.006 |
| minus_route | 0.897 ± 0.012 | 0.611 ± 0.007 | 0.727 ± 0.007 | 0.42% ± 0.05 | 38.9 | 0.697 ± 0.005 |
| minus_documents | 0.842 ± 0.009 | 0.506 ± 0.008 | 0.632 ± 0.008 | 0.57% ± 0.04 | 34.3 | 0.625 ± 0.006 |
| minus_graph | 0.826 ± 0.013 | 0.430 ± 0.008 | 0.566 ± 0.010 | 0.55% ± 0.05 | 29.7 | 0.581 ± 0.009 |
| exact_entities | 0.851 ± 0.009 | 0.616 ± 0.006 | 0.714 ± 0.006 | 0.66% ± 0.05 | 41.4 | 0.754 ± 0.006 |
| price_only | 0.604 ± 0.011 | 0.231 ± 0.006 | 0.334 ± 0.007 | 0.92% ± 0.04 | 21.9 | 0.264 ± 0.006 |
| checklist | 0.100 ± 0.007 | 0.530 ± 0.018 | 0.169 ± 0.010 | 28.83% ± 1.68 | 302.1 | 0.080 ± 0.004 |
| iqr_price_filter | 0.074 ± 0.002 | 0.685 ± 0.018 | 0.134 ± 0.004 | 51.70% ± 0.57 | 526.5 | 0.307 ± 0.009 |
| isolation_forest | 0.170 ± 0.004 | 0.312 ± 0.016 | 0.220 ± 0.005 | 9.23% ± 0.51 | 104.9 | 0.145 ± 0.006 |

## Recall by typology

| Configuration | over_invoicing | under_invoicing | phantom_shipment | multiple_invoicing | misdescription | circular_trading | shell_cluster | transshipment_high_risk | u_turn | name_variant |
|---|---|---|---|---|---|---|---|---|---|---|
| kashf_full | 0.43 | 0.28 | 0.68 | 1.00 | 1.00 | 1.00 | 1.00 | 0.51 | 0.17 | 0.87 |
| kashf_heuristic | 0.52 | 0.34 | 0.73 | 1.00 | 1.00 | 1.00 | 1.00 | 0.11 | 0.29 | 0.71 |
| minus_price | 0.00 | 0.00 | 0.67 | 1.00 | 0.33 | 1.00 | 1.00 | 0.49 | 0.00 | 0.86 |
| minus_route | 0.43 | 0.28 | 0.67 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.03 | 0.87 |
| minus_documents | 0.43 | 0.28 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.51 | 0.17 | 0.87 |
| minus_graph | 0.43 | 0.28 | 0.68 | 1.00 | 1.00 | 0.01 | 0.01 | 0.51 | 0.17 | 0.01 |
| exact_entities | 0.43 | 0.28 | 0.68 | 1.00 | 1.00 | 1.00 | 1.00 | 0.51 | 0.17 | 0.03 |
| price_only | 0.62 | 0.44 | 0.00 | 0.00 | 1.00 | 0.03 | 0.03 | 0.00 | 0.06 | 0.03 |
| checklist | 0.91 | 0.83 | 0.51 | 0.28 | 1.00 | 0.46 | 0.40 | 0.26 | 0.36 | 0.18 |
| iqr_price_filter | 0.96 | 0.93 | 0.47 | 0.52 | 1.00 | 0.55 | 0.60 | 0.51 | 0.63 | 0.64 |
| isolation_forest | 0.29 | 0.20 | 0.69 | 0.07 | 0.77 | 0.12 | 0.10 | 0.67 | 0.08 | 0.02 |

## Evidence attribution (share of true alerts whose evidence names the planted mechanism)

- kashf_full: 0.999 ± 0.001
- kashf_heuristic: 0.999 ± 0.001
- minus_price: 1.000 ± 0.000
- minus_route: 0.999 ± 0.001
- minus_documents: 0.999 ± 0.001
- minus_graph: 0.999 ± 0.001

## Kashf recall vs. size of price distortion (over- and under-invoicing)

| Distortion vs benchmark | Invoices | Recall |
|---|---|---|
| 1-1.5x | 76 | 0.00 |
| 1.5-2x | 113 | 0.00 |
| 2-3x | 272 | 0.11 |
| 3-4x | 206 | 0.34 |
| 4-6x | 254 | 0.41 |
| 6-10x | 205 | 0.77 |
| >10x | 74 | 0.97 |

Thresholds: kashf_full = 0.334, kashf_heuristic = 0.750, minus_price = 0.872, minus_route = 0.471, minus_documents = 0.334, minus_graph = 0.334, exact_entities = 0.334, price_only = 0.260, checklist = 0.500, iqr_price_filter = 0.000, isolation_forest = 0.484
