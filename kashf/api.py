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

from kashf.config import Settings
from kashf.detectors import link_graph
from kashf.pipeline import DTYPES, TABLES, analyse, load_dir
from kashf.report import entity_case, invoice_case

STATIC = Path(__file__).parent / "static"


def create_app(data_dir: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Kashf", version="0.1.0")
    state: dict = {}

    def load(tables: dict) -> None:
        tables = {k: v for k, v in tables.items() if k != "labels"}   # never expose ground truth
        state["res"] = analyse(tables)
        state["links"], state["hubs"] = link_graph(tables["entities"], Settings())

    if data_dir:
        load(load_dir(data_dir))

    def res():
        if "res" not in state:
            raise HTTPException(404, "No data loaded yet. Upload CSV files first.")
        return state["res"]

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

    @app.post("/api/upload")
    async def upload(files: list[UploadFile] = File(...)):
        got = {}
        for f in files:
            name = Path(f.filename or "").stem
            if name in TABLES:
                got[name] = pd.read_csv(io.BytesIO(await f.read()), dtype=DTYPES)
        missing = [t for t in TABLES if t not in got]
        if missing:
            raise HTTPException(400, f"missing files: {', '.join(m + '.csv' for m in missing)}")
        load(got)
        return summary()

    return app
