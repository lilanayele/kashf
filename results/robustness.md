# Robustness of the invoice layer (SYNTHETIC invoices)

Synthetic invoices from kashf.generate; reference prices: illustrative (kashf/reference.py). Tuned on seed 0, tested on seeds [1, 2, 3] (20,000 invoices each); mean ± sd. Each sweep changes one setting and re-runs calibration and threshold tuning on seed 0.

## 1. Sensitivity to hand-set thresholds

### price_z

| Value | Precision | Recall | F1 | False-alarm rate |
|---|---|---|---|---|
| 1.5 | 0.898 ± 0.012 | 0.671 ± 0.010 | 0.768 ± 0.010 | 0.46% ± 0.06 |
| 2.0 | 0.863 ± 0.011 | 0.686 ± 0.008 | 0.764 ± 0.009 | 0.66% ± 0.06 |
| 2.5 | 0.900 ± 0.012 | 0.670 ± 0.010 | 0.768 ± 0.010 | 0.45% ± 0.06 |
| 3.0 | 0.900 ± 0.012 | 0.670 ± 0.010 | 0.768 ± 0.010 | 0.45% ± 0.06 |

### qty_tolerance

| Value | Precision | Recall | F1 | False-alarm rate |
|---|---|---|---|---|
| 0.01 | 0.863 ± 0.011 | 0.686 ± 0.008 | 0.764 ± 0.009 | 0.66% ± 0.06 |
| 0.03 | 0.863 ± 0.011 | 0.686 ± 0.008 | 0.764 ± 0.009 | 0.66% ± 0.06 |
| 0.05 | 0.863 ± 0.011 | 0.686 ± 0.008 | 0.764 ± 0.009 | 0.66% ± 0.06 |
| 0.1 | 0.863 ± 0.011 | 0.686 ± 0.008 | 0.764 ± 0.009 | 0.66% ± 0.06 |

### weight_tolerance

| Value | Precision | Recall | F1 | False-alarm rate |
|---|---|---|---|---|
| 0.1 | 0.822 ± 0.013 | 0.686 ± 0.008 | 0.748 ± 0.010 | 0.90% ± 0.08 |
| 0.15 | 0.863 ± 0.011 | 0.686 ± 0.008 | 0.764 ± 0.009 | 0.66% ± 0.06 |
| 0.25 | 0.867 ± 0.011 | 0.686 ± 0.008 | 0.766 ± 0.009 | 0.64% ± 0.06 |
| 0.4 | 0.867 ± 0.011 | 0.686 ± 0.008 | 0.766 ± 0.009 | 0.64% ± 0.06 |

## 2. Alert threshold (calibration fixed)

| Threshold | Precision | Recall | F1 | False-alarm rate |
|---|---|---|---|---|
| 0.2 | 0.549 ± 0.000 | 0.852 ± 0.015 | 0.668 ± 0.005 | 4.23% ± 0.02 |
| 0.3 | 0.786 ± 0.008 | 0.708 ± 0.012 | 0.745 ± 0.010 | 1.16% ± 0.05 |
| 0.4 | 0.892 ± 0.011 | 0.671 ± 0.011 | 0.766 ± 0.010 | 0.49% ± 0.05 |
| 0.44 | 0.896 ± 0.012 | 0.671 ± 0.010 | 0.767 ± 0.010 | 0.47% ± 0.06 |
| 0.5 | 0.904 ± 0.011 | 0.657 ± 0.007 | 0.761 ± 0.008 | 0.42% ± 0.05 |
| 0.6 | 0.930 ± 0.005 | 0.631 ± 0.006 | 0.752 ± 0.005 | 0.29% ± 0.03 |
| 0.7 | 0.936 ± 0.004 | 0.625 ± 0.005 | 0.750 ± 0.004 | 0.26% ± 0.02 |
| 0.8 | 0.950 ± 0.002 | 0.603 ± 0.006 | 0.738 ± 0.005 | 0.19% ± 0.01 |

## 3. Generator shift

Tuned on the default generator; tested on seeds from the same generator vs a shifted one (price_noise_scale=1.3, premium_rate=0.06, clearance_rate=0.04, premium_range=[1.4, 3.5], over_range=[1.3, 4.0], under_range=[0.25, 0.75], typology_rate=0.004).

Alternative typology mechanics: ring_size=[4, 8], ring_hop_days=[10, 45], ring_price_drift=[0.95, 1.25], ring_qty_jitter=0.08, shell_links=[0.35, 0.25, 0.15], phantom_weight_range=[0.4, 0.75], multiple_split=True, over_range=[1.4, 3.0], under_range=[0.35, 0.7].

| Test data | Precision | Recall | F1 | False-alarm rate | Avg. precision |
|---|---|---|---|---|---|
| same generator | 0.863 ± 0.011 | 0.686 ± 0.008 | 0.764 ± 0.009 | 0.66% ± 0.06 | 0.818 ± 0.009 |
| shifted generator | 0.609 ± 0.010 | 0.690 ± 0.006 | 0.647 ± 0.003 | 2.02% ± 0.08 | 0.721 ± 0.004 |
| alt typologies | 0.856 ± 0.009 | 0.621 ± 0.019 | 0.720 ± 0.015 | 0.68% ± 0.04 | 0.752 ± 0.014 |
