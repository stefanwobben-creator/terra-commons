"""Laag 2: gemeente. De laag die er nog niet is.

Dit is de stap die de rijpheidspoort opent, want spreiding binnen een regio was
groter dan tussen regio's: 2,51 tegen 2,02 voor neerslag. Zolang deze laag leeg is
meet de regiovergelijking deels ruis, en dat is geen mening maar het gemeten getal.

De module draait wel, en rapporteert hoeveel gemeenten hij vond en welke bronnen
hem blokkeren. Een lege laag die zijn eigen leegte logt is beter dan een laag die
je vergeet.
"""
from __future__ import annotations

from .. import db, promote
from ..registry import SOURCES
from ..rules import municipality_filter

NEEDED = ("gisco-lau", "ign-lineas-limite", "chelsa-climate", "umc-decreto-46-1997")


def _obs(c, code: str) -> dict:
    rows = db.q(c, """select variable, value_num, value_txt, quality from observation
                      where subject_type='municipality' and subject_id=%s""", (code,))
    return {r["variable"]: r for r in rows if r["quality"] != "mis"}


def run(c, run_id: int | None = None, intent: str = "dehesa") -> dict:
    # Alleen gemeenten in regio's die door laag 1 kwamen of daar in beraad staan.
    live = [r["subject_id"] for r in promote.latest(c, "region")
            if r["status"] in ("promoted", "pending")]
    rows = db.q(c, """select code, name, region_code, area_ha from municipality
                      where region_code = any(%s) order by code""", (live,)) if live else []
    stats = {"regions_live": len(live), "seen": len(rows),
             "promoted": 0, "rejected": 0, "pending": 0, "changed": 0}
    for m in rows:
        o = _obs(c, m["code"])
        d = {"rain_mm": (o.get("rain_mm") or {}).get("value_num"),
             "aquifer_at_risk": (o.get("aquifer_status") or {}).get("value_txt") == "riesgo",
             "needs_groundwater": intent == "dehesa"}
        ok, reasons = municipality_filter(d, intent)   # onbekende neerslag -> geen pas
        status = "pending" if d["rain_mm"] is None else promote.verdict(ok, reasons)
        stats[status] += 1
        if promote.decide(c, "municipality", m["code"], status, reasons, run_id):
            stats["changed"] += 1
    if not rows:
        stats["blocked_by"] = [s.id for s in SOURCES if s.id in NEEDED]
        stats["note"] = ("geen gemeentegeometrie ingeladen; dit is de laag die de "
                         "rijpheidspoort opent")
    return stats
