# Kashf invoice-layer results (SYNTHETIC invoices)

Data: synthetic invoices from kashf.generate (not real trade). Reference prices: data/reference_comtrade.csv. Real-data results are in results/macro/.

Thresholds tuned on seed 0; mean ± sd over held-out seeds [1, 2, 3, 4, 5] (20,000 invoices each).

## Overall

| Configuration | Precision | Recall | F1 | False-alarm rate | Alerts / 1,000 | Avg. precision |
|---|---|---|---|---|---|---|
| kashf_full | 0.865 ± 0.014 | 0.671 ± 0.005 | 0.756 ± 0.006 | 0.45% ± 0.06 | 31.6 | 0.749 ± 0.009 |
| kashf_heuristic | 0.823 ± 0.018 | 0.662 ± 0.007 | 0.734 ± 0.005 | 0.60% ± 0.08 | 32.7 | 0.739 ± 0.007 |
| minus_price | 0.934 ± 0.006 | 0.560 ± 0.011 | 0.701 ± 0.010 | 0.17% ± 0.02 | 24.4 | 0.612 ± 0.009 |
| minus_route | 0.868 ± 0.016 | 0.670 ± 0.005 | 0.756 ± 0.006 | 0.43% ± 0.06 | 31.4 | 0.747 ± 0.009 |
| minus_documents | 0.764 ± 0.018 | 0.425 ± 0.009 | 0.546 ± 0.011 | 0.56% ± 0.05 | 22.6 | 0.458 ± 0.009 |
| minus_graph | 0.775 ± 0.021 | 0.430 ± 0.008 | 0.553 ± 0.011 | 0.53% ± 0.06 | 22.6 | 0.506 ± 0.014 |
| price_only | 0.605 ± 0.031 | 0.164 ± 0.008 | 0.257 ± 0.013 | 0.45% ± 0.04 | 11.0 | 0.193 ± 0.011 |
| checklist | 0.061 ± 0.002 | 0.655 ± 0.021 | 0.112 ± 0.003 | 42.39% ± 0.57 | 433.3 | 0.054 ± 0.001 |
| isolation_forest | 0.157 ± 0.011 | 0.217 ± 0.015 | 0.182 ± 0.011 | 4.94% ± 0.42 | 56.2 | 0.092 ± 0.007 |

## Recall by typology

| Configuration | over_invoicing | under_invoicing | phantom_shipment | multiple_invoicing | misdescription | circular_trading | shell_cluster |
|---|---|---|---|---|---|---|---|
| kashf_full | 0.25 | 0.07 | 0.67 | 1.00 | 0.78 | 1.00 | 1.00 |
| kashf_heuristic | 0.20 | 0.12 | 0.70 | 1.00 | 0.68 | 1.00 | 1.00 |
| minus_price | 0.00 | 0.00 | 0.69 | 1.00 | 0.33 | 1.00 | 1.00 |
| minus_route | 0.25 | 0.06 | 0.67 | 1.00 | 0.78 | 1.00 | 1.00 |
| minus_documents | 0.25 | 0.17 | 0.00 | 0.00 | 0.67 | 1.00 | 1.00 |
| minus_graph | 0.25 | 0.17 | 0.70 | 1.00 | 0.78 | 0.00 | 0.01 |
| price_only | 0.25 | 0.17 | 0.00 | 0.00 | 0.67 | 0.00 | 0.01 |
| checklist | 0.82 | 0.75 | 0.60 | 0.45 | 0.96 | 0.48 | 0.49 |
| isolation_forest | 0.07 | 0.06 | 0.64 | 0.03 | 0.50 | 0.09 | 0.09 |

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
| 1-1.5x | 142 | 0.00 |
| 1.5-2x | 136 | 0.00 |
| 2-3x | 212 | 0.01 |
| 3-4x | 153 | 0.12 |
| 4-6x | 193 | 0.17 |
| 6-10x | 165 | 0.41 |
| >10x | 199 | 0.35 |

Thresholds: kashf_full = 0.375, kashf_heuristic = 0.700, minus_price = 0.313, minus_route = 0.501, minus_documents = 0.327, minus_graph = 0.303, price_only = 0.327, checklist = 0.500, isolation_forest = 0.524
