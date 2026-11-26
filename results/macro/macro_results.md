# Macro layer results: REAL UN Comtrade mirror data

Label: **real (UN Comtrade)**. Annual HS data at total level (partner2 = World, all customs procedures, all transport modes), cached in data/raw/ by kashf.comtrade (pulled through the API, or saved API responses imported with `python -m kashf.comtrade import`). Comtrade-estimated quantities and weights and quantities in non-standard units are excluded. Coverage and caveats: docs/DATA_CARD.md.

- Mirror pairs: 19,007 (eligible, both sides >= $100.0k: 9,727)
- Years: 2020, 2021, 2022, 2023; partners: 156; HS6 codes: 43
- Median |log mirror gap|: 1.18 (sides typically differ by 3.25x after the CIF/FOB adjustment)
- Median mirror gap by direction: uae_export -1.41 (importer reports 0.24x the CIF-adjusted exporter value), uae_import +0.01 (importer reports 1.01x the CIF-adjusted exporter value)
- UAE exports, re-exports reported explicitly: re-exports (RX) are 34% of the UAE-reported export value in these pairs. Median gap against X + RX -1.41 (partner reports 0.24x); against domestic exports X only -0.89 (0.41x; 5,581 pairs with X > 0)
- Flag rate on real data: rules (relative baseline) 9.3%, Isolation Forest 5.0%; agreement 93.4%

**Fixed thresholds failed on real data.** The absolute thresholds set before seeing real data (|gap| > ln 1.5) flag 84% of real pairs, because UAE-export gaps are systematically negative: partners record most UAE re-exports under the country of origin. After seeing this, the rules compare each pair with the median of the same HS6 and direction (robust z). This change was made after looking at the real data and is disclosed here.

## Detection of injected misinvoicing (semi-synthetic: real flows + known distortion)

5% of eligible pairs have the importer-reported value pushed up or down by the stated size; mean over 5 repeats. Thresholds from configs/default.yaml, not tuned on the injected data. Precision is a lower bound: naturally anomalous real flows count as false positives. 'Recall on unflagged' counts only injected pairs the rules did not already flag before injection.

| Method | Distortion | Recall | Recall on unflagged | Precision (lower bound) | Flag rate | PR-AUC | PR-AUC (random) |
|---|---|---|---|---|---|---|---|
| iforest | +/-10% | 0.05 | 0.01 | 0.05 | 5.0% | 0.05 | 0.05 |
| rules | +/-10% | 0.10 | 0.00 | 0.05 | 9.3% | 0.05 | 0.05 |
| iforest | +/-25% | 0.06 | 0.01 | 0.06 | 5.0% | 0.05 | 0.05 |
| rules | +/-25% | 0.10 | 0.01 | 0.05 | 9.3% | 0.05 | 0.05 |
| iforest | +/-50% | 0.06 | 0.02 | 0.06 | 5.0% | 0.06 | 0.05 |
| rules | +/-50% | 0.10 | 0.01 | 0.06 | 9.3% | 0.06 | 0.05 |
| iforest | +/-100% | 0.07 | 0.03 | 0.07 | 5.0% | 0.06 | 0.05 |
| rules | +/-100% | 0.13 | 0.05 | 0.07 | 9.4% | 0.06 | 0.05 |
| iforest | x/÷3 | 0.10 | 0.05 | 0.09 | 5.0% | 0.08 | 0.05 |
| rules | x/÷3 | 0.20 | 0.13 | 0.11 | 9.6% | 0.08 | 0.05 |
| iforest | x/÷5 | 0.14 | 0.10 | 0.14 | 5.0% | 0.10 | 0.05 |
| rules | x/÷5 | 0.29 | 0.22 | 0.14 | 9.9% | 0.12 | 0.05 |
| iforest | x/÷10 | 0.21 | 0.18 | 0.21 | 5.0% | 0.15 | 0.05 |
| rules | x/÷10 | 0.45 | 0.41 | 0.21 | 10.6% | 0.20 | 0.05 |

## Case study: top 10 flagged UAE flows on the real data

Flags are reasons to look, not findings. Each row lists the benign explanations to rule out first.

**1. ITA -> UAE, HS 710813 Gold, semi-manufactured, 2023** (rule score 7.6; Isolation Forest not flagged)
- Why flagged: exporter's unit value $1.1k/kg is -22.8 robust SD from the global median $55.8k/kg for HS 710813 in 2023
- Isolation Forest: SHAP: uv_z_exp (+3.91), gap_rz (+0.20)
- Check first: UAE may record origin while the partner recorded a different destination (transshipment through a third country); freight/insurance far above 10% (CIF/FOB) or a shipment straddling the year end; different quantity units or a partial-shipment report; product mix inside one HS6 code (premium vs basic models) or a classification difference

**2. UAE -> ZAF, HS 710231 Diamonds; non-industrial, unworked or si, 2021** (rule score 7.1; Isolation Forest flagged)
- Why flagged: ZAF reports imports from UAE of $240.0k; UAE reports exports + re-exports of $556.5M (x1.10 CIF/FOB = $612.2M): importer side is 0.00x the expected value, while the typical ratio for this product and direction is 0.39x (-21.2 robust SD from peers); net weight differs 0.00x between the two reports (0 kg importer vs 256 kg exporter)
- Isolation Forest: SHAP: gap_rz (+3.18), wgap_rz (+2.75)
- Check first: partner may attribute UAE re-exports to the original producing country; freight/insurance far above 10% (CIF/FOB) or a shipment straddling the year end; different quantity units or a partial-shipment report

**3. UAE -> ZAF, HS 710231 Diamonds; non-industrial, unworked or si, 2022** (rule score 7.0; Isolation Forest flagged)
- Why flagged: ZAF reports imports from UAE of $299.4k; UAE reports exports + re-exports of $656.6M (x1.10 CIF/FOB = $722.3M): importer side is 0.00x the expected value, while the typical ratio for this product and direction is 0.39x (-21.0 robust SD from peers); net weight differs 0.00x between the two reports (0 kg importer vs 168 kg exporter)
- Isolation Forest: SHAP: gap_rz (+3.23), wgap_rz (+2.77)
- Check first: partner may attribute UAE re-exports to the original producing country; freight/insurance far above 10% (CIF/FOB) or a shipment straddling the year end; different quantity units or a partial-shipment report

**4. UAE -> ZAF, HS 710231 Diamonds; non-industrial, unworked or si, 2023** (rule score 6.9; Isolation Forest flagged)
- Why flagged: ZAF reports imports from UAE of $288.9k; UAE reports exports + re-exports of $572.8M (x1.10 CIF/FOB = $630.1M): importer side is 0.00x the expected value, while the typical ratio for this product and direction is 0.39x (-20.7 robust SD from peers); net weight differs 0.00x between the two reports (0 kg importer vs 73 kg exporter)
- Isolation Forest: SHAP: gap_rz (+3.36), wgap_rz (+2.81)
- Check first: partner may attribute UAE re-exports to the original producing country; freight/insurance far above 10% (CIF/FOB) or a shipment straddling the year end; different quantity units or a partial-shipment report

**5. UAE -> OMN, HS 710813 Gold, semi-manufactured, 2023** (rule score 6.6; Isolation Forest flagged)
- Why flagged: exporter's unit value $1.9k/kg is -19.8 robust SD from the global median $55.8k/kg for HS 710813 in 2023
- Isolation Forest: SHAP: uv_z_exp (+3.67), uv_z_imp (+0.86)
- Check first: goods shipped via UAE free zones may leave outside UAE customs statistics while the partner records the UAE as consignor; freight/insurance far above 10% (CIF/FOB) or a shipment straddling the year end; different quantity units or a partial-shipment report; product mix inside one HS6 code (premium vs basic models) or a classification difference

**6. UAE -> THA, HS 710231 Diamonds; non-industrial, unworked or si, 2021** (rule score 6.4; Isolation Forest not flagged)
- Why flagged: net weight differs 2141.36x between the two reports (47,110 kg importer vs 22 kg exporter)
- Isolation Forest: SHAP: wgap_rz (+3.43), uv_z_imp (+0.08)
- Check first: partner may attribute UAE re-exports to the original producing country; freight/insurance far above 10% (CIF/FOB) or a shipment straddling the year end; different quantity units or a partial-shipment report

**7. FRA -> UAE, HS 710813 Gold, semi-manufactured, 2022** (rule score 6.4; Isolation Forest flagged)
- Why flagged: importer's unit value $155/kg is -19.2 robust SD from the global median $47.0k/kg for HS 710813 in 2022
- Isolation Forest: SHAP: uv_z_imp (+3.00), uv_z_exp_missing (+1.01)
- Check first: UAE may record origin while the partner recorded a different destination (transshipment through a third country); product mix inside one HS6 code (premium vs basic models) or a classification difference

**8. IND -> UAE, HS 721420 Steel bars, 2022** (rule score 6.2; Isolation Forest flagged)
- Why flagged: UAE reports imports from IND of $652.3k; IND reports exports to UAE of $271.6k (x1.10 CIF/FOB = $298.8k): importer side is 2.18x the expected value, while the typical ratio for this product and direction is 0.95x (+3.9 robust SD from peers); net weight differs 3.94x between the two reports (1,078,460 kg importer vs 273,564 kg exporter)
- Isolation Forest: SHAP: wgap_rz (+2.88), gap_rz (+2.06)
- Check first: UAE may record origin while the partner recorded a different destination (transshipment through a third country); freight/insurance far above 10% (CIF/FOB) or a shipment straddling the year end; different quantity units or a partial-shipment report

**9. UAE -> THA, HS 710231 Diamonds; non-industrial, unworked or si, 2020** (rule score 5.9; Isolation Forest not flagged)
- Why flagged: net weight differs 1083.42x between the two reports (25,677 kg importer vs 24 kg exporter)
- Isolation Forest: SHAP: wgap_rz (+3.48), uv_z_imp (-0.08)
- Check first: partner may attribute UAE re-exports to the original producing country; freight/insurance far above 10% (CIF/FOB) or a shipment straddling the year end; different quantity units or a partial-shipment report

**10. BEN -> UAE, HS 710812 Metals; gold, non-monetary, unwrought (b, 2020** (rule score 5.9; Isolation Forest flagged)
- Why flagged: UAE reports imports from BEN of $542.6M; BEN reports exports to UAE of $176.4k (x1.10 CIF/FOB = $194.0k): importer side is 2797.11x the expected value, while the typical ratio for this product and direction is 2.13x (+5.8 robust SD from peers); exporter's unit value $1.7k/kg is -17.6 robust SD from the global median $49.3k/kg for HS 710812 in 2020
- Isolation Forest: SHAP: uv_z_exp (+3.04), gap_rz (+2.53)
- Check first: UAE may record origin while the partner recorded a different destination (transshipment through a third country); freight/insurance far above 10% (CIF/FOB) or a shipment straddling the year end; different quantity units or a partial-shipment report; product mix inside one HS6 code (premium vs basic models) or a classification difference

