# External validation against published reports (REAL UN Comtrade data)

**Not ground truth for laundering.** The documented flows come from NGO reports on gold smuggling and transit (SWISSAID 2024, 2025; see data/external_validation.csv for every source and page). They are a small, gold-only, Africa-only set chosen by investigators, not a sample of laundering.

- Eligible mirror pairs: 9,727; documented (partner, year) keys: 24; present as eligible pairs: 10 (10 pairs over HS 710812/710813).
- Keys absent from the data (partner did not report, or a side below the value filter): BEN 2022, ERI 2022, ETH 2022, GHA 2020, GHA 2023, LBY 2022, NER 2020, NER 2021, NER 2022, SDN 2023, SSD 2022, TCD 2022, TGO 2022, UGA 2022.
- Random precision: 0.0010 over all pairs, 0.042 within HS 7108 UAE-import pairs (236 pairs).

| Method | Keys flagged (by kind) | Median best rank (all) | Median best rank (gold imports) | P@10 all | P@25 all | P@10 gold | P@25 gold |
|---|---|---|---|---|---|---|---|
| kashf_rules | 4/10 (mirror 4/4, transit 0/6) | 4962 | 114 | 0.00 | 0.00 | 0.00 | 0.04 |
| isolation_forest | 4/10 (mirror 4/4, transit 0/6) | 5000 | 86 | 0.00 | 0.04 | 0.10 | 0.16 |
| gfi_gap | 6/10 (mirror 4/4, transit 2/6) | 361 | 46 | 0.20 | 0.12 | 0.30 | 0.20 |
| iqr_filter | 0/10 (mirror 0/4, transit 0/6) | 4572 | 68 | 0.00 | 0.00 | 0.00 | 0.04 |

GFI gap and IQR filter flag the same number of pairs as the Kashf rules (top k), so flag counts are comparable.

## Per documented key (Kashf rules)

| Source id | Partner | Year | Kind | Best rank (all) | Best rank (gold) | Flagged |
|---|---|---|---|---|---|---|
| GOLD-GHA-2020-23 | GHA | 2021 | mirror_discrepancy | 628 | 43 | yes |
| GOLD-GHA-2022 | GHA | 2022 | mirror_discrepancy | 252 | 26 | yes |
| GOLD-HUBS-2023 | RWA | 2023 | transit_hub | 7239 | 153 | no |
| GOLD-HUBS-2023 | UGA | 2023 | transit_hub | 2684 | 74 | no |
| GOLD-MLI-2021 | MLI | 2021 | mirror_discrepancy | 185 | 17 | yes |
| GOLD-MLI-2022 | MLI | 2022 | mirror_discrepancy | 409 | 36 | yes |
| GOLD-TRANSIT-2022 | BDI | 2022 | transit_hub | 7812 | 176 | no |
| GOLD-TRANSIT-2022 | CAF | 2022 | transit_hub | 9626 | 236 | no |
| GOLD-TRANSIT-2022 | EGY | 2022 | transit_hub | 7961 | 182 | no |
| GOLD-TRANSIT-2022 | RWA | 2022 | transit_hub | 7353 | 156 | no |
