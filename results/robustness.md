# Robustness of the invoice layer (SYNTHETIC invoices)

Synthetic invoices from kashf.generate; reference prices: illustrative (kashf/reference.py). Tuned on seed 0, tested on seeds [1, 2, 3] (20,000 invoices each); mean ± sd. Each sweep changes one setting and re-runs calibration and threshold tuning on seed 0.

## 1. Sensitivity to hand-set thresholds

### price_z

| Value | Precision | Recall | F1 | False-alarm rate |
|---|---|---|---|---|
| 1.5 | 0.879 ± 0.004 | 0.761 ± 0.007 | 0.816 ± 0.006 | 0.44% ± 0.02 |
| 2.0 | 0.879 ± 0.004 | 0.761 ± 0.007 | 0.816 ± 0.006 | 0.44% ± 0.02 |
| 2.5 | 0.878 ± 0.004 | 0.761 ± 0.007 | 0.815 ± 0.006 | 0.45% ± 0.02 |
| 3.0 | 0.879 ± 0.004 | 0.761 ± 0.007 | 0.816 ± 0.006 | 0.44% ± 0.02 |

### qty_tolerance

| Value | Precision | Recall | F1 | False-alarm rate |
|---|---|---|---|---|
| 0.01 | 0.879 ± 0.004 | 0.761 ± 0.007 | 0.816 ± 0.006 | 0.44% ± 0.02 |
| 0.03 | 0.879 ± 0.004 | 0.761 ± 0.007 | 0.816 ± 0.006 | 0.44% ± 0.02 |
| 0.05 | 0.879 ± 0.004 | 0.761 ± 0.007 | 0.816 ± 0.006 | 0.44% ± 0.02 |
| 0.1 | 0.879 ± 0.004 | 0.761 ± 0.007 | 0.816 ± 0.006 | 0.44% ± 0.02 |

### weight_tolerance

| Value | Precision | Recall | F1 | False-alarm rate |
|---|---|---|---|---|
| 0.1 | 0.835 ± 0.007 | 0.761 ± 0.007 | 0.796 ± 0.007 | 0.64% ± 0.03 |
| 0.15 | 0.879 ± 0.004 | 0.761 ± 0.007 | 0.816 ± 0.006 | 0.44% ± 0.02 |
| 0.25 | 0.887 ± 0.002 | 0.761 ± 0.007 | 0.819 ± 0.005 | 0.41% ± 0.01 |
| 0.4 | 0.887 ± 0.002 | 0.761 ± 0.007 | 0.819 ± 0.005 | 0.41% ± 0.01 |

## 2. Alert threshold (calibration fixed)

| Threshold | Precision | Recall | F1 | False-alarm rate |
|---|---|---|---|---|
| 0.2 | 0.695 ± 0.005 | 0.863 ± 0.010 | 0.770 ± 0.007 | 1.60% ± 0.03 |
| 0.3 | 0.844 ± 0.011 | 0.776 ± 0.012 | 0.808 ± 0.010 | 0.61% ± 0.05 |
| 0.4 | 0.879 ± 0.004 | 0.761 ± 0.007 | 0.816 ± 0.006 | 0.44% ± 0.02 |
| 0.44 | 0.879 ± 0.004 | 0.761 ± 0.007 | 0.816 ± 0.006 | 0.44% ± 0.02 |
| 0.5 | 0.881 ± 0.003 | 0.761 ± 0.007 | 0.816 ± 0.006 | 0.44% ± 0.01 |
| 0.6 | 0.910 ± 0.005 | 0.720 ± 0.008 | 0.804 ± 0.006 | 0.30% ± 0.02 |
| 0.7 | 0.927 ± 0.008 | 0.678 ± 0.003 | 0.783 ± 0.005 | 0.23% ± 0.03 |
| 0.8 | 0.935 ± 0.006 | 0.672 ± 0.002 | 0.782 ± 0.003 | 0.20% ± 0.02 |

## 3. Generator shift

Tuned on the default generator; tested on seeds from the same generator vs a shifted one (price_noise_scale=1.3, premium_rate=0.06, clearance_rate=0.04, premium_range=[1.4, 3.5], over_range=[1.3, 4.0], under_range=[0.25, 0.75], typology_rate=0.004).

| Test data | Precision | Recall | F1 | False-alarm rate | Avg. precision |
|---|---|---|---|---|---|
| same generator | 0.879 ± 0.004 | 0.761 ± 0.007 | 0.816 ± 0.006 | 0.44% ± 0.02 | 0.849 ± 0.003 |
| shifted generator | 0.611 ± 0.011 | 0.738 ± 0.009 | 0.668 ± 0.008 | 1.51% ± 0.05 | 0.740 ± 0.015 |
