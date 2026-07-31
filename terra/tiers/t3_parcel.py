"""Laag 3: perceel. Dit is wat je uiteindelijk koopt.

Drie echte poorten, en de eerlijke stand van de automatisering:
  K4 toegang        -> te benaderen uit het wegennet, dus automatisch
  K6 via pecuaria   -> uit de laag van MITECO, dus automatisch
  K5 register       -> een nota simple bij het eigendomsregister, dus met de hand

Daarom stopt de nacht bij een shortlist. Wat daarna komt is per perceel mensenwerk,
en de pijplijn hoort dat te zeggen in plaats van het te verbergen.
"""
from __future__ import annotations

from .. import db, promote
from ..config import PROFILE_HA
from ..countries import jurisdiction_of
from ..criteria import MIN_HA_FALLBACK
from ..rules import (candidate_window, parcel_flags, parcel_gates, profile_match)
from ..scoring import delta_per_price, parcel_score


def _obs(c, pid: str) -> dict:
    rows = db.q(c, """select variable, value_num, value_txt, quality from observation
                      where subject_type='parcel' and subject_id=%s and quality<>'mis'""",
                (pid,))
    return {r["variable"]: r for r in rows}


def run(c, run_id: int | None = None, intent: str = "dehesa") -> dict:
    rows = db.q(c, "select * from parcel order by id")
    stats = {"seen": len(rows), "promoted": 0, "rejected": 0, "pending": 0,
             "changed": 0, "profile": {}, "manual_next": [], "scored": []}
    for p in rows:
        pid = str(p["id"])
        o = _obs(c, pid)
        d = dict(p)
        d["jurisdiction"] = jurisdiction_of(p["region_code"])
        for g in ("k4_ok", "k5_ok", "k6_ok"):
            v = o.get(g)
            d[g] = None if v is None else bool(v["value_num"])
        ok, reasons = parcel_gates(d)
        flags = parcel_flags(d, intent, MIN_HA_FALLBACK)
        reasons = reasons + [f"{f['k']}: {f['note']}" for f in flags]
        status = promote.verdict(ok, reasons)
        stats[status] += 1
        fit = profile_match(d, *PROFILE_HA)
        stats["profile"][fit] = stats["profile"].get(fit, 0) + 1
        if d["k5_ok"] is None and ok is not False:
            stats["manual_next"].append({"parcel": pid, "need": "nota simple",
                                         "muni": p["muni_name"] or p["muni_code"]})
        sc = parcel_score({k: (o[k]["value_num"] if k in o else None) for k in "ABCDEFG"})
        eur_ha = (float(p["price_eur"]) / float(p["ha"])) if p["price_eur"] and p["ha"] else None
        stats["scored"].append({
            "parcel": pid, "eur_per_ha": round(eur_ha) if eur_ha else None,
            "points": sc["points"], "missing": sc["missing"],
            "delta_per_price": delta_per_price(sc["points"], eur_ha) if eur_ha else None})
        if promote.decide(c, "parcel", pid, status, reasons, run_id):
            stats["changed"] += 1
    return stats


def dry_run_quarantine(c, intent: str = "dehesa") -> dict:
    """Wat de trechter met de advertenties zou doen zodra hun herkomst er is.

    Expliciet gescheiden van run(): dit schrijft geen besluiten, want een besluit
    over een perceel dat je niet kunt terugvinden is geen besluit.
    """
    rows = db.q(c, "select * from listing_quarantine order by id")
    lo, hi = candidate_window(intent)
    out = {"n": len(rows), "profile": {}, "flags": {}, "candidates_window": 0,
           "candidates_min_only": 0, "window": [lo, hi], "ha_in_window": 0.0}
    for r in rows:
        ha = float(r["ha"]) if r["ha"] is not None else None
        d = {"ha": ha, "region_code": r["region_code"],
             "jurisdiction": jurisdiction_of(r["region_code"]),
             "price_eur": float(r["price_eur"]) if r["price_eur"] is not None else None}
        fit = profile_match(d, *PROFILE_HA)
        out["profile"][fit] = out["profile"].get(fit, 0) + 1
        for f in parcel_flags(d, intent, MIN_HA_FALLBACK):
            out["flags"][f["k"]] = out["flags"].get(f["k"], 0) + 1
        if ha and ha >= lo:
            out["candidates_min_only"] += 1          # K8 als scorepost
            if ha <= hi:
                out["candidates_window"] += 1        # K8 als uitsluiting
                out["ha_in_window"] += ha
    out["ha_in_window"] = round(out["ha_in_window"])
    out["note"] = ("dit zijn geen besluiten; deze advertenties zijn niet na te lopen "
                   "zonder URL en kijkdatum. Het verschil tussen de twee tellingen is "
                   "de open vraag of K8 uitsluit of alleen kost.")
    return out
