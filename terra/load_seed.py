"""Inname van wat de site nu toont, zodat de database dezelfde getallen produceert
als de pagina. Idempotent: tweemaal draaien geeft hetzelfde resultaat.

Let op de asymmetrie: regio's en landen komen er gewoon in, advertenties niet. Die
missen een URL en een kijkdatum en gaan daarom in quarantaine. Dat is geen bug in de
inname, dat is de inname die zijn werk doet.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from . import db
from .countries import COUNTRIES, REGION_COUNTRY
from .criteria import CRITERIA
from .registry import SOURCES

SEED = Path(__file__).resolve().parent.parent / "seed"
OBSERVED = date(2026, 7, 30)   # de dag waarop deze waarden op de site stonden

# Regiovariabele -> (bron, eenheid). Zonder die koppeling is een kwaliteitscode
# een mening in plaats van een eigenschap van een bron.
VAR_SOURCE = {
    "price_eur_ha": ("eurostat-lprc", "EUR/ha"),
    "cost_pct": ("legal-country", "%"),
    "rain_mm": ("chelsa-climate", "mm/jaar"),
    "burned_ha": ("effis-fires", "ha"),
    "cadastre_class": ("catastro-inspire", None),
    "buyer_access": ("legal-country", None),
}
VAR_MAP = {"price": "price_eur_ha", "cost": "cost_pct", "rain": "rain_mm",
           "fire": "burned_ha", "cadastre": "cadastre_class", "access": "buyer_access"}

_OBS_SQL = """
insert into observation (subject_type,subject_id,variable,value_num,value_txt,unit,
                         quality,comparable,source_id,observed_at,note)
values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
on conflict (subject_type,subject_id,variable,observed_at) do update set
  value_num=excluded.value_num, value_txt=excluded.value_txt,
  quality=excluded.quality, comparable=excluded.comparable, note=excluded.note
"""


def _j(name: str):
    return json.loads((SEED / f"{name}.json").read_text())


def load_sources(c) -> int:
    return db.many(c, """
        insert into source (id,name,url,licence,cadence,automatable,tier,notes)
        values (%s,%s,%s,%s,%s,%s,%s,%s)
        on conflict (id) do update set name=excluded.name, cadence=excluded.cadence,
          automatable=excluded.automatable, tier=excluded.tier, notes=excluded.notes
    """, [(s.id, s.name, s.url, s.licence, s.cadence, s.automatable, s.tier, s.notes)
          for s in SOURCES])


def load_countries(c) -> int:
    n = db.many(c, """
        insert into country (code,name,buy_allowed,buy_conditions,use_obligation,
                             exit_levy_pct,exit_levy_years)
        values (%s,%s,%s,%s,%s,%s,%s)
        on conflict (code) do update set
          buy_allowed=excluded.buy_allowed, buy_conditions=excluded.buy_conditions,
          use_obligation=excluded.use_obligation, exit_levy_pct=excluded.exit_levy_pct,
          exit_levy_years=excluded.exit_levy_years
    """, [(k["code"], k["name"], k["buy_allowed"], k["buy_conditions"],
           k["use_obligation"], k["exit_levy_pct"], k["exit_levy_years"])
          for k in COUNTRIES])
    # De landpoort is zelf een observatie, met een kwaliteitscode. Anders staat er
    # straks een harde false bij Bulgarije waar 'niet gelezen' hoort te staan.
    db.many(c, _OBS_SQL, [
        ("country", k["code"], "legal_gate_inputs", None,
         json.dumps({"buy_allowed": k["buy_allowed"], "conditions": k["buy_conditions"],
                     "use_obligation": k["use_obligation"],
                     "exit_levy_pct": k["exit_levy_pct"]}),
         None, k["quality"], True, "legal-country", OBSERVED, k["note"])
        for k in COUNTRIES])
    return n


def _region_value(r: dict, key: str) -> tuple[float | None, str | None]:
    """Middelpunt waar de site een bandbreedte toont, met de band in de tekst.

    Het middelpunt is een vereenvoudiging, dus de band gaat mee als tekst: de
    spreiding binnen een regio bleek groter dan die tussen regio's.
    """
    if key == "price":
        lo, hi = r.get("priceMin"), r.get("priceMax")
        return ((lo + hi) / 2, f"{lo}-{hi}") if lo is not None else (None, None)
    if key == "cost":
        return r.get("costV"), r.get("cost")
    if key == "rain":
        lo, hi = r.get("rainMin"), r.get("rainMax")
        return ((lo + hi) / 2, f"{lo}-{hi}") if lo is not None else (None, None)
    if key == "fire":
        return r.get("fire"), (r.get("fireNote") or {}).get("nl")
    if key == "cadastre":
        return None, (r.get("cadastre") or {}).get("nl")
    if key == "access":
        return None, r.get("access")
    return None, None


def load_regions(c) -> tuple[int, int]:
    regions = _j("regions")
    variables = {v["k"]: v for v in _j("variables")}
    rows, obs = [], []
    for r in regions:
        cc, nuts = REGION_COUNTRY[r["key"]]
        rows.append((r["key"], cc, r["name"]["nl"], nuts))
        for site_key, var in VAR_MAP.items():
            qual = r["q"].get(site_key, "mis")
            src, unit = VAR_SOURCE[var]
            cmp_ok = bool(variables[site_key]["cmp"])
            num, txt = _region_value(r, site_key) if qual != "mis" else (None, None)
            obs.append(("region", r["key"], var, num, txt, unit, qual, cmp_ok, src,
                        OBSERVED, None if cmp_ok else variables[site_key]["why"]["nl"]))
    n = db.many(c, """
        insert into region (code,country_code,name,nuts2) values (%s,%s,%s,%s)
        on conflict (code) do update set name=excluded.name,
          country_code=excluded.country_code, nuts2=excluded.nuts2
    """, rows)
    return n, db.many(c, _OBS_SQL, obs)


def load_criteria(c) -> int:
    crit = {x["k"]: x for x in _j("criteria")}
    return db.many(c, """
        insert into criterion (k,category,scope,jurisdiction,intent_dep,label_nl,
                               label_en,why_nl,why_en)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        on conflict (k) do update set category=excluded.category, scope=excluded.scope,
          jurisdiction=excluded.jurisdiction, intent_dep=excluded.intent_dep,
          label_nl=excluded.label_nl, why_nl=excluded.why_nl
    """, [(x.k, x.category, x.scope, x.jurisdiction, x.intent_dep,
           crit[x.k]["nm"]["nl"], crit[x.k]["nm"]["en"],
           crit[x.k]["w"]["nl"], crit[x.k]["w"]["en"]) for x in CRITERIA])


def load_listings(c) -> dict:
    """Advertenties. Zonder URL en kijkdatum komen ze niet in parcel."""
    parcels = _j("parcels")
    keep, quarantine = [], []
    for p in parcels:
        url, seen = p.get("url"), p.get("seen_at")
        if url and seen:
            keep.append((p["r"], p["m"], p["ha"], p["p"], url, "listings", seen))
        else:
            quarantine.append((p["r"], p["m"], p["ha"], p["p"], p.get("src"),
                               "geen listing_url en geen kijkdatum", json.dumps(p)))
    n_keep = db.many(c, """
        insert into parcel (kind,region_code,muni_name,ha,price_eur,listing_url,
                            source_id,seen_at)
        values ('listing',%s,%s,%s,%s,%s,%s,%s)""", keep)
    db.x(c, "truncate listing_quarantine")
    n_q = db.many(c, """
        insert into listing_quarantine (region_code,muni_name,ha,price_eur,src_name,
                                        reason,raw)
        values (%s,%s,%s,%s,%s,%s,%s)""", quarantine)
    return {"accepted": n_keep, "quarantined": n_q, "complete": len(parcels) >= 30}


def main() -> dict:
    with db.conn() as c:
        with db.Run(c, "load_seed") as run:
            stats = {"sources": load_sources(c), "countries": load_countries(c)}
            stats["regions"], stats["region_obs"] = load_regions(c)
            stats["criteria"] = load_criteria(c)
            stats["listings"] = load_listings(c)
            c.commit()
            run.stats = stats
        return stats


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
