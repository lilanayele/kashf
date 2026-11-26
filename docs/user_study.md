# User-study protocol: does the evidence panel help analysts?

Status: **protocol only. No participants have been run and no results exist.** The results table
at the end is empty and must stay empty until the study is actually carried out.

## Question

Do analysts decide on Kashf alerts faster and more accurately when they see the evidence panel
(signals, values, benchmark, calibrated weight, benign explanations) than when they see only the
risk score?

## Design

- **Participants:** 5 people with some compliance, audit or trade-finance background (students of
  finance/accounting acceptable for a pilot; record background).
- **Alerts:** 20 alerts drawn from a held-out synthetic seed (kashf.generate seed 6, not used for
  tuning or reporting): 14 true laundering, 6 false alarms, stratified across typologies. Each
  participant sees 10 alerts.
- **Conditions (within-subject):**
  - *Score only:* invoice row + risk score + the raw records (invoice, transport document,
    packing list, company table).
  - *Evidence panel:* the same, plus Kashf's evidence panel.
  Each participant does 5 alerts in each condition. Condition order and alert assignment are
  counterbalanced (Latin square) so every alert is seen in both conditions across participants.
- **Task per alert:** decide *escalate* or *close*, and write one sentence of justification.
- **Measures:**
  - time to decision (seconds, from opening the alert to submitting the decision);
  - accuracy (decision vs the generator's label);
  - justification quality: does the sentence name the planted mechanism? (scored blind by a second
    rater using kashf.evaluate.EXPECTED);
  - after the session: 5-point rating of trust and of "I could defend this decision to a supervisor".
- **Analysis:** per-participant paired differences (evidence minus score-only) for time and
  accuracy; report the mean, every participant's value, and a Wilcoxon signed-rank test. With 5
  participants this is a pilot: report effect sizes and raw data, not significance claims.

## Ethics and data

- Synthetic data only; no real company or person appears.
- Participation voluntary; no personal data beyond background category is recorded.
- Check whether the university requires ethics approval for a usability study before running it.

## Materials to prepare

1. `python -m kashf.generate --seed 6 --out data/study` and a script that samples the 20 alerts.
2. A dashboard build with a flag that hides the evidence panel (score-only condition).
3. A form or spreadsheet with one row per (participant, alert).

## Results template (fill in only after running the study)

| Participant | Background | Condition | Alert | Decision | Correct | Time (s) | Names mechanism |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

| Summary | Score only | Evidence panel | Difference |
|---|---|---|---|
| Accuracy (mean) | | | |
| Time to decision (median s) | | | |
| Justification names mechanism | | | |
