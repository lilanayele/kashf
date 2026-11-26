# Data card: UN Comtrade data used by Kashf

| Field | Value |
|---|---|
| Source | UN Comtrade API v1 (`data/v1/get/C/A/HS`), final annual data, HS classification |
| Retrieval | API responses saved on the user's machine and imported with `python -m kashf.comtrade import` (same parameters and post-processing as `pull`) |
| Excluded values | quantities in a non-standard unit for the HS6, and Comtrade-estimated quantities and net weights (`isQtyEstimated`, `isNetWgtEstimated`) |
| Pull date(s) (UTC) | 2026-11-26 |
| API calls logged | 16 successful, 0 failed (data/raw/calls.jsonl) |
| Years requested | 2020, 2021, 2022, 2023, 2024 |
| HS6 codes | 20 base (kashf/reference.py) + 23 top UAE re-export codes |
| Filters | partner2 = World, customs procedure = C00 (all), mode of transport = 0 (all) |
| Rows cached | 102,930 |

## Coverage by query family and year

| Source | Year | Rows | Reporters | Partners | HS6 | Missing qty | Missing net weight | Estimated weight |
|---|---|---|---|---|---|---|---|---|
| mirror | 2020 | 5,027 | 164 | 1 | 39 | 37% | 24% | 22% |
| mirror | 2021 | 5,340 | 166 | 1 | 42 | 36% | 22% | 21% |
| mirror | 2022 | 5,852 | 164 | 1 | 43 | 37% | 24% | 20% |
| mirror | 2023 | 6,052 | 163 | 1 | 43 | 39% | 26% | 22% |
| mirror | 2024 | 5,741 | 147 | 1 | 43 | 37% | 24% | 20% |
| uae | 2020 | 10,726 | 1 | 218 | 39 | 50% | 0% | 0% |
| uae | 2021 | 11,566 | 1 | 222 | 39 | 50% | 2% | 2% |
| uae | 2022 | 13,181 | 1 | 225 | 43 | 50% | 2% | 2% |
| uae | 2023 | 13,005 | 1 | 225 | 43 | 49% | 1% | 0% |
| world | 2020 | 5,058 | 169 | 1 | 39 | 45% | 34% | 30% |
| world | 2021 | 5,146 | 170 | 1 | 42 | 45% | 35% | 31% |
| world | 2022 | 5,530 | 168 | 1 | 43 | 46% | 34% | 28% |
| world | 2023 | 5,573 | 166 | 1 | 43 | 46% | 36% | 29% |
| world | 2024 | 5,133 | 149 | 1 | 43 | 46% | 36% | 28% |

## UAE reporting

- UAE-reported flows (X/RX/M/RM) found for: 2020, 2021, 2022, 2023
- Years with no UAE report (mirror pairs impossible): 2024
- Re-exports in UAE-reported exports: 29% of X + RX value

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

