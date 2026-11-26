# Kashf: pitch notes

Every number below is copied by `scripts/write_notes.py` from a results file. Each is labelled **real (UN Comtrade)** or **synthetic**.

## 5 bullets for judges

1. **Real data.** Kashf compares what the UAE and its partners each reported for the same trade: 19,007 UAE x partner x product x year mirror pairs (9,727 with both sides >= $100.0k), 156 partner countries, 43 HS6 products, years 2020, 2021, 2022, 2023. *real (UN Comtrade)*
2. **Real finding about UAE trade data.** UAE imports reconcile with partner reports (partners' exports ~ 1.01x after the 10% CIF/FOB margin), but for UAE exports partners record only ~0.24x of the value: re-exports are booked under the country of origin. Fixed thresholds set before seeing the data flagged 84% of pairs, so Kashf compares each flow with its own product's peers; that flags 9.3% of real pairs. *real (UN Comtrade)*
3. **Honest detection limits on real flows.** Known misinvoicing injected into real flows is found only when it is large: recall on not-already-flagged pairs is 0.05 at x2 and 0.41 at x10 (Isolation Forest 0.03 / 0.18). Country-level statistics are too noisy for moderate mispricing, which is why Kashf adds invoice-level evidence. *real flows + injected distortion*
4. **Invoice layer (synthetic invoices).** F1 0.81 with illustrative prices and 0.76 with real Comtrade reference prices; under generator shift F1 drops 0.82 -> 0.67. False-alarm rate 0.45% vs 17.9% for a manual checklist. *synthetic*
5. **Explainable, not accusatory.** Every flag shows its numbers and the innocent causes to rule out first (re-exports, free zones, CIF/FOB, estimated quantities, classification). To my knowledge no open tool combines real mirror statistics with invoice-level evidence this way; say "to my knowledge".

## Top flagged real flows (for the demo)

- **ITA -> UAE, HS 710813 Gold, semi-manufactured, 2023**: exporter's unit value $1.1k/kg is -22.8 robust SD from the global median $55.8k/kg for HS 710813 in 2023  
  Check first: UAE may record origin while the partner recorded a different destination (transshipment through a third country); freight/insurance far above 10% (CIF/FOB) or a shipment straddling the year end; different quantity units or a partial-shipment report; product mix inside one HS6 code (premium vs basic models) or a classification difference
- **UAE -> ZAF, HS 710231 Diamonds; non-industrial, unworked or si, 2021**: ZAF reports imports from UAE of $240.0k; UAE reports exports + re-exports of $556.5M (x1.10 CIF/FOB = $612.2M): importer side is 0.00x the expected value, while the typical ratio for this product and direction is 0.39x (-21.2 robust SD from peers); net weight differs 0.00x between the two reports (0 kg importer vs 256 kg exporter)  
  Check first: partner may attribute UAE re-exports to the original producing country; freight/insurance far above 10% (CIF/FOB) or a shipment straddling the year end; different quantity units or a partial-shipment report
- **UAE -> ZAF, HS 710231 Diamonds; non-industrial, unworked or si, 2022**: ZAF reports imports from UAE of $299.4k; UAE reports exports + re-exports of $656.6M (x1.10 CIF/FOB = $722.3M): importer side is 0.00x the expected value, while the typical ratio for this product and direction is 0.39x (-21.0 robust SD from peers); net weight differs 0.00x between the two reports (0 kg importer vs 168 kg exporter)  
  Check first: partner may attribute UAE re-exports to the original producing country; freight/insurance far above 10% (CIF/FOB) or a shipment straddling the year end; different quantity units or a partial-shipment report

## 3 honest limitations

1. **No ground-truth labels on real data, and weak detection of moderate mispricing there.** Real detection rates come from injected distortions (precision is a lower bound); below about x3 the mirror statistics cannot separate misinvoicing from normal reporting noise. The per-product baseline was chosen after seeing the real data (disclosed).
2. **Mirror gaps have many innocent causes.** Re-exports, free zones, origin attribution, CIF/FOB and timing all create gaps; the 10% CIF/FOB margin is an assumption.
3. **The invoice layer is still synthetic**, and its weights do not fully transfer: F1 0.82 -> 0.67 under generator shift. It needs analyst-labelled real cases.

## Likely questions

**"Is the gap just re-exports?"** Often, yes, and Kashf says so. It reports the re-export share of every UAE flow and lists re-exports first among the benign explanations when it is above 50%. A flag means "look here", not "laundering". The interesting flows are the ones where re-exports, CIF/FOB and timing cannot explain the size of the gap.

**"Is your data real?"** The macro layer: yes, UN Comtrade reports from the UAE and its partners (docs/DATA_CARD.md has the pull date and coverage). The invoice layer: no, synthetic, because real invoices with laundering labels are confidential. Its reference prices come from real Comtrade medians.

**"How do you avoid false accusations?"** Three ways: the macro layer works on country x product aggregates, never on named companies; every flag carries its evidence and the innocent explanations to check first; and Kashf never files reports. The analyst and the MLRO decide. False-alarm rates are reported next to every recall figure.

**"Why not deep learning?"** No labelled real data exists to train it, and analysts need evidence they can verify. An Isolation Forest is included as the ML comparison.
