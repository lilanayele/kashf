# Data card: UN Comtrade data used by Kashf

**Status: not yet pulled.** This file is regenerated from the cached data by
`python -m kashf.comtrade card` (step 4 of `scripts/run_real.sh`), with the pull date, the number of
API calls, and coverage per query family and year (rows, reporters, partners, HS6 codes, share of
missing quantities and weights, share of Comtrade-estimated weights).

| Field | Value |
|---|---|
| Source | UN Comtrade, final annual data, HS classification, via the `comtradeapicall` package |
| Queries | UAE (784) X/RX/M/RM by partner; all partners' M/X with the UAE; all reporters' X to World |
| Years | 2020-2024 (configs/default.yaml) |
| HS6 codes | the 20 in kashf/reference.py, plus the top 30 UAE re-export codes |
| Filters | partner2 = World, customs procedure = C00, mode of transport = all |

## Caveats (read before interpreting any mirror gap)

- **CIF vs FOB.** Importers usually value goods CIF (with freight and insurance), exporters FOB. Kashf
  assumes a flat 10% CIF/FOB margin (`macro.cif_fob_factor`). Real margins vary by product, route and
  year, so gaps within roughly +/-20-30% are not meaningful on their own.
- **Re-exports vs domestic exports.** The UAE reports re-exports (RX) separately. Partners often record
  goods by country of ORIGIN, not the UAE as consignor, so UAE re-exports can be missing from or
  attributed elsewhere in partner imports. Kashf sums X + RX on the UAE side and reports the re-export
  share for every pair.
- **Free zones.** Goods moving through UAE free zones may sit outside the UAE customs territory and be
  recorded differently (or not at all) in UAE statistics, while partners record the UAE.
- **Timing lags.** A shipment that leaves in December may arrive in January; annual totals then differ.
- **Confidential or suppressed codes.** Some reporters suppress HS6 detail for confidentiality; those
  values appear only in higher-level aggregates and look like missing trade at HS6.
- **Estimated quantities.** Comtrade estimates missing quantities and weights (`isQtyEstimated`,
  `isNetWgtEstimated`). Estimated weights make weight gaps and unit values less reliable; Kashf carries
  the flag into every pair.
- **Classification.** Partners may classify the same goods under different HS6 codes, or use a different
  HS edition; Comtrade converts between editions, which can add noise.
- **Reporting coverage.** The UAE and some partners report with a lag; the latest year may be incomplete.
- **What a flag means.** A flagged pair is a country x product x year aggregate that merits a closer look.
  It is not evidence that any company or person laundered money.
