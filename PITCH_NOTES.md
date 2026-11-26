# Kashf: pitch notes

Every number below is copied by `scripts/write_notes.py` from a results file. Each is labelled **real (UN Comtrade)** or **synthetic**.

## 5 bullets for judges

1. **Real data.** Mirror pairs from UAE and partner reports to UN Comtrade. *pending: run scripts/run_real.sh*
2. **Novel combination.** To my knowledge, no open tool combines country-level mirror statistics on real trade data with invoice-level evidence checks for one trader, with a benign explanation attached to every flag. (Say "to my knowledge", not "first".)
3. **Measured detection on real flows.** Known misinvoicing injected into real flows: rules recall pending at ±25% and pending at ±100%; Isolation Forest pending / pending. PR-AUC at ±50%: rules pending, IF pending (random = pending). *real flows + injected distortion*
4. **Invoice layer (synthetic) with an honest stress test.** F1 0.81 and false-alarm rate 0.45% on the benchmark; on test data from a shifted generator F1 drops 0.82 -> 0.67 and false alarms rise to 1.51%. *synthetic*
5. **Explainable, not accusatory.** Every alert shows the numbers behind it and the benign causes to rule out first (re-exports, free zones, CIF/FOB, timing, classification). Kashf ranks what to look at; a human decides.

## Top flagged real flows (for the demo)

*pending: run scripts/run_real.sh*

## 3 honest limitations

1. **No ground-truth labels on real data.** Real detection rates come from injected distortions; precision counts every natural anomaly as a false alarm, so it is a lower bound.
2. **Mirror gaps have many innocent causes.** Re-exports, free zones, origin attribution, CIF/FOB and timing all create gaps; the 10% CIF/FOB margin is an assumption.
3. **The invoice layer is still synthetic**, and its weights do not fully transfer: F1 0.82 -> 0.67 under generator shift. It needs analyst-labelled real cases.

## Likely questions

**"Is the gap just re-exports?"** Often, yes, and Kashf says so. It reports the re-export share of every UAE flow and lists re-exports first among the benign explanations when it is above 50%. A flag means "look here", not "laundering". The interesting flows are the ones where re-exports, CIF/FOB and timing cannot explain the size of the gap.

**"Is your data real?"** The macro layer: yes, UN Comtrade reports from the UAE and its partners (docs/DATA_CARD.md has the pull date and coverage). The invoice layer: no, synthetic, because real invoices with laundering labels are confidential. Its reference prices come from real Comtrade medians.

**"How do you avoid false accusations?"** Three ways: the macro layer works on country x product aggregates, never on named companies; every flag carries its evidence and the innocent explanations to check first; and Kashf never files reports. The analyst and the MLRO decide. False-alarm rates are reported next to every recall figure.

**"Why not deep learning?"** No labelled real data exists to train it, and analysts need evidence they can verify. An Isolation Forest is included as the ML comparison.
