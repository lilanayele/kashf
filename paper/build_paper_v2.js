// Builds paper/Kashf_Paper_v2.docx (IEEE-style two-column) from results files only.
//   node paper/build_paper_v2.js && soffice --headless --convert-to pdf --outdir paper paper/Kashf_Paper_v2.docx
// Every number goes through V(), which records the value and the file/key it came from in paper/NUMBERS.md.
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, AlignmentType, HeadingLevel,
  WidthType, BorderStyle, LevelFormat, SectionType, Footer, PageNumber,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const J = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8"));
const SYN = J("results/summary.json");
const RR = J("results/real_reference/summary.json");
const ROB = J("results/robustness.json");
const MAC = J("results/macro/macro_summary.json");
const CARD = fs.readFileSync(path.join(ROOT, "docs/DATA_CARD.md"), "utf8");
const FATF = fs.readFileSync(path.join(ROOT, "configs/fatf_lists.yaml"), "utf8");
const DER = J("paper/figures/derived_stats.json");
const REFT = Object.fromEntries(execSync(`${path.join(ROOT, ".venv/bin/python")} -c "from kashf.reference import default_table as d; print(d()[['hs6','log_mad']].to_csv(index=False))"`, { cwd: ROOT }).toString().trim().split("\n").slice(1).map((l) => { const [h, m] = l.split(","); return [h, +m]; }));
const EXP = J("results/explainability.json");
const EXT = J("results/external_validation.json"), AML = J("results/amlworld.json"), CASES = J("results/public_cases.json");
const S_EXT = "results/external_validation.json", S_AML = "results/amlworld.json", S_CASES = "results/public_cases.json",
  S_INJ = "results/macro/injection_summary.csv";
const INJ = (() => { const [h, ...rows] = fs.readFileSync(path.join(ROOT, S_INJ), "utf8").trim().split("\n").map((l) => l.split(","));
  return rows.map((r) => Object.fromEntries(h.map((k, i) => [k, isNaN(+r[i]) ? r[i] : +r[i]]))); })();
const injS = (m, s) => INJ.find((r) => r.method === m && Math.abs(r.size - s) < 1e-9);
const S_EXP = "results/explainability.json";
const S_DER = "paper/figures/derived_stats.json (from results/macro/flags.csv)";
const COMMIT = execSync("git rev-parse --short HEAD", { cwd: ROOT }).toString().trim();

// ---------- number registry
const NUMS = [];
let SEC = "front";
function V(value, source, fmt = (x) => String(x)) {
  const text = fmt(value);
  NUMS.push({ section: SEC, text, source });
  return text;
}
const f2 = (x) => x.toFixed(2), f3 = (x) => x.toFixed(3), pc = (x, d = 1) => (100 * x).toFixed(d) + "%";
const comma = (x) => Math.round(x).toLocaleString("en-US");
const ratio = (logv) => Math.exp(logv).toFixed(2) + "×";
const cardNum = (label) => {
  const m = CARD.match(new RegExp("\\| " + label + " \\| ([^|]+) \\|"));
  return m ? m[1].trim() : "n/a";
};

// ---------- styles
const FONT = "Times New Roman";
const BODY = 20; // 10 pt
function runs(text, base = {}) {
  const out = [], re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, size: BODY, ...base }));
    const t = m[0];
    out.push(t.startsWith("**") ? new TextRun({ text: t.slice(2, -2), bold: true, font: FONT, size: BODY, ...base })
                                : new TextRun({ text: t.slice(1, -1), italics: true, font: FONT, size: BODY, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, size: BODY, ...base }));
  return out;
}
const P = (t) => new Paragraph({ children: runs(t), alignment: AlignmentType.JUSTIFIED, spacing: { after: 80, line: 240 },
  indent: { firstLine: 200 } });
const P0 = (t) => new Paragraph({ children: runs(t), alignment: AlignmentType.JUSTIFIED, spacing: { after: 80, line: 240 } });
const H1 = (t) => { SEC = t; return new Paragraph({ heading: HeadingLevel.HEADING_1, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: t.toUpperCase(), font: FONT, size: BODY, smallCaps: true })], spacing: { before: 160, after: 80 } }); };
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text: t, font: FONT, size: BODY, italics: true })], spacing: { before: 100, after: 60 } });
const EQ = (t, n) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60, after: 60 },
  children: [new TextRun({ text: t, font: "Cambria Math", size: BODY, italics: true }),
             new TextRun({ text: `\t(${n})`, font: FONT, size: BODY })] });
const B = (t) => new Paragraph({ children: runs(t), numbering: { reference: "bul", level: 0 }, spacing: { after: 40 },
  alignment: AlignmentType.JUSTIFIED });

const COLW = 3.35 * 96; // column width in px for images (3.35 in)
function pngSize(f) { const b = fs.readFileSync(f); return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; }
let FIGN = 0;
const FIGS = {};
function FIG(key, file, caption, wIn = 3.35) {
  FIGN += 1; FIGS[key] = FIGN;
  const full = path.join(ROOT, file), { w, h } = pngSize(full), width = wIn * 96;
  return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60, after: 20 }, keepNext: true, keepLines: true,
      children: [new ImageRun({ type: "png", data: fs.readFileSync(full), transformation: { width, height: Math.round(width * h / w) } })] }),
    new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 100 },
      children: runs(`**Fig. ${FIGN}.** ${caption}`, { size: 16 }) })];
}
let TABN = 0;
const roman = (n) => ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"][n - 1];
const border = { style: BorderStyle.SINGLE, size: 4, color: "000000" }, none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const COL_DXA = 4900; // text width of one column: (12240 - 2*1008 - 360) / 2
function TABLE(caption, header, rows, widths0, note) {
  TABN += 1;
  const s0 = widths0.reduce((a, b) => a + b, 0);
  const widths = widths0.map((w) => Math.floor(w * COL_DXA / s0));
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (t, w, opt = {}) => new TableCell({ width: { size: w, type: WidthType.DXA },
    borders: { top: opt.top ? border : none, bottom: opt.bottom ? border : none, left: none, right: none },
    margins: { top: 20, bottom: 20, left: 50, right: 50 },
    children: [new Paragraph({ children: runs(String(t), { size: 14, bold: !!opt.bold }), keepNext: !opt.last, keepLines: true,
      alignment: opt.left ? AlignmentType.LEFT : AlignmentType.CENTER })] });
  const out = [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 100, after: 40 }, keepNext: true,
      children: [new TextRun({ text: `TABLE ${roman(TABN)}`, font: FONT, size: 16 })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, keepNext: true,
      children: [new TextRun({ text: caption, font: FONT, size: 16, smallCaps: true })] }),
    new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths, layout: "fixed", rows: [
      new TableRow({ tableHeader: true, cantSplit: true, children: header.map((h, i) => cell(h, widths[i], { top: true, bottom: true, bold: true, left: i === 0 })) }),
      ...rows.map((r, ri) => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, widths[i], { left: i === 0, bottom: ri === rows.length - 1, last: ri === rows.length - 1 })) })),
    ] })];
  if (note) out.push(new Paragraph({ spacing: { before: 30, after: 100 }, children: runs(note, { size: 14 }) }));
  else out.push(new Paragraph({ spacing: { after: 80 }, children: [] }));
  return out;
}

// ---------- data shortcuts
const C = SYN.configs, full = C.kashf_full, RF = RR.configs.kashf_full;
const st = MAC.stats, cfgM = MAC.config;
const inj = (m, s) => MAC.injection.find((r) => r.method === m && Math.abs(r.size - s) < 1e-9);
const sh = ROB.shift, same = sh.same_generator, shifted = sh.shifted_generator;
const S_SUM = "results/summary.json", S_RR = "results/real_reference/summary.json", S_ROB = "results/robustness.json",
  S_MAC = "results/macro/macro_summary.json", S_CARD = "docs/DATA_CARD.md";
const fatfDate = (FATF.match(/as_of: "([^"]+)"/) || [])[1];
const nCfa = (FATF.split("call_for_action:")[2] || "").split("increased_monitoring:")[0].match(/^  [A-Z]{2}:/gm).length;
const nIm = (FATF.split("increased_monitoring:")[2] || "").match(/^  [A-Z]{2}:/gm).length;
const top = MAC.case_study;
const zaf = top.filter((r) => r.partner_iso === "ZAF" && r.hs6 === "710231");

// ---------- content
const front = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({
    text: "Kashf: Two-Layer, Explainable Screening for Trade-Based Money Laundering in UAE Trade Using Real Mirror Statistics and Invoice Evidence",
    font: FONT, size: 44 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Lilan Getachew", font: FONT, size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({
    text: "Department of Computer Science and Engineering, Amity University Dubai, UAE", font: FONT, size: 18, italics: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 }, children: [new TextRun({
    text: "getachewlilan@gmail.com", font: FONT, size: 18 })] }),
];
SEC = "Abstract";
const abstract = new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 80 }, children: [
  new TextRun({ text: "Abstract—", bold: true, italics: true, font: FONT, size: 18 }),
  ...runs(
    `Trade-based money laundering (TBML) hides value in mispriced, misdescribed or fictitious trade. We present Kashf, an open screening system with two layers. ` +
    `The macro layer compares what the UAE and its partners reported to UN Comtrade for the same flows (mirror statistics) on **real data**: ${V(st.pairs, S_MAC + " stats.pairs", comma)} UAE × partner × HS6 × year pairs for ${V(st.years.length, S_MAC + " stats.years", String)} years. ` +
    `UAE imports reconcile with partner reports (median ratio ${V(st.median_gap_by_direction.uae_import, S_MAC + " stats.median_gap_by_direction.uae_import", ratio)}), but partners record only ${V(st.median_gap_by_direction.uae_export, S_MAC + " stats.median_gap_by_direction.uae_export", ratio)} of UAE export value, consistent with re-exports booked under the country of origin. ` +
    `Fixed thresholds set before seeing the data flagged ${V(st.absolute_flag_rate, S_MAC + " stats.absolute_flag_rate", (x) => pc(x, 0))} of pairs; a per-product peer baseline, adopted after seeing the data and disclosed, flags ${V(st.rule_flag_rate, S_MAC + " stats.rule_flag_rate", pc)}. ` +
    `Injected misinvoicing in real flows is recovered only when large (recall ${V(inj("rules", 1.0).recall_on_unflagged, S_MAC + " injection[rules,1.0].recall_on_unflagged", f2)} at ×2, ${V(inj("rules", 9.0).recall_on_unflagged, S_MAC + " injection[rules,9.0].recall_on_unflagged", f2)} at ×10). ` +
    `The invoice layer combines price, document, counterparty-graph and route detectors with calibrated, evidence-carrying scores; on a **synthetic** benchmark it reaches F1 ${V(full.f1.mean, S_SUM + " configs.kashf_full.f1.mean", f3)} (${V(RF.f1.mean, S_RR + " configs.kashf_full.f1.mean", f3)} with real Comtrade reference prices), falling to ${V(shifted.f1.mean, S_ROB + " shift.shifted_generator.f1.mean", f3)} under generator shift. We define explainability operationally and test it: dropping an alert's strongest evidence removes it in ${V(EXP.synthetic.deletion.all_alerts.drop_top_removes_alert, S_EXP + " synthetic.deletion.all_alerts.drop_top_removes_alert", (x) => pc(x, 0))} of cases. Against published NGO reports on gold flows, the rules flag all ${V(EXT.methods.kashf_rules.keys_flagged_by_kind.mirror_discrepancy, S_EXT + " methods.kashf_rules.keys_flagged_by_kind.mirror_discrepancy", String)} documented mismatches present in the data, though a GFI-style dollar gap ranks them higher; on IBM's independent AMLworld data the circular-trade rule, adapted to transfer data, finds ${V(AML.methods.kashf_cycle_adapted.recall_by_typology.cycle, S_AML + " methods.kashf_cycle_adapted.recall_by_typology.cycle", (x) => pc(x, 0))} of cycle-pattern transfers at precision ${V(AML.methods.kashf_cycle_adapted.all.precision, S_AML + " methods.kashf_cycle_adapted.all.precision", f2)} but only ${V(AML.methods.kashf_cycle_adapted.all.recall, S_AML + " methods.kashf_cycle_adapted.all.recall", (x) => pc(x, 1))} of all laundering, and as shipped almost none.`, { size: 18 }) ] });
const keywords = new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 160 }, children: [
  new TextRun({ text: "Index Terms—", bold: true, italics: true, font: FONT, size: 18 }),
  new TextRun({ text: "trade-based money laundering, mirror statistics, UN Comtrade, anomaly detection, explainable AI, United Arab Emirates.", font: FONT, size: 18, italics: true })] });

const body = [];
body.push(H1("I. Introduction"));
body.push(P0("TBML moves value across borders by misrepresenting the price, quantity, quality or existence of traded goods [1], [2]. Each transaction can look like ordinary business, and the evidence is spread across invoices, transport documents, ownership records and national statistics. The UAE is a major re-export hub, and its national risk assessment names TBML a predominant threat, notes that legal persons are abused through front and shell entities, and that free trade zones are vulnerable to money laundering [9]."));
body.push(P("Two families of methods exist. Statistical approaches compare declared prices with the distribution for the same product [3] or compare what trading partners report for the same flows [4]. Transaction-level approaches inspect one company's records. The first works on public data but cannot point at a company; the second can, but labelled data is confidential. Kashf combines both layers and is built to be checked: every alert carries the facts behind it and the innocent explanations to rule out first."));
body.push(P("**Contributions.** (i) An open mirror-statistics layer on real UN Comtrade data for the UAE, with explicit handling of re-exports, estimated quantities and mixed quantity units; (ii) an honest measurement of what such statistics can detect, using misinvoicing injected into real flows; (iii) an invoice layer of four transparent detectors with calibrated weights and fuzzy entity resolution, evaluated with ablations, published-method baselines, two shift tests and an independent benchmark; (iv) an operational definition of explainability with a deletion test; (v) external checks against published reports and public FATF/Egmont cases, including what Kashf misses; (vi) code, data card and results released for reproduction. To our knowledge, no open tool combines both layers with per-flag benign explanations."));

body.push(H1("II. Related Work"));
body.push(P0("FATF and the Egmont Group document TBML typologies and red-flag indicators [1], [2]. Zdanowicz and colleagues flag trade priced outside the inter-quartile range of prices for the same product [3], [12]. Global Financial Integrity estimates trade misinvoicing from mismatches between partner-reported trade statistics [4], [13]; Kashf uses the same mirror principle, but as a screening signal on individual UAE × partner × product flows rather than as a national estimate. Anomaly detectors such as the Isolation Forest [6] are common when labels are scarce, and SHAP [7] attributes a model's output to its inputs; Kashf uses both as a comparison and for per-flag explanations. Synthetic data is standard in AML research because real labels are confidential [10]; IBM's AMLworld [10] gives an independent transaction benchmark with planted laundering patterns. We implement the IQR filter and a GFI-style gap as baselines."));

body.push(H1("III. Data"));
SEC = "III. Data";
body.push(H2("A. Real: UN Comtrade (macro layer)"));
body.push(P0(`Annual HS data were retrieved from the UN Comtrade API [5] on ${V(cardNum("Pull date\\(s\\) \\(UTC\\)"), S_CARD + " Pull date", String)}: ${V(cardNum("API calls logged"), S_CARD + " API calls logged", String)}, ${V(cardNum("Rows cached"), S_CARD + " Rows cached", String)} rows, for ${V(st.hs6, S_MAC + " stats.hs6", String)} HS6 codes (${V(cardNum('HS6 codes'), S_CARD + ' HS6 codes', (x) => x.replace(' (kashf/reference.py)', '').replace('base', 'reference-table products'))}) and ${V(st.partners, S_MAC + " stats.partners", String)} partners. Three query families were used: the UAE's own exports (X), re-exports (RX), imports (M) and re-imports (RM) by partner; every partner's imports from and exports to the UAE; and all reporters' exports to the world, for the global unit-value distribution. All queries use totals (partner2 = World, all customs procedures, all transport modes). The UAE had not reported 2024 at the time of the pull. Quantities reported in a non-standard unit for their HS6, and quantities and weights estimated by Comtrade, were excluded; the data card in the repository lists coverage, missing shares and caveats. Redistribution of the derived per-pair file follows UN Comtrade's small-data guidance [11].`));
const cov = {};
for (const m of CARD.matchAll(/^\| (mirror|uae|world) \| (\d{4}) \| ([\d,]+) \| (\d+) \| (\d+) \| (\d+) \| (\d+)% \| (\d+)% \| (\d+)% \|$/gm)) {
  const [, fam, yr, rows, , , , mq, mw, ew] = m;
  if (+yr > 2023) continue;
  (cov[fam] = cov[fam] || []).push({ rows: +rows.replace(/,/g, ""), mq: +mq, mw: +mw, ew: +ew });
}
const FAM = { uae: "UAE as reporter (X, RX, M, RM)", mirror: "Partners' trade with UAE", world: "All reporters to World" };
body.push(...TABLE("Real UN Comtrade rows used, 2020–2023 (from the data card)",
  ["Query family", "Rows", "Missing qty", "Missing weight", "Est. weight"],
  ["uae", "mirror", "world"].filter((k) => cov[k]).map((k) => {
    const r = cov[k], n = r.reduce((a, b) => a + b.rows, 0), avg = (f) => Math.round(r.reduce((a, b) => a + b[f] * b.rows, 0) / n);
    return [FAM[k], V(n, S_CARD + ` coverage ${k} rows 2020-2023 (sum)`, comma), V(avg("mq"), S_CARD + ` coverage ${k} missing qty (row-weighted)`, (x) => x + "%"),
      V(avg("mw"), S_CARD + ` coverage ${k} missing net weight (row-weighted)`, (x) => x + "%"), V(avg("ew"), S_CARD + ` coverage ${k} estimated weight (row-weighted)`, (x) => x + "%")];
  }),
  [2000, 900, 900, 950, 900],
  "Shares are row-weighted means of the data card's per-year values. 2024 rows (partners only) are excluded because the UAE had not reported 2024."));
body.push(P0(`Table ${roman(TABN)} summarises the rows used. Missing and estimated quantities matter because unit values and weight gaps need them; value gaps do not. The high share of estimated weights among partner reports is why estimated values are excluded rather than trusted.`));
body.push(H2("B. Synthetic: invoice benchmark"));
body.push(P0(`Labelled TBML records are confidential, so the invoice layer is evaluated on a generator of synthetic UAE trade (${V(SYN.protocol.invoices_per_seed, S_SUM + ' protocol.invoices_per_seed', comma)} invoices per instance, ${V(SYN.counts.reduce((a,c)=>a+c.laundering/c.invoices,0)/SYN.counts.length, S_SUM + ' counts[].laundering/invoices (mean)', pc)} laundering across ${V(Object.keys(SYN.counts[0]).length-2, S_SUM + ' counts[0] typology keys', String)} planted typologies, with deliberately noisy legitimate trade such as premium and clearance pricing, shared business-centre addresses and missing paperwork). Companies in high-risk jurisdictions use the FATF lists of ${V(fatfDate, "configs/fatf_lists.yaml as_of", String)} [8] (${V(nCfa, "configs/fatf_lists.yaml call_for_action count", String)} call-for-action and ${V(nIm, "configs/fatf_lists.yaml increased_monitoring count", String)} increased-monitoring jurisdictions). Reference prices are either illustrative or the real Comtrade medians from Section III-A. Ten typologies are planted: over- and under-invoicing, phantom shipments, multiple invoicing, misdescription, circular trading, shell clusters, transshipment through a FATF-listed jurisdiction, U-turn trade, and shell networks registered under spelling variants; legitimate look-alikes include calls at listed regional ports and genuine returns. **All invoice-layer results are synthetic.**`));
body.push(H2("C. External and independent data"));
body.push(P0(`**Published reports (real flows).** SWISSAID's study of African gold [14] and its 2025 statement [15], and a Reuters report of its Ghana study [16], name gold flows into the UAE as mismatched or as transit routes. We list them in data/external_validation.csv with source and page: ${V(EXT.documented_keys, S_EXT + " documented_keys", String)} (partner, year) flows, of which ${V(EXT.documented_keys_in_data, S_EXT + " documented_keys_in_data", String)} exist as eligible mirror pairs. **These are not laundering labels.** **AMLworld (independent synthetic).** IBM's HI-Small set [10], [17]: ${V(AML.transfers, S_AML + " transfers", comma)} transfers, ${V(AML.laundering, S_AML + " laundering", comma)} labelled laundering. **Public cases.** Six scenarios reconstructed from FATF/Egmont case boxes [1], with invented names and values.`));

body.push(H1("IV. Method"));
SEC = "IV. Method";
body.push(P0(`Fig. ${FIGN + 1} shows the two layers and how they connect.`));
body.push(...FIG("arch", "paper/figures/fig_architecture.png", "Two-layer architecture. The macro layer works on real UN Comtrade statistics and also supplies real reference prices to the invoice layer; the analyst makes every decision."));
body.push(H2("A. Macro layer"));
body.push(P0(`For a flow reported by both sides, with importer value v_m, exporter value v_x and an assumed CIF/FOB margin c = ${V(cfgM.cif_fob_factor, S_MAC + " config.cif_fob_factor", String)},`));
body.push(EQ("g = ln( v_m / ((1 + c) · v_x) )", 1));
body.push(P0("For UAE exports, v_x is reported both as X + RX and as domestic exports X alone. The weight gap uses net weights without a freight margin. Each side's unit value u (per kg or per unit, by the HS6 code's usual unit) is compared with all reporters' exports of that HS6 in that year by a robust z-score,"));
body.push(EQ("z = ( ln u − med ln u ) / ( 1.4826 · MAD ln u )", 2));
body.push(P0(`Because gaps carry systematic, product-specific offsets (Section VI-A), the rules compare each pair's gap with the median and MAD of pairs of the same HS6 and direction (eq. 2 applied to g), flagging |z| > ${V(cfgM.gap_z_threshold, S_MAC + " config.gap_z_threshold", String)} for the value or weight gap, or a unit-value |z| > ${V(cfgM.uv_z_threshold, S_MAC + " config.uv_z_threshold", String)}. **This peer baseline was adopted after seeing the real data**, because the absolute thresholds fixed beforehand (|g| > ln 1.5) flagged ${V(st.absolute_flag_rate, S_MAC + " stats.absolute_flag_rate", (x) => pc(x, 0))} of pairs. An Isolation Forest [6] on the same features is the ML comparison, explained per flag with SHAP [7]. Only pairs with both sides of at least $${V(cfgM.min_flow_usd, S_MAC + " config.min_flow_usd", comma)} are scored.`));
body.push(H2("B. Invoice layer"));
body.push(P0("Four detectors read a trader's records: a price benchmark (eq. 2 on invoice unit prices against the reference table), document consistency (missing, reused or contradictory transport documents and packing lists), a counterparty graph (shared directors, phones, addresses, accounts, matched after normalising formats and, for names, by rapidfuzz similarity together with a similar address; circular trades of three to five hops) and route risk (transit through FATF-listed jurisdictions, loops, excess legs, and U-turns where goods exported from the UAE come back from the same party). Each rule r is weighted by its Laplace-smoothed precision on a labelled tuning set, w_r = (TP_r + 1)/(F_r + 2), and signals are combined by a noisy-OR:"));
body.push(EQ("s = 1 − ∏_r ( 1 − w_r )", 3));
body.push(P0("An invoice is an alert when s reaches a threshold tuned on the tuning instance. Every signal carries a sentence of evidence built from the records, which the dashboard shows next to the score."));
body.push(H2("C. What \u201cexplainable\u201d means in Kashf"));
body.push(P0("An analyst who escalates or closes a TBML alert has to justify the decision in a case file, so a score alone is not enough: the analyst needs the facts behind it and a way to check them. We call an alert *explainable* when it lists the specific evidence (values, benchmark and rule) that produced it, **and removing that evidence removes the alert**. The second half is testable, and Section VII-B tests it. Kashf meets the first half in four ways."));
body.push(B("**Transparent by design.** Every detector is a rule a compliance officer can read: a robust z-score against a stated reference (eq. 2), a document check, a graph pattern or a listed jurisdiction. Thresholds are in readable units (standard deviations, value ratios), not learned weights."));
body.push(B("**Decomposable score.** Each rule's weight w_r is its measured precision on the tuning set, and eq. 3 combines them, so the contribution of every signal to an alert can be read off and removed (the ablations in Table V do exactly this)."));
body.push(B("**Evidence in the analyst's terms.** Each signal is rendered as a sentence with the numbers from the records. A real macro flag (Table IV, row 2) reads: *\u201c" + V(MAC.case_study[1].why.split("; net weight")[0], S_MAC + " case_study[1].why (value-gap clause)", String) + "\u201d*."));
body.push(B("**Benign explanations first.** Every macro flag lists the innocent causes to rule out (re-export attribution, CIF/FOB margins, timing, units), so the explanation argues against the alert as well as for it."));
body.push(P0("Only the Isolation Forest comparison needs a post-hoc explanation; there, SHAP [7] attributes each anomaly score to the four gap and unit-value features. Kashf\u2019s own alerts need none, because the score is built from the explanations rather than explained after the fact. Whether the evidence helps analysts decide faster or better is a separate question that needs a user study; we provide a protocol (docs/user_study.md) but have not run it."));

body.push(H1("V. Experiments"));
SEC = "V. Experiments";
body.push(P0(`**Real (macro).** No ground-truth labels exist for real flows, so detection is measured by injection: in each of ${V(cfgM.injection_repeats, S_MAC + " config.injection_repeats", String)} repeats, ${V(cfgM.injection_share, S_MAC + " config.injection_share", (x) => pc(x, 0))} of eligible pairs have the importer-reported value multiplied or divided by a factor from ${V(1+Math.min(...MAC.injection.map((r) => r.size)), S_MAC + ' injection[].size (1 + min)', String)} to ${V(1+Math.max(...MAC.injection.map((r) => r.size)), S_MAC + ' injection[].size (1 + max)', String)}. We report recall on injected pairs that the rules had not already flagged before injection, precision (a lower bound, since natural anomalies count as false positives) and PR-AUC against the random baseline. Baselines: a GFI-style gap (|v_m/(1+c) − v_x| in dollars, ranked) [13] and the IQR filter on each side's unit value [12], both flagging as many pairs as the rules. For the published flows we report how many are flagged, their rank among all pairs and precision@k.`));
body.push(P0("**Synthetic (invoice).** Instance 0 tunes calibration and thresholds; held-out instances 1–5 are reported as mean ± s.d. Baselines: price benchmark alone, the IQR price filter [12], a rule checklist and an Isolation Forest on invoice features; an ablation with exact identifier matching measures entity resolution. Robustness: one-at-a-time sweeps of hand-set thresholds and of the alert threshold; a noise shift (more price noise, more premium and clearance goods, subtler mispricing); and different typology mechanics (longer and slower rings with drifting quantities, shells linked only by a bank account, split multiple invoicing, subtler mispricing), written without first running the detectors. **AMLworld.** Accounts become companies and each transfer becomes a trade passing value from payer to payee; with no HS codes, prices, documents, routes or identifiers, only the circular-trade rule applies, run as shipped and adapted (timestamps, amounts in USD at the data's own exchange rates, up to 10 hops), against degree rules (k chosen on the first half of days) and a time-free cycle check."));

body.push(H1("VI. Results: Real Data (UN Comtrade)"));
SEC = "VI. Results (real)";
body.push(H2("A. What real UAE mirror data look like"));
body.push(P0(`Of ${V(st.pairs, S_MAC + " stats.pairs", comma)} pairs, ${V(st.eligible, S_MAC + " stats.eligible", comma)} pass the value filter. UAE imports reconcile with partner exports (median ratio ${V(st.median_gap_by_direction.uae_import, S_MAC + " stats.median_gap_by_direction.uae_import", ratio)} after the CIF/FOB margin), which supports the method. For UAE exports, partners report only ${V(st.uae_export_median_gap_x_plus_rx, S_MAC + " stats.uae_export_median_gap_x_plus_rx", ratio)} of the X + RX value and ${V(st.uae_export_median_gap_x_only, S_MAC + " stats.uae_export_median_gap_x_only", ratio)} of domestic exports alone; re-exports are ${V(st.uae_export_rx_share_of_value, S_MAC + " stats.uae_export_rx_share_of_value", (x) => pc(x, 0))} of export value in these pairs (Fig. ${FIGN + 1}). A single absolute threshold therefore flags most export pairs, which is why the peer baseline is used.`));
body.push(...FIG("gaps", "paper/figures/fig_mirror_gaps.png", "Real mirror gaps (eq. 1) for eligible pairs. UAE imports centre near zero; UAE exports are shifted left, less so against domestic exports (X) alone. Source: results/macro/flags.csv."));
body.push(H2("B. What the rules flag"));
body.push(P0(`The rules flag ${V(DER.rule_flags, S_DER + " rule_flags", comma)} of ${V(DER.eligible, S_DER + " eligible", comma)} eligible pairs and the Isolation Forest ${V(DER.if_flags, S_DER + " if_flags", comma)}; ${V(DER.both_flags, S_DER + " both_flags", comma)} are flagged by both. The flag rate is similar every year (${V(Math.min(...Object.values(DER.flag_rate_by_year)), S_DER + " min flag_rate_by_year", pc)}–${V(Math.max(...Object.values(DER.flag_rate_by_year)), S_DER + " max flag_rate_by_year", pc)}), and higher for UAE imports (${V(DER.flag_rate_by_direction.uae_import, S_DER + " flag_rate_by_direction.uae_import", pc)}) than for UAE exports (${V(DER.flag_rate_by_direction.uae_export, S_DER + " flag_rate_by_direction.uae_export", pc)}), since the peer baseline absorbs the systematic export shortfall. The three reasons contribute about equally (Table ${roman(TABN + 1)}); the most-flagged products are petroleum oils (HS 2710) and gold (HS 7108), which are high-value, heavily re-traded goods.`));
body.push(...TABLE("Reasons behind real rule flags (a flag can have several)",
  ["Reason", "Flagged pairs"],
  [[`Value gap beyond ${cfgM.gap_z_threshold} robust SD of peers`, V(DER.reason_value_gap, S_DER + " reason_value_gap", comma)],
   [`Weight gap beyond ${cfgM.gap_z_threshold} robust SD of peers`, V(DER.reason_weight_gap, S_DER + " reason_weight_gap", comma)],
   [`Unit value beyond ${cfgM.uv_z_threshold} robust SD of world exports`, V(DER.reason_unit_value, S_DER + " reason_unit_value", comma)],
   ...DER.top_hs6_by_flags.slice(0, 3).map(([h, n], i) => [`Top product ${i + 1}: HS ${h}`, V(n, S_DER + ` top_hs6_by_flags[${i}]`, comma)])],
  [3400, 1500], "Real (UN Comtrade). Source: results/macro/flags.csv."));
body.push(P0(`The two detectors also agree on *why*: for the ${V(EXP.macro.pairs_flagged_by_both, S_EXP + " macro.pairs_flagged_by_both", comma)} pairs both flag, the feature SHAP ranks first for the Isolation Forest belongs to a rule that fired in ${V(EXP.macro.shap_top1_in_fired_rule, S_EXP + " macro.shap_top1_in_fired_rule", pc)} of cases, against ${V(EXP.macro.random_top1_expected, S_EXP + " macro.random_top1_expected", pc)} expected by chance.`));
body.push(H2("C. Detection of injected misinvoicing"));
const sizes = [0.1, 0.5, 1.0, 2.0, 4.0, 9.0], lab = (s) => s >= 1 ? `×${(1 + s).toFixed(0)}` : `±${(100 * s).toFixed(0)}%`;
body.push(...TABLE("Recall on real flows with injected distortion (real flows + synthetic distortion)",
  ["Distortion", "Rules recall", "IF recall", "Rules PR-AUC", "IF PR-AUC", "Random"],
  sizes.map((s) => [lab(s),
    V(inj("rules", s).recall_on_unflagged, S_MAC + ` injection[rules,${s}].recall_on_unflagged`, f2),
    V(inj("iforest", s).recall_on_unflagged, S_MAC + ` injection[iforest,${s}].recall_on_unflagged`, f2),
    V(inj("rules", s).pr_auc, S_MAC + ` injection[rules,${s}].pr_auc`, f2),
    V(inj("iforest", s).pr_auc, S_MAC + ` injection[iforest,${s}].pr_auc`, f2),
    V(inj("rules", s).pr_auc_random, S_MAC + ` injection[rules,${s}].pr_auc_random`, f2)]),
  [1100, 1050, 900, 1050, 950, 850],
  "Recall counts only injected pairs not flagged before injection. Rules flag rate on unaltered real data: " +
  V(st.rule_flag_rate, S_MAC + " stats.rule_flag_rate", pc) + "; Isolation Forest " + V(st.if_flag_rate, S_MAC + " stats.if_flag_rate", pc) + "."));
body.push(P0(`Table ${roman(TABN)} gives recall and PR-AUC at each size. Moderate misinvoicing is not separable from normal reporting noise: at ×2 the rules recover ${V(inj("rules", 1.0).recall_on_unflagged, S_MAC + " injection[rules,1.0].recall_on_unflagged", f2)} of injected pairs, and only at ×10 do they reach ${V(inj("rules", 9.0).recall_on_unflagged, S_MAC + " injection[rules,9.0].recall_on_unflagged", f2)} (Fig. ${FIGN + 1}). The Isolation Forest stays close to random. Country-level statistics are therefore a coarse first screen, which motivates the invoice layer.`));
body.push(...FIG("inj", "paper/figures/fig_injection.png", "Recall vs injected distortion factor on real UN Comtrade flows (mean of repeats). Source: results/macro/macro_summary.json."));
body.push(H2("D. Published baselines and published flows"));
const bsz = [[1.0, "×2"], [4.0, "×5"], [9.0, "×10"]];
body.push(...TABLE("Recall on injected real flows at the rules' flag rate (published baselines)",
  ["Distortion", "Kashf rules", "GFI-style gap", "IQR filter"],
  bsz.map(([z, lab]) => [lab, V(injS("rules", z).recall, S_INJ + ` rules size ${z} recall`, f3),
    V(injS("gfi_gap_topk", z).recall, S_INJ + ` gfi_gap_topk size ${z} recall`, f3),
    V(injS("iqr_filter_topk", z).recall, S_INJ + ` iqr_filter_topk size ${z} recall`, f3)]),
  [1200, 1200, 1300, 1200], "Real flows with synthetic distortion. GFI-style gap and IQR filter flag the top k pairs, k = the rules' flag count."));
body.push(P0(`On injected distortions (Table ${roman(TABN)}) the IQR filter is level with or ahead of the rules at moderate sizes, because it reads exactly the unit value the injection changes; its own rule (any unit value outside [Q1, Q3]) flags ${V(injS("iqr_filter", 1.0).flag_rate, S_INJ + " iqr_filter size 1.0 flag_rate", (x) => pc(x, 0))} of real pairs. The GFI-style dollar gap is close to random here, because it ranks by flow size.`));
const EM = EXT.methods, kin = (m, k) => EM[m].keys_flagged_by_kind[k] || 0;
body.push(...TABLE("Published gold flows (SWISSAID) among real mirror pairs — not laundering labels",
  ["Method", "Mismatches flagged", "Transit flows flagged", "Median rank", "P@10 (gold imports)"],
  [["Kashf rules", "kashf_rules"], ["Isolation Forest", "isolation_forest"], ["GFI-style gap", "gfi_gap"], ["IQR filter", "iqr_filter"]].map(([lab, m]) => [lab,
    `${V(kin(m, "mirror_discrepancy"), S_EXT + ` methods.${m} mirror flagged`, String)}/${EXT.by_kind.mirror_discrepancy.in_data}`,
    `${V(kin(m, "transit_hub"), S_EXT + ` methods.${m} transit flagged`, String)}/${EXT.by_kind.transit_hub.in_data}`,
    V(EM[m].median_best_rank, S_EXT + ` methods.${m}.median_best_rank`, comma),
    V(EM[m].precision_at_k["10"].gold_import_pairs, S_EXT + ` methods.${m}.precision_at_k.10.gold_import_pairs`, f2)]),
  [1300, 1100, 1100, 900, 1000], `Rank among ${comma(EXT.eligible_pairs)} pairs (best HS 710812/710813 pair per flow). Random P@10 within the ${V(EXT.gold_import_pairs, S_EXT + " gold_import_pairs", String)} gold import pairs: ${V(EXT.random.precision_gold_import_pairs, S_EXT + " random.precision_gold_import_pairs", f3)}. Source: results/external_validation.json.`));
body.push(P0(`Of the flows the reports name, ${V(EXT.documented_keys - EXT.documented_keys_in_data, S_EXT + " documented_keys - documented_keys_in_data", String)} cannot be mirror pairs at all: the partner did not report to UN Comtrade (e.g. Chad, Sudan, Togo in the named years) or one side fell below the value filter, which is itself a limit of mirror screening. The rules flag every documented mismatch that is in the data, and none of the transit flows, which reconcile in the statistics because the anomaly lies in the origin, not the reported values. Ranked by score, however, the documented flows sit mid-table for the rules and near the top for the GFI-style gap (Table ${roman(TABN)}): Kashf scores each pair against its own product's peers, which deliberately discounts the sheer size of gold flows that makes them stand out in dollars.`));
body.push(H2("E. Case study: top flagged real flows"));
const shortBenign = (t) => t.split(";")[0];
body.push(...TABLE("Top 10 flagged real flows (rules), with the first benign explanation to check",
  ["Flow, HS6, year", "Importer / exporter value", "Check first"],
  top.slice(0, 10).map((r, i) => [
    `${r.direction === "uae_export" ? "UAE→" + r.partner_iso : r.partner_iso + "→UAE"}, ${r.hs6}, ${r.year}`,
    `${V(r.value_imp, S_MAC + ` case_study[${i}].value_imp`, (x) => "$" + (x / 1e6).toFixed(2) + "M")} / ${V(r.value_exp, S_MAC + ` case_study[${i}].value_exp`, (x) => "$" + (x / 1e6).toFixed(2) + "M")}`,
    shortBenign(r.benign)]),
  [1500, 1700, 2900],
  "Ranked by rule score (largest ratio of a robust z-score to its threshold). Flags are reasons to look at a country × product × year aggregate, not findings against any person or company. Full reasons: results/macro/macro_results.md."));
if (zaf.length) {
  const z = zaf[0];
  body.push(P0(`Table ${roman(TABN)} lists the ten highest-scoring flags. The strongest value-gap flags are UAE diamond exports to South Africa (HS 710231): in ${V(z.year, S_MAC + " case_study[ZAF].year", String)} the UAE reported $${V(z.value_exp, S_MAC + " case_study[ZAF].value_exp", (x) => (x / 1e6).toFixed(1))}M of exports and re-exports while South Africa reported $${V(z.value_imp, S_MAC + " case_study[ZAF].value_imp", (x) => (x / 1e6).toFixed(2))}M of imports from the UAE (Fig. ${FIGN + 1}). The first benign explanation is that South Africa records these diamonds under their country of origin; others are timing and classification. Kashf shows this list next to the flag so that an analyst checks it before suspecting anything.`));
}
body.push({ SPAN: FIG("macro", "paper/figures/screen_macro_diamonds.png", "Macro view (real UN Comtrade data): mirror gap of HS 710231 diamonds between the UAE and South Africa by year (UAE exports dark, UAE imports light, peer medians dashed); flagged years in red, each with its reasons and the benign explanations to check first.", 5.6) });

body.push(H1("VII. Results: Synthetic Benchmark"));
SEC = "VII. Results (synthetic)";
body.push(H2("A. Main results and ablations"));
SEC = "VII. Results (synthetic)";
const cfgs = ["kashf_full", "kashf_heuristic", "exact_entities", "minus_price", "minus_route", "minus_documents", "minus_graph", "price_only", "iqr_price_filter", "isolation_forest", "checklist"];
const NAME = { kashf_full: "Kashf (calibrated)", kashf_heuristic: "Kashf (hand-set)", minus_price: "– price", minus_route: "– route",
  minus_documents: "– documents", minus_graph: "– graph", price_only: "Price only", isolation_forest: "Isolation Forest", checklist: "Checklist",
  exact_entities: "Exact ID matching", iqr_price_filter: "IQR price filter" };
body.push(...TABLE("Invoice layer on held-out synthetic instances (mean over 5 × 20,000 invoices)",
  ["Configuration", "Prec.", "Recall", "F1", "False alarms", "F1 (real ref.)"],
  cfgs.map((k) => [NAME[k], V(C[k].precision.mean, S_SUM + ` configs.${k}.precision.mean`, f3),
    V(C[k].recall.mean, S_SUM + ` configs.${k}.recall.mean`, f3), V(C[k].f1.mean, S_SUM + ` configs.${k}.f1.mean`, f3),
    V(C[k].far.mean, S_SUM + ` configs.${k}.far.mean`, (x) => pc(x, 2)), V(RR.configs[k].f1.mean, S_RR + ` configs.${k}.f1.mean`, f3)]),
  [1600, 800, 850, 800, 1000, 1000], "Synthetic data. Last column: same protocol with real UN Comtrade reference prices."));
body.push(P0(`Table ${roman(TABN)} gives the main results and ablations. The full system reaches F1 ${V(full.f1.mean, S_SUM + " configs.kashf_full.f1.mean", f3)} at a ${V(full.far.mean, S_SUM + " configs.kashf_full.far.mean", (x) => pc(x, 2))} false-alarm rate, against ${V(C.price_only.f1.mean, S_SUM + " configs.price_only.f1.mean", f3)} for price benchmarking alone; with real reference prices, whose dispersion is wider, it reaches ${V(RF.f1.mean, S_RR + " configs.kashf_full.f1.mean", f3)}. Removing the document or graph detector costs most (F1 ${V(C.minus_documents.f1.mean, S_SUM + " configs.minus_documents.f1.mean", f3)} and ${V(C.minus_graph.f1.mean, S_SUM + " configs.minus_graph.f1.mean", f3)}); removing the route detector lowers F1 to ${V(C.minus_route.f1.mean, S_SUM + " configs.minus_route.f1.mean", f3)}, so it stays in the score (transshipment recall ${V(C.minus_route.recall_by_typology.transshipment_high_risk.mean, S_SUM + " configs.minus_route.recall_by_typology.transshipment_high_risk", f2)} → ${V(full.recall_by_typology.transshipment_high_risk.mean, S_SUM + " configs.kashf_full.recall_by_typology.transshipment_high_risk", f2)}; U-turn ${V(C.minus_route.recall_by_typology.u_turn.mean, S_SUM + " configs.minus_route.recall_by_typology.u_turn", f2)} → ${V(full.recall_by_typology.u_turn.mean, S_SUM + " configs.kashf_full.recall_by_typology.u_turn", f2)}, held down by genuine returns). With exact identifier matching, name-variant shells are caught ${V(C.exact_entities.recall_by_typology.name_variant.mean, S_SUM + " configs.exact_entities.recall_by_typology.name_variant", f2)} of the time; fuzzy resolution raises this to ${V(full.recall_by_typology.name_variant.mean, S_SUM + " configs.kashf_full.recall_by_typology.name_variant", f2)}. The published IQR price filter flags ${V(C.iqr_price_filter.far.mean, S_SUM + " configs.iqr_price_filter.far.mean", (x) => pc(x, 0))} of clean invoices by construction. Fig. ${FIGN + 1} shows F1 by configuration and Fig. ${FIGN + 2} recall by typology.`));
body.push(...FIG("f1", "paper/figures/fig_synthetic_f1.png", "F1 by configuration on held-out synthetic instances (error bars: s.d.). Source: results/summary.json."));
body.push(...FIG("typ", "paper/figures/fig_typology.png", "Recall by typology, synthetic benchmark. Source: results/summary.json."));
body.push(H2("B. Explanation faithfulness"));
const Dl = EXP.synthetic.deletion, rowsD = [["All alerts", "all_alerts"], ["≥ 2 signals", "multi_signal_alerts"], ["True alerts", "true_alerts"], ["False alerts", "false_alerts"]];
body.push(P0(`For every planted typology, ${V(Math.min(...Object.values(EXP.synthetic.attribution_by_typology).map((v) => v.mean)), S_EXP + " synthetic.attribution_by_typology (min over typologies)", pc)} of true alerts cite a rule that matches the planted mechanism; this is partly by construction, since the detectors were written for these typologies. The deletion test is stricter (Table ${roman(TABN + 1)}): removing an alert's strongest signal and re-scoring with eq. 3 removes the alert in ${V(Dl.all_alerts.drop_top_removes_alert, S_EXP + " synthetic.deletion.all_alerts.drop_top_removes_alert", pc)} of cases, against ${V(Dl.all_alerts.drop_random_removes_alert, S_EXP + " synthetic.deletion.all_alerts.drop_random_removes_alert", pc)} for a random signal. ${V(Dl.share_single_signal, S_EXP + " synthetic.deletion.share_single_signal", pc)} of alerts rest on a single signal; among the rest, ${V(1 - Dl.multi_signal_alerts.drop_top_removes_alert, S_EXP + " 1 - synthetic.deletion.multi_signal_alerts.drop_top_removes_alert", pc)} survive losing their strongest signal because a second, independent signal also crosses the threshold. That is redundant evidence, not unfaithful evidence: removing *all* cited evidence removes every alert, because the score is computed from nothing else.`));
body.push(...TABLE("Deletion test: share of alerts removed when one signal is dropped (synthetic)",
  ["Alerts", "n", "Drop strongest", "Drop random", "Strongest alone ≥ thr."],
  rowsD.map(([lab, k]) => [lab, V(Dl[k].alerts, S_EXP + ` synthetic.deletion.${k}.alerts`, comma),
    V(Dl[k].drop_top_removes_alert, S_EXP + ` synthetic.deletion.${k}.drop_top_removes_alert`, pc),
    V(Dl[k].drop_random_removes_alert, S_EXP + ` synthetic.deletion.${k}.drop_random_removes_alert`, pc),
    V(Dl[k].top_signal_alone_is_alert, S_EXP + ` synthetic.deletion.${k}.top_signal_alone_is_alert`, pc)]),
  [1300, 700, 1000, 1000, 1200], `Held-out seeds ${EXP.synthetic.seeds.join(", ")}; alert threshold ${EXP.synthetic.alert_threshold.toFixed(3)}. Source: results/explainability.json.`));
body.push(H2("C. Robustness"));
body.push(P0(`Varying the alert threshold from ${V(Object.keys(ROB.alert_threshold)[0], S_ROB + ' alert_threshold keys (min)', String)} to ${V(Object.keys(ROB.alert_threshold).slice(-1)[0], S_ROB + ' alert_threshold keys (max)', String)} trades recall for precision (Fig. ${FIGN + 1}, left). Under generator shift, F1 falls from ${V(same.f1.mean, S_ROB + " shift.same_generator.f1.mean", f3)} to ${V(shifted.f1.mean, S_ROB + " shift.shifted_generator.f1.mean", f3)} and the false-alarm rate rises from ${V(same.far.mean, S_ROB + " shift.same_generator.far.mean", (x) => pc(x, 2))} to ${V(shifted.far.mean, S_ROB + " shift.shifted_generator.far.mean", (x) => pc(x, 2))}: weights tuned on one population do not fully transfer, so calibration must be refit for each data source. Under different typology mechanics F1 is ${V(ROB.shift.alt_typologies.f1.mean, S_ROB + " shift.alt_typologies.f1.mean", f3)}, with over- and under-invoicing recall down to ${V(ROB.shift.alt_typologies.recall_by_typology.over_invoicing, S_ROB + " shift.alt_typologies.recall_by_typology.over_invoicing", f2)} and ${V(ROB.shift.alt_typologies.recall_by_typology.under_invoicing, S_ROB + " shift.alt_typologies.recall_by_typology.under_invoicing", f2)} and circular trading to ${V(ROB.shift.alt_typologies.recall_by_typology.circular_trading, S_ROB + " shift.alt_typologies.recall_by_typology.circular_trading", f2)}.`));
const sw = ROB.sweep;
const swAll = Object.values(sw).flatMap((vals) => Object.values(vals).map((v) => v.f1.mean));
body.push(P0(`Sweeping each hand-set threshold one at a time (${Object.keys(sw).join(", ")}) moves F1 only between ${V(Math.min(...swAll), S_ROB + " sweep (min f1 over all settings)", f3)} and ${V(Math.max(...swAll), S_ROB + " sweep (max f1 over all settings)", f3)}, which shows insensitivity on this generator, not robustness on real documents.`));
body.push(...FIG("rob", "paper/figures/fig_robustness.png", "Left: precision, recall and F1 vs alert threshold. Right: F1 on the tuning generator, under a noise shift, and with different typology mechanics. Synthetic. Source: results/robustness.json."));
body.push(H2("D. Independent benchmark: AMLworld"));
const AM = AML.methods;
body.push(...TABLE("IBM AMLworld HI-Small: circular-trade rule vs simple baselines (independent synthetic data)",
  ["Method", "Flagged", "Prec.", "Recall", "F1", "Cycle recall"],
  [["Kashf cycle (as shipped)", "kashf_cycle_as_shipped"], ["Kashf cycle (adapted)", "kashf_cycle_adapted"],
   ["Time-free cycle, 3–5", "timefree_cycle_3to5"], ...Object.keys(AM).filter((k) => k.startsWith("fan_")).map((k) => [k.replace(/_/g, " ").replace(" degree", "-degree"), k]),
   ["Random (same count)", "random_same_count"]].map(([lab, k]) => [lab, V(AM[k].all.flagged, S_AML + ` methods.${k}.all.flagged`, comma),
    V(AM[k].all.precision, S_AML + ` methods.${k}.all.precision`, f3), V(AM[k].all.recall, S_AML + ` methods.${k}.all.recall`, f3),
    V(AM[k].all.f1, S_AML + ` methods.${k}.all.f1`, f3), V(AM[k].recall_by_typology.cycle, S_AML + ` methods.${k}.recall_by_typology.cycle`, f2)]),
  [1700, 900, 650, 700, 650, 800], "All transfers; degree thresholds k chosen on the first half of days. Source: results/amlworld.json."));
body.push(P0(`On data it did not generate (Table ${roman(TABN)}), the rule as shipped almost never fires: AMLworld's cycles change currency from hop to hop, often within one day, and run up to ten hops, while the shipped rule compares amounts only within one currency, orders invoices by calendar day and stops at five hops. Adapted to transfer data without using the labels, it finds ${V(AM.kashf_cycle_adapted.recall_by_typology.cycle, S_AML + " methods.kashf_cycle_adapted.recall_by_typology.cycle", (x) => pc(x, 0))} of cycle-pattern transfers at precision ${V(AM.kashf_cycle_adapted.all.precision, S_AML + " methods.kashf_cycle_adapted.all.precision", f2)}, against ${V(AM.timefree_cycle_3to5.recall_by_typology.cycle, S_AML + " methods.timefree_cycle_3to5.recall_by_typology.cycle", (x) => pc(x, 0))} at precision ${V(AM.timefree_cycle_3to5.all.precision, S_AML + " methods.timefree_cycle_3to5.all.precision", f2)} for a time-free cycle check. Overall recall stays low because most AMLworld laundering follows other patterns (fan-in/out, scatter-gather, stacks) that the rule does not look for; degree rules catch some of them at very low precision.`));
const CV = Object.entries(CASES), vis = CV.filter(([, v]) => v.expect === "evidence");
body.push(H2("E. Public FATF/Egmont cases"));
body.push(P0(`On the six reconstructed cases, the expected evidence appears in ${V(vis.filter(([, v]) => v.rules_expected.every((r) => v.rules_fired.includes(r))).length, S_CASES + " evidence cases with expected rules", String)} of ${vis.length} schemes visible in trade records, but only ${V(vis.filter(([, v]) => v.alerts > 0).length, S_CASES + " evidence cases with an alert", String)} (the vehicle VAT chain, Box 2.6) crosses the alert threshold: a five-fold under-priced phone is only about ${V(Math.abs(Math.log(36 / 180) / (1.4826 * REFT["851713"])), "computed: abs(ln(36/180)) / (1.4826 × log_mad of HS 851713 in kashf/reference.py); price 36 from scripts/make_cases.py", (x) => x.toFixed(1))} robust SD below the illustrative reference, and invoices without shipping documents alone carry a low calibrated weight. The two payment-side schemes (Black Market Peso Exchange, Box 2.9; third-party payments to partners with one owner, Box 4.7) leave no trace in trade records and produce nothing, as expected.`));
body.push(H2("F. Analyst view"));
body.push(P0(`The dashboard lists alerts by score (Fig. ${FIGN + 1}); opening one shows each signal's evidence and calibrated weight (Fig. ${FIGN + 2}) and the counterparty network around the seller (Fig. ${FIGN + 3}). The screenshots use synthetic invoices priced around real Comtrade medians.`));
body.push(...FIG("alerts", "paper/figures/screen_alerts.png", "Alert list (synthetic invoices): score, invoice, goods and the main reason in words."));
body.push(...FIG("evidence", "paper/figures/screen_evidence.png", "Evidence panel for one alert (synthetic): each signal states the fact behind it and its calibrated weight."));
body.push(...FIG("network", "paper/figures/screen_network.png", "Counterparty network around the seller (synthetic): trade links, alerted trades and shared identifiers."));

body.push(H1("VIII. Discussion"));
SEC = "VIII. Discussion";
body.push(P0("The real data change the story told by the synthetic benchmark. Mirror statistics are noisy enough that only large distortions stand out, and their largest gaps have well-known benign causes, above all re-exports. Their value is as a public, coarse screen that points at products and corridors; evidence about a specific trade has to come from that trader's documents, which is what the invoice layer reads. Calibration helps, but the shift results show that it must be refit on each new population, ideally on cases analysts have already closed. The external checks temper the synthetic numbers: on data Kashf did not generate, its rules are precise but narrow, and simple published methods win where the signal is a single large quantity (a unit value, a dollar gap)."));

body.push(H2("Re-exports are the main confounder"));
body.push(P0("The single largest pattern in the real data is not fraud but bookkeeping: a hub that re-exports goods records itself as the exporter, while the destination often records the producing country. Any mirror screen for the UAE that does not separate X from RX, or that uses one threshold for all products, will mostly rediscover this. Reporting both X + RX and X-only gaps, and comparing each pair with its own product's peers, is the minimum needed before a gap says anything about a flow."));
body.push(H2("What an analyst gets"));
body.push(P0("A macro flag is a pointer: a country × product × year where the two sides disagree more than that product usually does, with the size of the disagreement in plain numbers and a list of innocent reasons. The invoice layer then answers a different question, whether one trader's documents are internally consistent and priced like the market. Both layers end in an analyst decision; Kashf never files or blocks anything."));
body.push(H1("IX. Limitations and Ethics"));
SEC = "IX. Limitations";
body.push(B("**No real labels.** Real-data detection rates come from injected distortions; precision is a lower bound."));
body.push(B("**Post-hoc baseline.** The peer baseline was chosen after seeing the real data; the pre-set thresholds and their failure are reported."));
body.push(B("**Assumptions.** A flat 10% CIF/FOB margin; Comtrade-estimated quantities excluded, which lowers coverage."));
body.push(B("**Synthetic invoices.** The generator and detectors share an author, so typologies match what the detectors look for; the alternative mechanics test is a stress test, not independent data."));
body.push(B("**External checks are small and indirect.** The published flows are gold-only, Africa-only and not laundering labels; AMLworld tests only the cycle rule; the public cases are reconstructions."));
body.push(B("**Kashf loses to simple baselines on some tests:** the IQR filter on injected unit-value distortions, the GFI-style gap on ranking published gold flows, and, as shipped, the cycle rule on AMLworld, which needed adapting to transfer data."));
body.push(B("**Explanations not user-tested.** Faithfulness is measured (Section VII-B) but usefulness is not: no analyst study has measured whether the evidence speeds up or improves decisions. A protocol is in docs/user_study.md; its results table is empty."));
body.push(B("**Aggregates.** Annual HS6 totals mix many traders; a laundering scheme smaller than reporting noise in its aggregate is invisible to the macro layer by construction."));
body.push(B(`**Coverage.** ${st.hs6} products and ${st.years[0]}–${st.years[st.years.length-1]} only; results may differ for other goods and for partners that report late or suppress detail.`));
body.push(P0("No customer, client or employer data was used. Macro flags concern country × product aggregates and never name a company. Kashf drafts evidence and benign explanations; decisions and any reports stay with human analysts."));

body.push(H1("X. Future Work"));
body.push(P0("Evaluation on analyst-labelled cases from a real compliance engagement; the user study in docs/user_study.md; a cycle rule that tolerates currency conversion and changing amounts; combining Kashf's peer-relative scores with dollar size when ranking macro flags; bilateral CIF/FOB estimates instead of a flat margin; monthly Comtrade data to reduce timing gaps."));

body.push(H1("XI. Reproducibility"));
body.push(P0(`Code, configuration, data card and results: https://github.com/lilanayele/kashf (results generated at commit ${COMMIT}). With a Comtrade key in .env (never committed):`));
for (const cmd of ["pip install -r requirements.txt && pip install --no-deps -e .", "bash scripts/run_real.sh", "python -m kashf.evaluate --seeds 5 && python -m kashf.evaluate --robustness"])
  body.push(new Paragraph({ spacing: { after: 30 }, children: [new TextRun({ text: cmd, font: "Courier New", size: 15 })] }));

body.push(H1("References"));
const REFS = [
  "FATF and Egmont Group, “Trade-Based Money Laundering: Trends and Developments,” FATF, Paris, Dec. 2020. https://www.fatf-gafi.org/en/publications/Methodsandtrends/Trade-based-money-laundering-trends-and-developments.html",
  "FATF and Egmont Group, “Trade-Based Money Laundering: Risk Indicators,” FATF, Paris, Mar. 2021. https://www.fatf-gafi.org/en/publications/Methodsandtrends/Trade-based-money-laundering-indicators.html",
  "J. S. Zdanowicz, “Trade-based money laundering and terrorist financing,” Rev. Law Econ., vol. 5, no. 2, pp. 855–878, 2009, doi: 10.2202/1555-5879.1419.",
  "Global Financial Integrity, “Trade-Related Illicit Financial Flows in 135 Developing Countries: 2008–2017,” Washington, DC, Mar. 2020. https://gfintegrity.org/report/trade-related-illicit-financial-flows-in-135-developing-countries-2008-2017/",
  "United Nations Statistics Division, “UN Comtrade database and API (data/v1).” https://comtradeapi.un.org/ (accessed Nov. 2026).",
  "F. T. Liu, K. M. Ting, and Z.-H. Zhou, “Isolation forest,” in Proc. 8th IEEE Int. Conf. Data Mining (ICDM), 2008, pp. 413–422, doi: 10.1109/ICDM.2008.17.",
  "S. M. Lundberg and S.-I. Lee, “A unified approach to interpreting model predictions,” in Adv. Neural Inf. Process. Syst. 30 (NIPS 2017), pp. 4765–4774. arXiv:1705.07874.",
  "FATF, “High-Risk Jurisdictions subject to a Call for Action” and “Jurisdictions under Increased Monitoring,” 30 Oct. 2026. https://www.fatf-gafi.org/en/publications/High-risk-and-other-monitored-jurisdictions/increased-monitoring-october-2026.html",
  "UAE National AML/CFT Committee, “Money Laundering and Terrorist Financing Risk Assessment Report, United Arab Emirates (Updated Public Version),” approved 2025 (ADGM FSRA Notice No. 37 of 2025). https://assets.adgm.com/download/assets/Updated+UAE+National+ML-TF+Risk+Assessment+Report+-+Public+Version.pdf/a4d0340a210211f085342e4ad712ca04",
  "E. Altman et al., “Realistic synthetic financial transactions for anti-money laundering models,” in Adv. Neural Inf. Process. Syst. 36 (NeurIPS 2023), Datasets and Benchmarks Track, pp. 29851–29874. arXiv:2306.16424.",
  "UN Comtrade, “What constitutes ‘transformed’ or ‘substantially different’ data for re-dissemination under the UN Comtrade license?” UN Comtrade Help Center, https://comtradewiki.azurewebsites.net/?p=893 (accessed Nov. 2026).",
,
  "M. E. de Boyrie, S. J. Pak, and J. S. Zdanowicz, “Money laundering and income tax evasion: the determination of optimal audits and inspections to detect abnormal prices in international trade,” J. Financial Crime, vol. 12, no. 2, pp. 123–130, 2005, doi: 10.1108/13590790510624972.",
  "Global Financial Integrity, “Trade misinvoicing: mirror analysis methodology.” https://gfintegrity.org/research/trade-misinvoicing-mirror-analysis/ (accessed Nov. 2026).",
  "M. Ummel and Y. Schulz, “On the trail of African gold: quantifying production and trade to combat illicit flows,” SWISSAID, Bern, May 2024. https://www.swissaid.ch/wp-content/uploads/2026/05/swissaid-on-the-trail-of-african-gold-web-ok.pdf",
  "SWISSAID, “United Arab Emirates: more than ever a hub for conflict gold,” press release, 4 Nov. 2025. https://www.swissaid.ch/en/media/united-arab-emirates-more-than-ever-a-hub-for-conflict-gold/",
  "Reuters, “Ghana lost $11 billion to gold smuggling, links to UAE, report finds,” 16 Jun. 2025 (reporting a SWISSAID study). https://www.kitco.com/news/off-the-wire/2025-06-16/ghana-lost-11-billion-gold-smuggling-links-uae-report-finds",
  "E. Altman et al., “IBM Transactions for Anti Money Laundering (AML),” Kaggle dataset, HI-Small files. https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml"];
REFS.forEach((t) => body.push(new Paragraph({ numbering: { reference: "refs", level: 0 }, spacing: { after: 30 },
  children: [new TextRun({ text: t, font: FONT, size: 15 })] })));

// ---------- sections: one-column front matter, two-column body, one-column spans for wide figures
function sections() {
  const page = { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1080, left: 1008, right: 1008 } };
  const footers = { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
    children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16 })] })] }) };
  const out = [{ properties: { page }, footers, children: [...front, abstract, keywords] }];
  let cur = [];
  const flush = () => { if (cur.length) out.push({ properties: { type: SectionType.CONTINUOUS, column: { count: 2, space: 360 }, page },
    footers, children: cur }); cur = []; };
  for (const item of body) {
    if (item && item.SPAN) { flush(); out.push({ properties: { type: SectionType.CONTINUOUS, column: { count: 1 }, page }, footers, children: item.SPAN }); }
    else cur.push(item);
  }
  flush();
  return out;
}

// ---------- document
const doc = new Document({
  creator: "Lilan Getachew", title: "Kashf: two-layer explainable TBML screening",
  styles: { default: { document: { run: { font: FONT, size: BODY } } } },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 240, hanging: 160 } } } }] },
    { reference: "refs", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "[%1]", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 360, hanging: 360 } } } }] }] },
  sections: sections(),
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(path.join(ROOT, "paper/Kashf_Paper_v2.docx"), buf);
  const L = ["# Number-to-source list (paper/Kashf_Paper_v2)", "",
    `Generated by paper/build_paper_v2.js at commit ${COMMIT}. Every number in the paper text and tables is listed with the file and key it was read from.`, "",
    "| Section | Value | Source |", "|---|---|---|", ...NUMS.map((n) => `| ${n.section} | ${n.text} | \`${n.source}\` |`)];
  fs.writeFileSync(path.join(ROOT, "paper/NUMBERS.md"), L.join("\n") + "\n");
  console.log("wrote paper/Kashf_Paper_v2.docx and paper/NUMBERS.md:", NUMS.length, "numbers,", FIGN, "figures,", TABN, "tables");
});
