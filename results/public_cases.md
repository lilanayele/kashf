# Scenarios reconstructed from public FATF/Egmont case boxes

Label: **reconstructed from public reports**. Each folder in tests/cases/ follows the mechanism of one box in FATF and Egmont Group (2020), *Trade-Based Money Laundering: Trends and Developments*; names, dates, quantities and prices are invented. Scored with the shipped calibration and alert threshold.

Schemes visible in trade records: evidence surfaced in 4/4; at least one alert in 1/4. Payment-side schemes (blind spots by design): 2, none alerted.

| Box | Country | Expected | Rules fired | Alerts | Max score |
|---|---|---|---|---|---|
| 2.11 (p. 32) | New Zealand | evidence | high_risk_party | 0/3 | 0.06 |
| 2.13 (p. 34) | Italy | evidence | high_risk_party, no_transport_doc | 0/3 | 0.33 |
| 2.6 (p. 22) | Spain, Italy (Europol) | evidence | circular_trade, over_priced | 8/8 | 0.98 |
| 2.8 (p. 24) | Australia | evidence | under_priced | 0/4 | 0.26 |
| 2.9 (p. 28) | United States | blind spot | - | 0/3 | 0.00 |
| 4.7 (p. 52) | Germany | blind spot | - | 0/4 | 0.00 |

Evidence without an alert means the rule fired but its calibrated weight (fitted on the synthetic generator) kept the score below the threshold: for example a 5x under-priced phone is only about 3.6 robust SD below the illustrative reference because phone prices vary widely.
