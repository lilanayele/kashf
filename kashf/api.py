"""Kashf web API and dashboard.

    kashf serve data/demo     ->  http://127.0.0.1:8800
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import networkx as nx
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse

from kashf.config import Settings, load_yaml
from kashf.detectors import link_graph
from kashf.pipeline import DTYPES, TABLES, analyse, load_dir
from kashf.report import entity_case, invoice_case

STATIC = Path(__file__).parent / "static"


MACRO_DIR = Path(__file__).resolve().parent.parent / "results" / "macro"


def create_app(data_dir: str | Path | None = None, macro_dir: str | Path | None = None,
               reference_path: str | Path | None = None) -> FastAPI:
    """data_dir: invoice CSVs to load at start; macro_dir: results of `python -m kashf.macro`;
    reference_path: reference price CSV (e.g. data/reference_comtrade.csv); None = illustrative table."""
    app = FastAPI(title="Kashf", version="0.1.0")
    state: dict = {}
    max_bytes = int(float(load_yaml().get("api", {}).get("max_upload_mb", 10)) * 1024 * 1024)
    from kashf import reference as _reference
    ref = _reference.load(reference_path) if reference_path else None
    state["reference"] = str(reference_path) if reference_path else "illustrative (kashf/reference.py)"

    def load(tables: dict) -> None:
        tables = {k: v for k, v in tables.items() if k != "labels"}   # never expose ground truth
        state["res"] = analyse(tables, ref=ref)
        state["links"], state["hubs"] = link_graph(tables["entities"], Settings.from_yaml())

    if data_dir:
        load(load_dir(data_dir))

    def res():
        if "res" not in state:
            raise HTTPException(404, "No data loaded yet. Upload CSV files first.")
        return state["res"]

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (STATIC / "index.html").read_text(encoding="utf-8")

    @app.get("/static/d3.min.js")
    def d3js():
        return PlainTextResponse((STATIC / "d3.min.js").read_text(encoding="utf-8"), media_type="application/javascript")

    @app.get("/logo.svg")
    def logo():
        return PlainTextResponse((STATIC / "logo.svg").read_text(encoding="utf-8"), media_type="image/svg+xml")

    @app.get("/api/summary")
    def summary():
        r = res()
        a = r.invoices[r.invoices["alert"]]
        by_det = r.signals[r.signals["invoice_no"].isin(a["invoice_no"])].groupby("detector")["invoice_no"].nunique()
        return {"invoices": len(r.invoices), "alerts": len(a), "alert_value_usd": float(a["value_usd"].sum()),
                "total_value_usd": float(r.invoices["value_usd"].sum()),
                "companies_flagged": int((r.entities["alerts"] > 0).sum()),
                "by_detector": {k: int(v) for k, v in by_det.items()}}

    @app.get("/api/alerts")
    def alerts(limit: int = 300, detector: Optional[str] = None, q: Optional[str] = None):
        r = res()
        a = r.invoices[r.invoices["alert"]]
        if detector:
            a = a[a["detectors"].str.contains(detector)]
        if q:
            ql = q.lower()
            a = a[a.apply(lambda x: ql in " ".join(map(str, x.values)).lower(), axis=1)]
        return a.head(limit).to_dict("records")

    @app.get("/api/invoice/{invoice_no}")
    def invoice(invoice_no: str):
        r = res()
        inv = r.tables["invoices"]
        row = inv[inv["invoice_no"] == invoice_no]
        if row.empty:
            raise HTTPException(404, "invoice not found")
        sc = r.invoices[r.invoices["invoice_no"] == invoice_no].iloc[0]
        sig = r.signals[r.signals["invoice_no"] == invoice_no].sort_values("strength", ascending=False)
        ents = r.entities.set_index("entity_id")
        rec = row.iloc[0].where(pd.notna(row.iloc[0]), None).to_dict()
        return {"invoice": rec, "score": float(sc["score"]), "alert": bool(sc["alert"]),
                "seller": ents.loc[rec["seller_id"]][["name", "kind", "country"]].to_dict(),
                "buyer": ents.loc[rec["buyer_id"]][["name", "kind", "country"]].to_dict(),
                "signals": sig.drop(columns=["value"]).to_dict("records")}

    @app.get("/api/case/{case_id}", response_class=PlainTextResponse)
    def case(case_id: str):
        r = res()
        try:
            return invoice_case(r, case_id) if case_id.startswith("INV") else entity_case(r, case_id)
        except KeyError:
            raise HTTPException(404, "not found")

    @app.get("/api/entities")
    def entities(limit: int = 50):
        e = res().entities
        return e[e["alerts"] > 0].head(limit).to_dict("records")

    @app.get("/api/network/{entity_id}")
    def network(entity_id: str, hops: int = 1):
        """Companies within `hops` trades or shared identifiers of entity_id."""
        r = res()
        inv = r.invoices
        g = nx.Graph()
        for x in inv.itertuples(index=False):
            g.add_edge(x.seller_id, x.buyer_id)
        links = state["links"]
        g.add_edges_from(links.edges())
        if entity_id not in g:
            raise HTTPException(404, "entity not found")
        keep = nx.single_source_shortest_path_length(g, entity_id, cutoff=hops)
        keep = list(keep)[:60]
        ents = r.entities.set_index("entity_id")
        nodes = [{"id": n, "name": ents.loc[n, "name"], "country": ents.loc[n, "country"],
                  "alerts": int(ents.loc[n, "alerts"]), "focus": n == entity_id} for n in keep]
        ks = set(keep)
        sub = inv[inv["seller_id"].isin(ks) & inv["buyer_id"].isin(ks)]
        trades = sub.groupby(["seller_id", "buyer_id"]).agg(n=("invoice_no", "count"), alert=("alert", "max"),
                                                             value=("value_usd", "sum")).reset_index()
        edges = [{"source": t.seller_id, "target": t.buyer_id, "kind": "trade", "n": int(t.n),
                  "alert": bool(t.alert), "value": float(t.value)} for t in trades.itertuples()]
        edges += [{"source": a, "target": b, "kind": "shared", "via": d["via"]}
                  for a, b, d in links.edges(data=True) if a in ks and b in ks]
        return {"nodes": nodes, "edges": edges}

    # ---------------------------------------------------------- macro view (real Comtrade mirror data)
    mdir = Path(macro_dir) if macro_dir else MACRO_DIR

    def macro_flags() -> pd.DataFrame:
        if "macro" not in state:
            f = mdir / "flags.csv"
            if not f.exists():
                raise HTTPException(404, "No macro results yet. Run: python -m kashf.comtrade pull && "
                                         "python -m kashf.macro")
            state["macro"] = pd.read_csv(f, dtype={"hs6": str})
        return state["macro"]

    @app.get("/api/macro/options")
    def macro_options():
        m = macro_flags()
        hs = sorted(m["hs6"].unique())
        partners = (m[["partner", "partner_iso"]].drop_duplicates("partner").fillna({"partner_iso": ""})
                    .sort_values("partner_iso"))
        top = m.sort_values("rule_score", ascending=False).iloc[0]
        return {"source": "UN Comtrade (real, annual)", "hs6": hs,
                "top": {"hs6": str(top["hs6"]), "partner": int(top["partner"])},
                "partners": [{"code": int(r.partner), "iso": r.partner_iso} for r in partners.itertuples()],
                "pairs": len(m), "flagged": int(m["rule_flag"].sum())}

    @app.get("/api/macro")
    def macro_series(hs6: str, partner: int):
        from kashf import macro as mac
        cfg = load_yaml()["macro"]
        m = macro_flags()
        d = m[(m["hs6"] == hs6) & (m["partner"] == partner)].sort_values(["direction", "year"])
        rows = []
        for _, r in d.iterrows():
            rows.append({"year": int(r["year"]), "direction": r["direction"],
                         "value_exp": float(r["value_exp"]), "value_imp": float(r["value_imp"]),
                         "mirror_gap": float(r["mirror_gap"]),
                         "weight_gap": None if pd.isna(r["weight_gap"]) else float(r["weight_gap"]),
                         "peer_median": None if pd.isna(r.get("gap_peer_median", float("nan")))
                         else float(r["gap_peer_median"]),
                         "rule_flag": bool(r["rule_flag"]), "if_flag": bool(r.get("if_flag", False)),
                         "why": mac.explain(r, cfg) if r["rule_flag"] else "",
                         "benign": mac.innocent(r) if r["rule_flag"] else ""})
        return {"hs6": hs6, "partner": partner, "gap_threshold": float(cfg["gap_threshold"]),
                "baseline": cfg.get("baseline", "relative"), "gap_z_threshold": float(cfg.get("gap_z_threshold", 3.0)),
                "cif_fob_factor": float(cfg["cif_fob_factor"]), "rows": rows}

    @app.post("/api/upload")
    async def upload(files: list[UploadFile] = File(...)):
        got, total = {}, 0
        for f in files:
            fname = f.filename or ""
            if not fname.lower().endswith(".csv"):
                raise HTTPException(415, f"only .csv files are accepted (got {Path(fname).name or 'unnamed'})")
            name = Path(fname).stem
            if name in TABLES:
                data = await f.read(max_bytes - total + 1)     # never read more than the limit allows
                total += len(data)
                if total > max_bytes:
                    raise HTTPException(413, f"upload too large: limit is {max_bytes // (1024 * 1024)} MB")
                try:
                    got[name] = pd.read_csv(io.BytesIO(data), dtype=DTYPES)
                except Exception as e:
                    raise HTTPException(400, f"{name}.csv could not be read as CSV: {type(e).__name__}")
        missing = [t for t in TABLES if t not in got]
        if missing:
            raise HTTPException(400, f"missing files: {', '.join(m + '.csv' for m in missing)}")
        load(got)
        return summary()

    return app
