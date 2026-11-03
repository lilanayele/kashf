// Builds paper/Kashf_Research_Paper.docx from the evaluation results.
// node paper/build_paper.js   (run from the repo root)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, AlignmentType,
  WidthType, ShadingType, BorderStyle, LevelFormat, Footer, PageNumber, HeadingLevel,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const S = JSON.parse(fs.readFileSync(path.join(ROOT, "results/summary.json"), "utf8"));
const C = S.configs;
const FONT = "Times New Roman";
const W = 9026; // A4 text width in DXA with 1" margins

const f3 = (x) => x.mean.toFixed(3);
const pct = (x, d = 2) => (100 * x.mean).toFixed(d) + "%";
const sd3 = (x) => `${x.mean.toFixed(3)} ± ${x.sd.toFixed(3)}`;

// ---------- text helpers
function runs(text, base = {}) {
  // **bold**, *italic*
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, font: FONT, ...base }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, font: FONT, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, ...base }));
  return out;
}
const P = (text, opts = {}) => new Paragraph({ children: runs(text), alignment: AlignmentType.JUSTIFIED,
  spacing: { after: 120, line: 276 }, ...opts });
const H1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text, font: FONT })] });
const H2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text, font: FONT })] });
const B = (text) => new Paragraph({ children: runs(text), numbering: { reference: "bullets", level: 0 },
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 276 } });
const N = (text, ref = "nums") => new Paragraph({ children: runs(text), numbering: { reference: ref, level: 0 },
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 276 } });
const EQ = (text, num) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 80, after: 120 },
  children: [new TextRun({ text, italics: true, font: "Cambria Math", size: 22 }),
             new TextRun({ text: `        (${num})`, font: FONT, size: 22 })] });

function FIG(file, wpx, caption, maxW = 560) {
  const full = path.join(ROOT, file);
  const { w, h } = pngSize(full);
  const width = Math.min(maxW, wpx);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: fs.readFileSync(full),
        transformation: { width, height: Math.round(width * h / w) } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: runs(caption, { size: 18 }) }),
  ];
}
function pngSize(f) {
  const b = fs.readFileSync(f);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
const borders = { top: border, bottom: border, left: border, right: border };
function TABLE(caption, header, rows, widths, boldRow = -1) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (t, w, opts = {}) => new TableCell({
    borders, width: { size: w, type: WidthType.DXA }, margins: { top: 50, bottom: 50, left: 80, right: 80 },
    shading: opts.head ? { fill: "E8ECF1", type: ShadingType.CLEAR, color: "auto" } : undefined,
    children: [new Paragraph({ alignment: opts.left ? AlignmentType.LEFT : AlignmentType.CENTER,
      children: [new TextRun({ text: String(t), font: FONT, size: 18, bold: !!opts.bold || !!opts.head })] })],
  });
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 160, after: 80 }, keepNext: true,
      children: runs(caption, { size: 18 }) }),
    new Table({
      width: { size: total, type: WidthType.DXA }, columnWidths: widths,
      rows: [
        new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, widths[i], { head: true, left: i === 0 })) }),
        ...rows.map((r, ri) => new TableRow({ children: r.map((c, i) => cell(c, widths[i], { left: i === 0, bold: ri === boldRow })) })),
      ],
    }),
    new Paragraph({ spacing: { after: 160 }, children: [] }),
  ];
}

// ---------- numbers
const full = C.kashf_full, heur = C.kashf_heuristic;
const TYP = ["over_invoicing", "under_invoicing", "phantom_shipment", "multiple_invoicing", "misdescription", "circular_trading", "shell_cluster"];
const TYPN = { over_invoicing: "Over-inv.", under_invoicing: "Under-inv.", phantom_shipment: "Phantom", multiple_invoicing: "Multiple inv.",
  misdescription: "Misdescr.", circular_trading: "Circular", shell_cluster: "Shell cluster" };
const NAME = { kashf_full: "Kashf (calibrated)", kashf_heuristic: "Kashf (hand-set weights)", minus_price: "– price detector",
  minus_route: "– route detector", minus_documents: "– document detector", minus_graph: "– graph detector",
  price_only: "Price benchmark only", checklist: "Manual-review checklist", isolation_forest: "Isolation forest" };
const rec = (c, t) => C[c].recall_by_typology[t].mean.toFixed(2);
const curve = Object.fromEntries(S.mispricing_recall.map((r) => [r.bin, r]));
const cal = S.calibration;
const counts = S.counts;
const meanCount = (k) => (counts.reduce((a, c) => a + c[k], 0) / counts.length);
const pos = meanCount("laundering");

// ---------- content
const children = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 },
    children: [new TextRun({ text: "Kashf: Explainable Detection of Trade-Based Money Laundering in UAE Trade Records Using Calibrated Multi-Detector Evidence",
      font: FONT, size: 34, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
    children: [new TextRun({ text: "Lilan Getachew", font: FONT, size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
    children: [new TextRun({ text: "Department of Computer Science and Engineering, Amity University Dubai, United Arab Emirates", font: FONT, size: 20, italics: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 280 },
    children: [new TextRun({ text: "getachewlilan@gmail.com", font: FONT, size: 20 })] }),

  new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 120, line: 260 }, children: [
    new TextRun({ text: "Abstract — ", bold: true, italics: true, font: FONT, size: 20 }),
    new TextRun({ font: FONT, size: 20, text:
      `Trade-based money laundering (TBML) hides illicit value inside ordinary trade through mispriced, misdescribed, duplicated or fictitious shipments, and is hard to detect because each transaction resembles legitimate business. ` +
      `We present Kashf, an explainable system that screens a trading company's invoices, transport documents and counterparties for TBML red flags. ` +
      `Kashf combines four detectors (unit-price benchmarking with a robust z-score, document consistency, a counterparty identifier graph with circular-trade search, and route risk), calibrates each rule's weight to its precision on labelled cases, and combines signals with a noisy-OR score in which every alert carries human-readable evidence. ` +
      `Because labelled TBML data is not public, we also contribute a synthetic UAE trade benchmark with seven planted typologies and deliberately noisy legitimate trade. ` +
      `On five held-out benchmark instances of 20,000 invoices each, Kashf reaches F1 = ${f3(full.f1)} (precision ${f3(full.precision)}, recall ${f3(full.recall)}) at a false-alarm rate of ${pct(full.far)}, against ${f3(C.price_only.f1)} for price benchmarking alone, ${f3(C.isolation_forest.f1)} for an isolation forest and ${f3(C.checklist.f1)} for a rule checklist. ` +
      `Calibration raises precision from ${f3(heur.precision)} to ${f3(full.precision)}. Mild mispricing (under 2× the benchmark) is not detected. Results are on synthetic data and indicate feasibility, not field performance.` })] }),
  new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 240 }, children: [
    new TextRun({ text: "Index Terms — ", bold: true, italics: true, font: FONT, size: 20 }),
    new TextRun({ text: "anti-money laundering, trade-based money laundering, anomaly detection, graph analytics, explainable AI, calibration, synthetic data, United Arab Emirates.", font: FONT, size: 20, italics: true })] }),

  H1("I. Introduction"),
  P("Trade-based money laundering uses the movement of goods, or the paperwork that claims to move them, to transfer value across borders. A seller who invoices goods at several times their market price receives more money than the goods are worth; a buyer who pays for a shipment that never sails moves money with nothing in return. The joint FATF and Egmont Group report describes criminals exploiting trade to move money rather than goods, and stresses that TBML is hard to recognise because of the speed of trade, the variety of goods and the number of parties involved [1]."),
  P("The problem is acute for the United Arab Emirates, a major re-export hub. A published summary of the UAE's 2024 National Risk Assessment lists the misuse of trade transactions through front and shell companies, and the misuse of free trade zones, among the country's money-laundering concerns [5]. Trade surveillance products exist, but they are aimed at banks with trade-finance operations. Small and mid-size traders, and the compliance consultancies that serve them, largely review invoices manually against red-flag checklists such as the FATF and Egmont risk indicators [2]."),
  P("Such checklists are easy to explain but produce many false alarms, while statistical methods such as price filtering [3] address only one typology at a time. Machine-learning approaches to anti-money laundering mostly target bank transfers [4] and rarely explain individual alerts in terms an analyst can verify. This paper asks whether a small set of transparent detectors, combined with a calibrated score, can cover several TBML typologies at once at a false-alarm rate a compliance team can absorb, while keeping every alert explainable."),
  P("**Contributions.**"),
  N("**Kashf**, an open-source system that combines four TBML detectors and attaches the evidence for each alert, with a review dashboard and draft case summaries for analysts."),
  N("**Per-rule calibration** of signal weights to their smoothed precision on labelled cases, with price signals calibrated by z-score band, which makes the score both better and interpretable."),
  N("**A synthetic UAE trade benchmark** with seven planted TBML typologies and realistic sources of false alarms (premium goods, free-zone business centres, related-party groups, missing paperwork), released with its generator."),
  N("**An evaluation** against three baselines, four ablations and a calibration study on held-out data, including where detection fails."),

  H1("II. Background and Related Work"),
  H2("A. TBML typologies"),
  P("FATF and the Egmont Group catalogue TBML techniques through case studies and risk indicators [1], [2]. The typologies used in this work follow those sources: over- and under-invoicing of goods; phantom shipments, where documents describe a shipment that never took place; multiple invoicing of the same goods; misrepresentation of the quantity, quality or type of goods; and the use of related or shell companies, including circular trading in which goods and money loop back to their origin."),
  H2("B. Price-based detection"),
  P("Zdanowicz showed that abnormally priced trade can be identified statistically by comparing declared prices with the distribution of prices for the same product, and used this to estimate value moved through U.S. trade [3]. Price filters are effective when manipulation is large relative to natural price dispersion, but they say nothing about paperwork, routing or ownership, and they operate on national trade statistics rather than on one company's records."),
  H2("C. Machine learning for AML"),
  P("Learning-based AML research has largely focused on account and transfer data. Altman et al. released realistic synthetic financial transaction datasets with labelled laundering patterns to train and compare models, including graph neural networks [4]. Unsupervised anomaly detectors such as the isolation forest [7] are a common starting point when labels are scarce. These approaches do not model trade documents, prices or shipments, and an anomaly score alone does not tell an analyst why a transaction is suspicious."),
  H2("D. Commercial screening"),
  P("Commercial AML tools in the region concentrate on sanctions and name screening, including the difficult problem of matching Arabic names across transliterations [8], [9]. Screening answers who a counterparty is, not whether a given trade is plausible; it is complementary to the transaction-level checks proposed here."),
  H2("E. Gap"),
  P("We found no open system that combines price benchmarking, document consistency, routing and counterparty-network analysis at the level of a single trader's records, with alerts that carry verifiable evidence, evaluated against labelled TBML typologies. Kashf targets that gap."),

  H1("III. Problem Formulation"),
  P("A trader's records consist of a set of companies E, each with identifiers (director, phone, address, bank account); a set of invoices I, each with seller, buyer, date, HS product code, quantity, unit price, declared weight and route; transport documents D (bills of lading or air waybills) referenced by invoices; and packing lists. A reference table gives, for each HS code, a median unit value, its dispersion and a typical weight per unit."),
  P("The task is to assign each invoice i a risk score s(i) in [0, 1] and an evidence set ε(i) of human-readable statements, such that invoices with s(i) ≥ τ are reviewed by an analyst. The goal is high recall of laundering invoices at a low false-alarm rate, with ε(i) sufficient for the analyst to verify the alert without rerunning the system."),

  H1("IV. The Kashf System"),
  ...FIG("docs/figures/architecture.png", 560, "**Fig. 1.** Kashf architecture. Records are normalised once, checked by four detectors in parallel, and scored; the analyst sees each alert with its evidence and decides on any report."),
  H2("A. Price benchmark"),
  P("For invoice i with declared unit price p and HS code h, Kashf computes a robust z-score of the log price against the reference median m(h) and the median absolute deviation of log reference prices, MAD(h):"),
  EQ("z(i) = ( ln p − ln m(h) ) / ( 1.4826 · MAD(h) )", 1),
  P("The constant 1.4826 makes the MAD a consistent estimator of the standard deviation under normality. Lines with |z| ≥ 2 raise an over- or under-priced signal whose evidence states the declared price, the benchmark, their ratio and z. Using logs and medians keeps a few extreme reference values from distorting the benchmark."),
  H2("B. Document consistency"),
  P("The document detector compares each invoice with its transport document and packing list. It raises signals for: no matching bill of lading or air waybill; a departure date more than 120 days after or 30 days before the invoice; an unidentified vessel; quantity differences above 3% and gross-weight differences above 15%; one transport document cited by more than one invoice (multiple invoicing); and a declared weight per unit more than four times above or below the typical weight for the HS code, which indicates misdescribed goods."),
  H2("C. Counterparty graph"),
  P("Kashf builds an undirected graph whose nodes are companies and whose edges join companies sharing a director, phone number, address or bank account. Identifiers shared by six or more companies are treated as hubs and ignored, because free-zone business centres legitimately host many unrelated companies at one address. An invoice whose seller and buyer are adjacent in this graph raises a linked-parties signal naming the shared identifier; parties in the same connected component raise a weaker linked-cluster signal."),
  P("Circular trading is found on the directed trade graph. For each HS code, a bounded depth-first search follows invoices from seller to buyer, allowing a next hop only if it starts from the previous buyer within 60 days and carries a quantity within 10% of the previous hop. A path of three to five hops that returns to the first seller flags every invoice on the loop. The quantity constraint separates repeated movement of the same goods from coincidental chains of unrelated trade."),
  H2("D. Route check"),
  P("Routes are recorded as ordered country codes. The route detector raises signals when a party or transit country is on a configurable high-risk list, when a route passes through the same country twice, and when a shipment has four or more legs."),
  H2("E. Calibrated scoring"),
  P("Hand-set signal weights encode the designer's guesses. Kashf instead calibrates each rule r to its Laplace-smoothed precision on a labelled tuning set, where TP(r) is the number of laundering invoices on which r fired and F(r) the number of invoices on which it fired:"),
  EQ("w(r) = ( TP(r) + 1 ) / ( F(r) + 2 )", 2),
  P("Price signals are calibrated separately for |z| bands [2, 3), [3, 4), [4, 5), [5, 7) and ≥ 7, because a price two deviations from the benchmark is weak evidence while one eight deviations away is strong. Signals for an invoice are combined with a noisy-OR, counting the strongest signal of each rule once:"),
  EQ("s(i) = 1 − ∏ r∈R(i) ( 1 − w(r) )", 3),
  P("An invoice is an alert when s(i) ≥ τ, with τ chosen on the tuning set. Calibration gives the weights a direct reading for analysts: a weight of 0.86 means signals of that kind were laundering in 86% of tuning cases. The noisy-OR assumes signals are independent, which overstates the score when correlated signals fire together; Section VIII returns to this."),
  H2("F. Analyst interface"),
  P("A FastAPI service exposes alerts, evidence, company risk and a counterparty-network view to a web dashboard (Fig. 2), and generates a draft case summary for each alert listing the transaction, the red flags with their evidence, and suggested verification steps. The summary is built only from detector evidence and ends by leaving the decision to escalate, and to file a suspicious transaction report, with the analyst and money-laundering reporting officer."),
  ...FIG("docs/dashboard.png", 560, "**Fig. 2.** Kashf review dashboard showing a shell-cluster alert: two free-zone companies trading gold share a director, and the network view shows five companies linked by that director."),

  H1("V. Synthetic Benchmark"),
  P("Labelled TBML cases are confidential and no public benchmark exists for trade documents, so we built a generator of synthetic UAE trade. Each instance contains about 500 companies (UAE mainland, UAE free zone, and foreign counterparties in 15 partner countries and three illustrative high-risk jurisdictions) and 20,000 invoices over one year, with bills of lading or air waybills and packing lists. Clean trade draws unit prices from a log-normal distribution around the reference median for each of 20 HS codes typical of UAE re-export trade."),
  P("Legitimate trade is deliberately noisy, so that every detector faces realistic false alarms: 3% of clean invoices are premium-priced (1.4–2.6× the benchmark) and 2% are clearance-priced (0.45–0.75×); 0.5% have no transport document on file and 0.5% are short shipments; 60% of free-zone companies sit in one of five shared business-centre addresses; five disclosed related-party groups trade with each other; and some legitimate counterparties are in high-risk jurisdictions. Table I lists the planted typologies."),
  ...TABLE("**TABLE I.** Planted TBML typologies (per 20,000-invoice instance)",
    ["Typology", "How it is planted", "Invoices"],
    [["Over-invoicing", "Unit price × 1.8–8 of a normally drawn price", "120"],
     ["Under-invoicing", "Unit price × 0.12–0.55", "120"],
     ["Phantom shipment", "No transport document, an impossible departure date with no vessel, or a document weight 5–30% of the invoice", "120"],
     ["Multiple invoicing", "Same goods and transport document invoiced to a second buyer", "120"],
     ["Misdescription", "Electronics declared as plastics (per kg) or T-shirts", "120"],
     ["Circular trading", "Goods resold around a ring of 3–4 companies, 2–3 times", `${meanCount("circular_trading").toFixed(0)} (avg.)`],
     ["Shell cluster", "3–5 new companies sharing a director, phone or address, trading among themselves", `${meanCount("shell_cluster").toFixed(0)} (avg.)`]],
    [1900, 5626, 1500]),
  P(`Across the held-out instances, laundering invoices average ${pos.toFixed(0)} of 20,000 (${(100 * pos / 20000).toFixed(1)}%). Ground-truth labels are stored in a separate table that detectors never read, and invoice order is shuffled.`),
  P("The reference price table used in all experiments is illustrative: plausible order-of-magnitude unit values chosen for the prototype, not UN Comtrade data. The system includes a loader that replaces it with Comtrade unit values (free accounts allow 500 API calls a day [6]); this could not be run in the experimental environment, which had no access to the Comtrade API."),

  H1("VI. Experimental Setup"),
  P("Instance 0 is the tuning set: calibration weights and each configuration's alert threshold τ (chosen to maximise F1) are fitted there and then frozen. Instances 1–5 are held-out test sets generated with different random seeds; we report means and standard deviations over them."),
  P("**Configurations.** Kashf with calibrated weights (the full system); Kashf with hand-set weights; four ablations each removing one detector; price benchmark only, representing classical price-filter analysis [3]; a manual-review checklist that alerts when price is outside 0.5–2× the benchmark, the transport document is missing, a party is in a high-risk jurisdiction, or quantities differ by more than 5%; and an isolation forest [7] (300 trees) on eight per-invoice features (log price ratio, log unit-weight ratio, missing document, quantity and weight gaps, legs, high-risk flag, log value)."),
  P("**Metrics.** Precision, recall and F1 of laundering invoices at τ; false-alarm rate (share of clean invoices alerted); alerts per 1,000 invoices as a proxy for analyst workload; average precision, which does not depend on τ; recall per typology; and evidence attribution, the share of true alerts whose evidence names the mechanism that was planted."),

  H1("VII. Results"),
  H2("A. Overall performance"),
  ...TABLE("**TABLE II.** Results on held-out instances (mean ± s.d. over 5 × 20,000 invoices)",
    ["Configuration", "Precision", "Recall", "F1", "False alarms", "Alerts/1k", "Avg. prec."],
    ["kashf_full", "kashf_heuristic", "minus_price", "minus_route", "minus_documents", "minus_graph", "price_only", "isolation_forest", "checklist"]
      .map((k) => [NAME[k], f3(C[k].precision), f3(C[k].recall), sd3(C[k].f1), pct(C[k].far), C[k].alerts_per_1000.mean.toFixed(1), f3(C[k].avg_precision)]),
    [2400, 950, 950, 1350, 1100, 1000, 1276], 0),
  P(`Table II shows that the full system reaches F1 = ${f3(full.f1)} with precision ${f3(full.precision)} and a false-alarm rate of ${pct(full.far)}, about ${full.alerts_per_1000.mean.toFixed(0)} alerts per 1,000 invoices. Price benchmarking alone reaches F1 = ${f3(C.price_only.f1)}, and the isolation forest and checklist both stay below 0.2. The checklist finds ${f3(C.checklist.recall)} of laundering invoices but alerts on ${pct(C.checklist.far, 1)} of clean ones, about ${C.checklist.alerts_per_1000.mean.toFixed(0)} alerts per 1,000 invoices, mostly false. Variation across instances is small (F1 s.d. ${full.f1.sd.toFixed(3)}).`),
  ...FIG("docs/figures/f1_by_config.png", 540, "**Fig. 3.** F1 on held-out instances by configuration. Error bars show one standard deviation over five instances."),
  H2("B. Ablation"),
  P(`Removing the document detector lowers F1 to ${f3(C.minus_documents.f1)} and removing the graph detector to ${f3(C.minus_graph.f1)}; without the price detector F1 falls to ${f3(C.minus_price.f1)}. Each covers typologies no other detector catches: without the document detector, recall of phantom shipments and multiple invoicing drops to ${rec("minus_documents", "phantom_shipment")} and ${rec("minus_documents", "multiple_invoicing")}; without the graph detector, circular trading and shell clusters drop to ${rec("minus_graph", "circular_trading")} and ${rec("minus_graph", "shell_cluster")}; without the price detector, over- and under-invoicing drop to ${rec("minus_price", "over_invoicing")}. Removing the route detector leaves F1 unchanged at ${f3(C.minus_route.f1)}: on this benchmark, no typology is planted through routing, and the high-risk-party rule calibrates to a weight of only ${cal.high_risk_party.toFixed(2)} because legitimate trade with those jurisdictions is common. We keep it as context for analysts rather than as evidence.`),
  ...TABLE("**TABLE III.** Recall by typology on held-out instances",
    ["Configuration", ...TYP.map((t) => TYPN[t])],
    ["kashf_full", "kashf_heuristic", "price_only", "isolation_forest", "checklist"].map((k) => [NAME[k], ...TYP.map((t) => rec(k, t))]),
    [2200, 975, 975, 975, 975, 975, 975, 976], 0),
  ...FIG("docs/figures/recall_by_typology.png", 540, "**Fig. 4.** Recall by typology for the full system and the three baselines."),
  H2("C. Calibration"),
  P(`Calibration raises precision from ${f3(heur.precision)} to ${f3(full.precision)}, halves the false-alarm rate from ${pct(heur.far)} to ${pct(full.far)}, and increases average precision from ${f3(heur.avg_precision)} to ${f3(full.avg_precision)}, at a small cost in recall (${f3(heur.recall)} to ${f3(full.recall)}). The fitted weights explain why. A missing transport document is laundering in only ${(100 * cal.no_transport_doc).toFixed(0)}% of tuning cases, because legitimate paperwork also goes missing, so calibration correctly demotes it. Shared transport documents (${cal.doc_reused.toFixed(2)}), impossible dates (${cal.implausible_dates.toFixed(2)}) and implausible unit weights (${cal.implausible_unit_weight.toFixed(2)}) are near-certain. Over-priced signals rise from ${cal["over_priced|z2-3"].toFixed(2)} for |z| in [2, 3) to ${cal["over_priced|z7-inf"].toFixed(2)} for |z| ≥ 7.`),
  H2("D. Where detection fails"),
  P(`Over- and under-invoicing are the hardest typologies (recall ${rec("kashf_full", "over_invoicing")} and ${rec("kashf_full", "under_invoicing")}). Fig. 5 shows why: Kashf catches none of the mispriced invoices within 2× of the benchmark, ${curve["3-4x"].recall.toFixed(2)} of those at 3–4×, ${curve["6-10x"].recall.toFixed(2)} at 6–10× and ${curve[">10x"].recall.toFixed(2)} beyond 10×. Moderate manipulation overlaps with legitimate premium and clearance pricing, so no price threshold separates them without raising many false alarms; the checklist's higher recall on these typologies is bought with its ${pct(C.checklist.far, 1)} false-alarm rate. Phantom shipments reach recall ${rec("kashf_full", "phantom_shipment")}: impossible dates and weight discrepancies are caught, but a phantom with simply no document is indistinguishable from legitimate missing paperwork at the invoice level.`),
  ...FIG("docs/figures/mispricing_recall.png", 420, "**Fig. 5.** Recall of over- and under-invoicing against the size of the price distortion relative to the benchmark (pooled over held-out instances)."),
  H2("E. Explanations"),
  P(`For every configuration that uses Kashf's detectors, all true alerts carried evidence naming the planted mechanism (evidence attribution ${f3(full.evidence_attribution)}). This is partly by construction, since each detector was designed for known typologies, so it shows that explanations are consistent with the cause rather than that they would be on unseen typologies. Fig. 6 compares precision–recall curves on one held-out instance.`),
  ...FIG("docs/figures/pr_curves.png", 340, "**Fig. 6.** Precision–recall curves on held-out instance 1."),

  H1("VIII. Discussion"),
  P(`**Combining evidence is the main gain.** Price benchmarking alone reaches F1 = ${f3(C.price_only.f1)}, and removing any one of the price, document or graph detectors costs 0.11 to 0.18 F1, because each typology leaves traces in different records: prices, documents or ownership. Analysts receive an alert with a reason they can check, rather than an anomaly score.`),
  P("**Moderate mispricing needs context, not a sharper threshold.** Distinguishing a premium product from a 2× over-invoice requires information that invoices do not contain, such as the buyer's history with the same goods, contract terms, or mirror statistics from the importing country. Company-level aggregation, flagging a trader whose prices are persistently high across many invoices, is a natural next step."),
  P("**Threats to validity.** The benchmark was designed by the same author as the detectors, so the planted typologies match what the detectors look for; performance on real trade, and on typologies not anticipated here, is unknown. The reference prices are illustrative. Thresholds and calibration were fitted on data from the same generator as the test instances, which favours all tuned configurations equally but overstates how well tuning transfers to a new population. The noisy-OR independence assumption overstates scores when correlated rules fire together; a learned combiner such as logistic regression over rule indicators would address this once real labels exist."),
  P("**Deployment.** The system runs on a laptop, needs no client data to build, and its weights can be recalibrated on cases an analyst has already closed. That makes it suitable for a consultancy to pilot with clients' own records under appropriate data agreements, which is the necessary next test."),

  H1("IX. Ethics"),
  P("No real customer, client or employer data was used. All companies, people and transactions in the benchmark are synthetic. Kashf is designed to support, not replace, human judgement: it drafts evidence and next steps, and it does not file reports or label any person or company a criminal. False alarms carry real costs for legitimate traders, which is why the false-alarm rate is reported alongside recall and why every alert exposes its reasoning to review."),

  H1("X. Conclusion and Future Work"),
  P(`Kashf shows that four transparent detectors with calibrated weights can cover seven TBML typologies at once on a synthetic UAE benchmark, reaching F1 = ${f3(full.f1)} at a ${pct(full.far)} false-alarm rate with an explanation for every alert, compared with ${f3(C.price_only.f1)} for price benchmarking alone. Future work will replace the illustrative reference prices with UN Comtrade unit values, evaluate on analyst-labelled cases from a real compliance engagement, add company-level and graph-neural-network models, extend document intake to Arabic invoices with OCR, and add route-based typologies to test the route detector properly. The code, generator, benchmark and results are released openly.`),

  H1("References"),
  ...[
    "FATF and Egmont Group, “Trade-Based Money Laundering: Trends and Developments,” FATF, Paris, Dec. 2020. [Online]. Available: https://www.fatf-gafi.org/en/publications/Methodsandtrends/Trade-based-money-laundering-trends-and-developments.html",
    "FATF and Egmont Group, “Trade-Based Money Laundering: Risk Indicators,” FATF, Paris, 2021. [Online]. Available: https://www.fatf-gafi.org/en/publications/Methodsandtrends/Trade-based-money-laundering-indicators.html",
    "J. S. Zdanowicz, “Trade-based money laundering and terrorist financing,” Review of Law & Economics, vol. 5, no. 2, 2009.",
    "E. Altman et al., “Realistic synthetic financial transactions for anti-money laundering models,” in Advances in Neural Information Processing Systems 36 (NeurIPS 2023), Datasets and Benchmarks Track, 2023. arXiv:2306.16424.",
    "Crowe UAE, “Understanding money laundering and terrorist financing typologies: insights from the UAE National Risk Assessment 2024,” 2024. [Online]. Available: https://www.crowe.com/ae/news/uae-national-risk-assessment-nra-2024",
    "United Nations Statistics Division, “UN Comtrade: subscription tiers and API access.” [Online]. Available: https://comtradewiki.azurewebsites.net/?p=78",
    "F. T. Liu, K. M. Ting, and Z.-H. Zhou, “Isolation forest,” in Proc. 8th IEEE Int. Conf. Data Mining (ICDM), 2008, pp. 413–422.",
    "AML Watcher, “Arabic name matching in the MENA region.” [Online]. Available: https://amlwatcher.com/press-release/aml-watcher-cracks-the-code-of-arabic-name-matching-in-mena/",
    "NetOwl, “The challenges of Arabic name matching for AML.” [Online]. Available: https://www.netowl.com/the-challenges-of-arabic-name-matching-for-aml/",
  ].map((t) => new Paragraph({ children: [new TextRun({ text: t, font: FONT, size: 18 })],
    numbering: { reference: "refs", level: 0 }, spacing: { after: 60 } })),
];

const doc = new Document({
  creator: "Lilan Getachew",
  title: "Kashf: Explainable Detection of Trade-Based Money Laundering",
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 24, bold: true, allCaps: false },
        paragraph: { spacing: { before: 280, after: 120 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 22, bold: true, italics: true },
        paragraph: { spacing: { before: 180, after: 80 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "nums", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1)", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
    { reference: "refs", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "[%1]", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 500, hanging: 500 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18 })] })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = path.join(ROOT, "paper/Kashf_Research_Paper.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", out);
});
