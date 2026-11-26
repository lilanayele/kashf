"""Kashf command line.

    kashf generate --seed 1 --out data/demo            # synthetic dataset
    kashf analyse data/demo --out output/              # alerts.csv, signals.csv, entities.csv
    kashf case data/demo INV-2025-000123               # case summary for one invoice (Markdown)
    kashf serve data/demo                              # dashboard at http://127.0.0.1:8800
    kashf evaluate --seeds 5                           # reproduce the paper's results
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kashf", description="Explainable trade-based money laundering detection")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--seed", type=int, default=1)
    g.add_argument("--n", type=int, default=20000)
    g.add_argument("--out", default="data/demo")
    g.add_argument("--reference", help="draw invoice prices around this reference CSV (e.g. real Comtrade)")
    a = sub.add_parser("analyse")
    a.add_argument("data")
    a.add_argument("--out", default="output")
    a.add_argument("--reference", help="reference price CSV (e.g. from scripts/fetch_comtrade.py)")
    c = sub.add_parser("case")
    c.add_argument("data")
    c.add_argument("id", help="invoice number or entity id")
    c.add_argument("--html", action="store_true")
    s = sub.add_parser("serve")
    s.add_argument("data")
    s.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8800)))
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--reference", help="reference price CSV used to analyse the data")
    s.add_argument("--macro-dir", help="folder with results of `python -m kashf.macro`")
    e = sub.add_parser("evaluate")
    e.add_argument("--seeds", type=int, default=5)
    e.add_argument("--n", type=int, default=20000)
    e.add_argument("--out", default="results")
    args = ap.parse_args(argv)

    if args.cmd == "generate":
        from kashf import reference
        from kashf.generate import Config, generate, save
        ref = reference.load(args.reference) if args.reference else None
        t = generate(Config(seed=args.seed, n_invoices=args.n, reference=ref))
        save(t, args.out)
        print(f"wrote {len(t['invoices'])} invoices to {args.out}")
    elif args.cmd == "analyse":
        from kashf import reference
        from kashf.pipeline import analyse, load_dir
        r = analyse(load_dir(args.data), ref=reference.load(args.reference) if args.reference else None)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        r.invoices.to_csv(out / "scored_invoices.csv", index=False)
        r.invoices[r.invoices["alert"]].to_csv(out / "alerts.csv", index=False)
        r.signals.to_csv(out / "signals.csv", index=False)
        r.entities.to_csv(out / "entities.csv", index=False)
        n_alert = int(r.invoices["alert"].sum())
        print(f"{len(r.invoices)} invoices analysed, {n_alert} alerts -> {out}/alerts.csv")
        print(r.invoices[r.invoices["alert"]].head(10)[["invoice_no", "score", "detectors", "top_reason"]]
              .to_string(index=False, max_colwidth=90))
    elif args.cmd == "case":
        from kashf.pipeline import analyse, load_dir
        from kashf.report import entity_case, invoice_case, to_html
        r = analyse(load_dir(args.data))
        md = invoice_case(r, args.id) if args.id.startswith("INV") else entity_case(r, args.id)
        print(to_html(md) if args.html else md)
    elif args.cmd == "serve":
        import uvicorn
        from kashf.api import create_app
        uvicorn.run(create_app(args.data, macro_dir=args.macro_dir, reference_path=args.reference),
                    host=args.host, port=args.port)
    elif args.cmd == "evaluate":
        from kashf.evaluate import run
        run(args.seeds, args.n, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
