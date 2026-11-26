"""Real trade data from UN Comtrade (replaces scripts/fetch_comtrade.py).

Pulls annual HS6 flows with the official `comtradeapicall` package, caches every raw
response as Parquet under data/raw/, logs every call, retries with backoff, keeps to the
free-tier daily budget, and FAILS LOUDLY: nothing here ever falls back to the illustrative
prices in kashf/reference.py.

Three query families per year (all at total level: partner2=World, customs=C00, mode=all):

    uae_<year>     UAE (784) as reporter: exports X, re-exports RX, imports M, re-imports RM,
                   by partner                                      -> UAE side of each mirror pair
    mirror_<year>  every reporter's imports M / exports X with partner = UAE
                                                                   -> partner side of each mirror pair
    world_<year>   every reporter's exports X to World             -> global unit-value distribution

Usage (key in .env as COMTRADE_KEY=..., never in code):

    python -m kashf.comtrade test                    # one call: UAE, HS 851713, 2023
    python -m kashf.comtrade pull                    # ~16 calls, cached; safe to re-run
    python -m kashf.comtrade reference               # data/reference_comtrade.csv (reference.py schema)
    python -m kashf.comtrade card                    # docs/DATA_CARD.md (coverage, missing data, caveats)

API field names follow Comtrade's v1 "get" endpoint as returned by comtradeapicall 1.4
(primaryValue, qty, qtyUnitAbbr, netWgt, isQtyEstimated, isNetWgtEstimated, ...).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

from kashf.config import load_yaml
from kashf.reference import COLUMNS, default_table

log = logging.getLogger("kashf.comtrade")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CALL_LOG = RAW / "calls.jsonl"
QUOTA = RAW / ".quota.json"
MAX_RECORDS = 250_000            # API maximum per call with a subscription key

REQUIRED = ["period", "reporterCode", "partnerCode", "flowCode", "cmdCode", "primaryValue"]
KEEP = REQUIRED + ["reporterISO", "reporterDesc", "partnerISO", "partnerDesc", "cmdDesc", "qty",
                   "qtyUnitAbbr", "netWgt", "isQtyEstimated", "isNetWgtEstimated", "isReported",
                   "cifvalue", "fobvalue", "partner2Code", "customsCode", "motCode"]


class ComtradeError(RuntimeError):
    """Raised for any failure to get real data. There is no silent fallback."""


# ------------------------------------------------------------------ key handling
def get_key() -> str:
    try:
        from dotenv import load_dotenv
    except ImportError as e:  # pragma: no cover
        raise ComtradeError("python-dotenv is not installed: pip install python-dotenv") from e
    load_dotenv(ROOT / ".env")
    key = os.environ.get("COMTRADE_KEY", "").strip()
    if not key:
        raise ComtradeError("COMTRADE_KEY is not set. Put COMTRADE_KEY=<your key> in .env at the repo root.")
    return key


def _redact(text: str, key: str) -> str:
    """The key travels in the URL query string; make sure it never reaches a log or traceback."""
    return text.replace(key, "***") if key else text


# ------------------------------------------------------------------ quota + call log
def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _calls_today() -> int:
    if not QUOTA.exists():
        return 0
    q = json.loads(QUOTA.read_text())
    return int(q.get("count", 0)) if q.get("date") == _today() else 0


def _count_call() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    QUOTA.write_text(json.dumps({"date": _today(), "count": _calls_today() + 1}))


def _log_call(name: str, params: dict, status: str, rows: int, seconds: float, error: str = "") -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "query": name,
           "params": params, "status": status, "rows": rows, "seconds": round(seconds, 2)}
    if error:
        rec["error"] = error[:500]
    with CALL_LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")


# ------------------------------------------------------------------ one cached query
def fetch(name: str, *, period: str, cmd: str, flow: str, reporter: Optional[str], partner: Optional[str],
          key: str, cfg: dict, refresh: bool = False,
          caller: Optional[Callable[..., pd.DataFrame]] = None) -> pd.DataFrame:
    """Run one Comtrade query, or return its cached Parquet copy.

    `caller` exists for tests (inject a fake); in normal use it is comtradeapicall.getFinalData.
    """
    path = RAW / f"{name}.parquet"
    if path.exists() and not refresh:
        log.info("cache hit %s (%s)", name, path.name)
        return pd.read_parquet(path)
    if caller is None:
        import comtradeapicall
        caller = comtradeapicall.getFinalData
    budget = int(cfg.get("daily_call_budget", 450))
    if _calls_today() >= budget:
        raise ComtradeError(f"daily call budget reached ({budget}); cached queries still work, rerun tomorrow")

    params = {"typeCode": "C", "freqCode": "A", "clCode": "HS", "period": period, "reporterCode": reporter,
              "cmdCode": cmd, "flowCode": flow, "partnerCode": partner, "partner2Code": "0",
              "customsCode": "C00", "motCode": "0", "maxRecords": MAX_RECORDS, "includeDesc": True}
    retries, wait = int(cfg.get("max_retries", 5)), float(cfg.get("seconds_between_calls", 1.2))
    for attempt in range(1, retries + 1):
        t0 = time.time()
        try:
            _count_call()
            df = caller(key, **params)
            secs = time.time() - t0
        except Exception as e:  # network errors, HTTP 429/5xx raised by comtradeapicall
            msg = _redact(f"{type(e).__name__}: {e}", key)
            _log_call(name, params, "error", 0, time.time() - t0, msg)
            transient = any(c in msg for c in ("429", "500", "502", "503", "504", "Timeout", "MaxRetry",
                                                "Connection"))
            if not transient or attempt == retries:
                raise ComtradeError(f"{name}: Comtrade call failed after {attempt} attempt(s): {msg}") from None
            backoff = wait * 2 ** attempt
            log.warning("%s: attempt %d failed (%s); retrying in %.0fs", name, attempt, msg, backoff)
            time.sleep(backoff)
            continue
        if df is None:
            _log_call(name, params, "error", 0, secs, "no data frame returned")
            raise ComtradeError(f"{name}: comtradeapicall returned nothing (check the key and parameters)")
        n = len(df)
        _log_call(name, params, "ok", n, secs)
        log.info("%s: %d rows in %.1fs", name, n, secs)
        if n >= MAX_RECORDS:
            raise ComtradeError(f"{name}: hit the {MAX_RECORDS}-row cap, result truncated; split the query")
        df = _postprocess(df, name)
        RAW.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        time.sleep(wait)
        return df
    raise ComtradeError(f"{name}: unreachable")  # pragma: no cover


def _postprocess(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Keep the columns Kashf uses and normalise HS codes; raise if the schema changed."""
    if df.empty:
        return df
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ComtradeError(f"{name}: response lacks columns {missing}; the API schema changed")
    df = df[[c for c in KEEP if c in df.columns]].copy()
    df["cmdCode"] = df["cmdCode"].astype(str).str.zfill(6)
    return df


def import_saved(paths: list[Path]) -> dict[str, int]:
    """Import API responses saved as JSON elsewhere (e.g. fetched from a browser on a machine whose
    network can reach Comtrade). Each file must hold {"query": "<name>", "data": [...]} where data is
    the API's own `data` array. Same post-processing and cache layout as `fetch`; logged as via=import."""
    from pandas import json_normalize
    RAW.mkdir(parents=True, exist_ok=True)
    done = {}
    for p in paths:
        obj = json.loads(Path(p).read_text())
        name = obj.get("query") or Path(p).stem.replace("kashf_", "")
        if name == "smoke_test":
            continue
        rows = obj.get("data") or []
        df = _postprocess(json_normalize(rows) if rows else pd.DataFrame(), name)
        df.to_parquet(RAW / f"{name}.parquet", index=False)
        params = {k: v for k, v in (obj.get("params") or {}).items() if "key" not in k.lower()}
        rec = {"ts": obj.get("pulled", datetime.now(timezone.utc).isoformat(timespec="seconds")),
               "query": name, "params": params, "status": "ok", "rows": len(df), "seconds": None,
               "via": "import"}
        with CALL_LOG.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        done[name] = len(df)
        log.info("imported %s: %d rows", name, len(df))
    return done


# ------------------------------------------------------------------ pulls
def hs_codes(extra: Optional[list[str]] = None) -> list[str]:
    codes = list(default_table()["hs6"])
    for c in extra or []:
        if c not in codes:
            codes.append(c)
    return codes


def top_reexports(key: str, cfg: dict, n: int, year: int) -> list[str]:
    """Top-n HS6 codes by UAE re-export value in `year` (one call)."""
    if n <= 0:
        return []
    df = fetch(f"top_rx_{year}", period=str(year), cmd="AG6", flow="RX", reporter=str(cfg["reporter"]),
               partner="0", key=key, cfg=cfg)
    if df.empty:
        log.warning("UAE reported no re-exports for %d; not expanding the HS6 list", year)
        return []
    return (df.groupby("cmdCode")["primaryValue"].sum().sort_values(ascending=False)
            .head(n).index.astype(str).str.zfill(6).tolist())


def pull(cfg: Optional[dict] = None, refresh: bool = False) -> dict[str, pd.DataFrame]:
    """Pull every query for every configured year. Cached queries cost no calls."""
    cfg = cfg or load_yaml().get("comtrade", {})
    key = get_key()
    years = [int(y) for y in cfg["years"]]
    uae = str(cfg["reporter"])
    extra: list[str] = []
    if int(cfg.get("expand_top_reexports", 0)):
        # latest year in which the UAE reported re-exports
        for y in sorted(years, reverse=True):
            extra = top_reexports(key, cfg, int(cfg["expand_top_reexports"]), y)
            if extra:
                break
    codes = hs_codes(extra)
    (RAW / "hs_codes.json").parent.mkdir(parents=True, exist_ok=True)
    (RAW / "hs_codes.json").write_text(json.dumps({"base": hs_codes(), "added_top_reexports": extra}, indent=2))
    cmd = ",".join(codes)
    out = {}
    for y in years:
        out[f"uae_{y}"] = fetch(f"uae_{y}", period=str(y), cmd=cmd, flow="X,RX,M,RM", reporter=uae,
                                partner=None, key=key, cfg=cfg, refresh=refresh)
        out[f"mirror_{y}"] = fetch(f"mirror_{y}", period=str(y), cmd=cmd, flow="M,X", reporter=None,
                                   partner=uae, key=key, cfg=cfg, refresh=refresh)
        out[f"world_{y}"] = fetch(f"world_{y}", period=str(y), cmd=cmd, flow="X", reporter=None,
                                  partner="0", key=key, cfg=cfg, refresh=refresh)
    empty = [k for k, v in out.items() if v.empty]
    if empty:
        log.warning("queries with no rows (recorded in the data card): %s", ", ".join(empty))
    if all(out[f"uae_{y}"].empty for y in years):
        raise ComtradeError("the UAE reported no data for any configured year; mirror pairs cannot be built")
    return out


def load_raw(raw: Path = RAW) -> pd.DataFrame:
    """All cached flows in one tidy frame (one row per reporter x partner x flow x HS6 x year)."""
    files = sorted(raw.glob("uae_*.parquet")) + sorted(raw.glob("mirror_*.parquet")) + \
        sorted(raw.glob("world_*.parquet"))
    if not files:
        raise ComtradeError(f"no cached Comtrade data in {raw}; run `python -m kashf.comtrade pull` first")
    frames = []
    for f in files:
        d = pd.read_parquet(f)
        if d.empty:
            continue
        d["source"] = f.stem.split("_")[0]
        frames.append(d)
    if not frames:
        raise ComtradeError(f"all cached Comtrade files in {raw} are empty")
    return harmonise_units(tidy(pd.concat(frames, ignore_index=True)))


def harmonise_units(t: pd.DataFrame) -> pd.DataFrame:
    """Blank quantities reported in a unit other than the HS6 code's usual one.

    Reporters sometimes give the same product in different quantity units (e.g. furniture in
    pieces by most, in kg by a few). Dividing value by such a quantity produces absurd unit values,
    so a quantity counts only when its unit matches the most common unit for that HS6 in the
    world-export rows. Net weights (always kg) are untouched. The count of blanked quantities is
    logged and shown in the data card via the missing-quantity share.
    """
    t = t.copy()
    unit = t["qty_unit"].fillna("").astype(str).str.lower()
    ref = t[t["source"] == "world"] if (t["source"] == "world").any() else t
    modal = (ref.assign(u=unit[ref.index]).groupby("hs6")["u"]
             .agg(lambda x: x.mode().iloc[0] if len(x.mode()) else ""))
    expected = t["hs6"].map(modal).fillna("")
    bad = t["qty"].notna() & (unit != expected)
    if bad.any():
        log.info("blanked %d quantities (%.1f%%) reported in a non-standard unit for their HS6",
                 int(bad.sum()), 100 * bad.mean())
    t.loc[bad, "qty"] = np.nan
    # Comtrade fills missing quantities/weights with its own estimates; a unit value or weight gap
    # built on an estimate is not evidence about the trade, so estimates are dropped too.
    qe = t["qty"].notna() & t["qty_estimated"].astype("boolean").fillna(False).astype(bool)
    we = t["net_wgt_kg"].notna() & t["wgt_estimated"].astype("boolean").fillna(False).astype(bool)
    log.info("dropped %d Comtrade-estimated quantities (%.1f%%) and %d estimated net weights (%.1f%%)",
             int(qe.sum()), 100 * qe.mean(), int(we.sum()), 100 * we.mean())
    t.loc[qe, "qty"] = np.nan
    t.loc[we, "net_wgt_kg"] = np.nan
    return t


def tidy(df: pd.DataFrame) -> pd.DataFrame:
    """Rename Comtrade columns to Kashf's names and coerce types."""
    ren = {"period": "year", "reporterCode": "reporter", "partnerCode": "partner", "flowCode": "flow",
           "cmdCode": "hs6", "primaryValue": "value_usd", "netWgt": "net_wgt_kg", "qtyUnitAbbr": "qty_unit",
           "reporterISO": "reporter_iso", "partnerISO": "partner_iso", "cmdDesc": "description",
           "isQtyEstimated": "qty_estimated", "isNetWgtEstimated": "wgt_estimated"}
    t = df.rename(columns=ren).copy()
    t["year"] = t["year"].astype(int)
    t["reporter"] = t["reporter"].astype(int)
    t["partner"] = t["partner"].astype(int)
    t["hs6"] = t["hs6"].astype(str).str.zfill(6)
    for c in ("value_usd", "qty", "net_wgt_kg"):
        if c in t:
            t[c] = pd.to_numeric(t[c], errors="coerce")
            t.loc[t[c] <= 0, c] = np.nan
    for c in ("qty_estimated", "wgt_estimated"):
        if c not in t:
            t[c] = np.nan
    for c in ("qty_unit", "reporter_iso", "partner_iso", "description"):
        if c not in t:
            t[c] = None
    return t


# ------------------------------------------------------------------ reference table
def price_basis(world: pd.DataFrame) -> pd.Series:
    """Per HS6: 'kg' when Comtrade's usual quantity unit is kg or missing, else 'unit'."""
    u = world[["hs6", "qty_unit"]].copy()
    u["qty_unit"] = u["qty_unit"].fillna("").astype(str).str.lower()
    top = u.groupby("hs6")["qty_unit"].agg(lambda x: x.mode().iloc[0] if len(x.mode()) else "")
    return top.map(lambda v: "kg" if v in ("kg", "n/q", "n/a", "na", "none", "-1", "") else "unit")


def unit_value(df: pd.DataFrame, basis: pd.Series) -> pd.Series:
    """USD per kg (kg-priced HS6) or per unit (unit-priced HS6); NaN when the quantity is missing."""
    per_kg = df["hs6"].map(basis).fillna("kg") == "kg"
    denom = np.where(per_kg, df["net_wgt_kg"], df["qty"])
    return pd.Series(df["value_usd"].values / denom, index=df.index)


def global_distribution(flows: pd.DataFrame, min_reporters: int = 5) -> pd.DataFrame:
    """Median and MAD of log unit values across reporters' exports to World, per HS6 x year."""
    w = flows[(flows["source"] == "world") & (flows["flow"] == "X") & (flows["partner"] == 0)].copy()
    if w.empty:
        raise ComtradeError("no world export rows cached; cannot build the global unit-value distribution")
    basis = price_basis(w)
    w["uv"] = unit_value(w, basis)
    w = w[np.isfinite(w["uv"]) & (w["uv"] > 0)]
    w["luv"] = np.log(w["uv"])
    g = w.groupby(["hs6", "year"])["luv"].agg(
        n_reporters="count", log_median="median",
        log_mad=lambda x: float(np.median(np.abs(x - np.median(x))))).reset_index()
    g["basis"] = g["hs6"].map(basis)
    g["enough"] = g["n_reporters"] >= min_reporters
    return g


def build_reference(flows: pd.DataFrame, cfg: Optional[dict] = None, allow_partial: bool = False) -> pd.DataFrame:
    """Real reference table in kashf.reference's schema, pooled over all cached years.

    Codes with too few reporters raise ComtradeError unless allow_partial=True, in which case
    they are LEFT OUT (never filled with illustrative values) and listed in the log.
    """
    cfg = cfg or load_yaml().get("comtrade", {})
    min_rep = int(cfg.get("min_reporters_for_reference", 5))
    base = default_table().set_index("hs6")
    w = flows[(flows["source"] == "world") & (flows["flow"] == "X") & (flows["partner"] == 0)
              & flows["hs6"].isin(base.index)].copy()
    basis = price_basis(w) if not w.empty else pd.Series(dtype=str)
    rows, missing = [], []
    for hs6, b in base.iterrows():
        g = w[w["hs6"] == hs6]
        if g.empty:
            missing.append(f"{hs6} (no rows)")
            continue
        uv = unit_value(g, basis)
        uv = uv[np.isfinite(uv) & (uv > 0)]
        if len(uv) < min_rep:
            missing.append(f"{hs6} ({len(uv)} usable reporter-years)")
            continue
        luv = np.log(uv)
        med = float(np.median(luv))
        mad = float(np.median(np.abs(luv - med)))
        unit = basis.get(hs6, "kg")
        if unit == "unit":
            kpu = (g["net_wgt_kg"] / g["qty"]).replace([np.inf, -np.inf], np.nan).dropna()
            kg_per_unit = float(np.median(kpu)) if len(kpu) else float(b["kg_per_unit"])
            kpu_source = "comtrade" if len(kpu) else "illustrative (no weight data)"
        else:
            kg_per_unit, kpu_source = 1.0, "n/a (kg-priced)"
        rows.append({"hs6": hs6, "description": b["description"], "unit": unit,
                     "ref_usd": round(math.exp(med), 4), "log_mad": round(max(mad, 0.05), 4),
                     "kg_per_unit": round(kg_per_unit, 4), "n_reporter_years": int(len(uv)),
                     "kg_per_unit_source": kpu_source})
        log.info("%s %s: median $%s/%s from %d reporter-years (log-MAD %.2f)", hs6, b["description"],
                 f"{math.exp(med):,.2f}", unit, len(uv), mad)
    if missing:
        msg = "not enough real Comtrade data for: " + ", ".join(missing)
        if not allow_partial:
            raise ComtradeError(msg + ". Re-run with --allow-partial to write only the codes that have data.")
        log.warning(msg + " (left out of the reference table)")
    if not rows:
        raise ComtradeError("no HS6 code had enough data; reference table not written")
    return pd.DataFrame(rows)


def write_reference(ref: pd.DataFrame, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    ref[COLUMNS].to_csv(out, index=False)
    ref.to_csv(out.with_name(out.stem + "_detail.csv"), index=False)


# ------------------------------------------------------------------ data card
CAVEATS = """## Caveats (read before interpreting any mirror gap)

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
"""


def data_card(flows: pd.DataFrame, path: Path, cfg: Optional[dict] = None) -> None:
    """Write docs/DATA_CARD.md from the cached data and the call log."""
    cfg = cfg or load_yaml().get("comtrade", {})
    calls = [json.loads(x) for x in CALL_LOG.read_text().splitlines()] if CALL_LOG.exists() else []
    ok = [c for c in calls if c["status"] == "ok" and c["query"] != "smoke_test"]
    pulled = sorted({c["ts"][:10] for c in ok})
    codes = json.loads((RAW / "hs_codes.json").read_text()) if (RAW / "hs_codes.json").exists() else {}
    L = ["# Data card: UN Comtrade data used by Kashf", "",
         "| Field | Value |", "|---|---|",
         "| Source | UN Comtrade API v1 (`data/v1/get/C/A/HS`), final annual data, HS classification |",
         "| Retrieval | " + ("API responses saved on the user's machine and imported with `python -m kashf.comtrade "
                           "import` (same parameters and post-processing as `pull`)"
                           if any(c.get("via") == "import" for c in ok) else "`python -m kashf.comtrade pull` "
                           "(comtradeapicall)") + " |",
         "| Excluded values | quantities in a non-standard unit for the HS6, and Comtrade-estimated quantities and "
         "net weights (`isQtyEstimated`, `isNetWgtEstimated`) |",
         f"| Pull date(s) (UTC) | {', '.join(pulled) or 'not recorded'} |",
         f"| API calls logged | {len(ok)} successful, {sum(c['status'] == 'error' for c in calls)} failed "
         "(data/raw/calls.jsonl) |",
         f"| Years requested | {', '.join(map(str, cfg.get('years', [])))} |",
         f"| HS6 codes | {len(codes.get('base', []))} base (kashf/reference.py) + "
         f"{len(codes.get('added_top_reexports', []))} top UAE re-export codes |",
         "| Filters | partner2 = World, customs procedure = C00 (all), mode of transport = 0 (all) |",
         f"| Rows cached | {len(flows):,} |", ""]
    L += ["## Coverage by query family and year", "",
          "| Source | Year | Rows | Reporters | Partners | HS6 | Missing qty | Missing net weight | Estimated weight |",
          "|---|---|---|---|---|---|---|---|---|"]
    for (src, yr), g in flows.groupby(["source", "year"]):
        est = g["wgt_estimated"].astype("boolean").mean() if g["wgt_estimated"].notna().any() else float("nan")
        L.append(f"| {src} | {yr} | {len(g):,} | {g['reporter'].nunique()} | {g['partner'].nunique()} | "
                 f"{g['hs6'].nunique()} | {g['qty'].isna().mean():.0%} | {g['net_wgt_kg'].isna().mean():.0%} | "
                 + ("n/a" if pd.isna(est) else f"{est:.0%}") + " |")
    uae = flows[flows["source"] == "uae"]
    years_missing = sorted(set(int(y) for y in cfg.get("years", [])) - set(uae["year"].unique()))
    L += ["", "## UAE reporting", "",
          f"- UAE-reported flows (X/RX/M/RM) found for: {', '.join(map(str, sorted(uae['year'].unique()))) or 'none'}",
          f"- Years with no UAE report (mirror pairs impossible): {', '.join(map(str, years_missing)) or 'none'}",
          "- Re-exports in UAE-reported exports: "
          + (f"{uae.loc[uae['flow'] == 'RX', 'value_usd'].sum() / max(1.0, uae.loc[uae['flow'].isin(['X', 'RX']), 'value_usd'].sum()):.0%} of X + RX value"
             if not uae.empty else "n/a"), ""]
    L += [CAVEATS]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n")


# ------------------------------------------------------------------ smoke test
def smoke_test() -> pd.DataFrame:
    """One call: UAE (784) exports of HS 851713 (smartphones) in 2023, all partners."""
    import comtradeapicall
    key = get_key()
    try:
        df = comtradeapicall.getFinalData(key, typeCode="C", freqCode="A", clCode="HS", period="2023",
                                          reporterCode="784", cmdCode="851713", flowCode="X,RX",
                                          partnerCode=None, partner2Code="0", customsCode="C00", motCode="0",
                                          maxRecords=500, includeDesc=True)
    except Exception as e:
        raise ComtradeError(_redact(f"test call failed: {type(e).__name__}: {e}", key)) from None
    _log_call("smoke_test", {"reporter": 784, "cmd": "851713", "period": 2023}, "ok",
              0 if df is None else len(df), 0.0)
    return df if df is not None else pd.DataFrame()


# ------------------------------------------------------------------ CLI
def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m kashf.comtrade")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("test", help="one test call (UAE, HS 851713, 2023)")
    p = sub.add_parser("pull", help="pull and cache all configured queries")
    p.add_argument("--refresh", action="store_true", help="ignore the cache and call the API again")
    r = sub.add_parser("reference", help="build data/reference_comtrade.csv from the cache")
    r.add_argument("--out", default=str(ROOT / "data" / "reference_comtrade.csv"))
    r.add_argument("--allow-partial", action="store_true")
    sub.add_parser("card", help="write docs/DATA_CARD.md from the cache")
    im = sub.add_parser("import", help="import API responses saved as JSON (see import_saved)")
    im.add_argument("files", nargs="+")
    im.add_argument("--codes", help="comma-separated HS6 list actually requested (for hs_codes.json)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if a.cmd == "test":
        df = smoke_test()
        if df.empty:
            log.warning("key accepted but 0 rows: the UAE may not have reported 2023 for this code yet")
        else:
            cols = [c for c in ("flowCode", "partnerDesc", "primaryValue", "qty", "netWgt") if c in df.columns]
            log.info("key works: %d rows. Top partners by value:\n%s", len(df),
                     df.sort_values("primaryValue", ascending=False)[cols].head(5).to_string(index=False))
    elif a.cmd == "pull":
        out = pull(refresh=a.refresh)
        log.info("done: %s", ", ".join(f"{k}={len(v)}" for k, v in out.items()))
    elif a.cmd == "reference":
        ref = build_reference(load_raw(), allow_partial=a.allow_partial)
        write_reference(ref, Path(a.out))
        log.info("wrote %s (%d HS6 codes, real Comtrade values)", a.out, len(ref))
    elif a.cmd == "import":
        done = import_saved([Path(f) for f in a.files])
        if a.codes:
            codes = [c.strip().zfill(6) for c in a.codes.split(",") if c.strip()]
            base = hs_codes()
            (RAW / "hs_codes.json").write_text(json.dumps(
                {"base": base, "added_top_reexports": [c for c in codes if c not in base]}, indent=2))
        log.info("imported %d files: %s", len(done), ", ".join(f"{k}={v}" for k, v in sorted(done.items())))
    elif a.cmd == "card":
        data_card(load_raw(), ROOT / "docs" / "DATA_CARD.md")
        log.info("wrote docs/DATA_CARD.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
