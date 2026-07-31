"""Pure beslisfuncties. Geen database, geen netwerk, dus testbaar."""
from __future__ import annotations
from typing import Iterable

from .criteria import (BY_K, CRITERIA, GATES, MIN_HA_FALLBACK, PROFILE_HA,
                       RAIN_FLOOR_MM, Intent)


def country_gate(c: dict) -> tuple[bool, list[str]]:
    """Stap 0. Landniveau, binair. Faalt dit, dan is perceelscoring zinloos."""
    reasons: list[str] = []
    if c.get("buy_allowed") is False:
        reasons.append("EU-particulier mag hier geen landbouwgrond verwerven")
    if c.get("buy_conditions"):
        reasons.append(f"kwalificatie-eis: {c['buy_conditions']}")
    if c.get("use_obligation"):
        reasons.append("verplicht exclusief agrarisch gebruik, botst met passief herstel")
    if (c.get("exit_levy_pct") or 0) >= 50:
        reasons.append(f"heffing {c['exit_levy_pct']}% bij doorverkoop binnen "
                       f"{c.get('exit_levy_years')} jaar")
    if c.get("parcel_geometry_open") is False:
        reasons.append("geen open perceelgeometrie, screenen niet mogelijk")
    return (not reasons), reasons


def municipality_filter(m: dict, intent: Intent = "dehesa") -> tuple[bool, list[str]]:
    """Tier 2. De juridische envelop plus de klimaatdrempel."""
    reasons: list[str] = []
    floor = RAIN_FLOOR_MM[intent]
    rain = m.get("rain_mm")
    if rain is None:
        reasons.append("K1 neerslag niet vastgesteld")       # onbekend != geschikt
    elif rain < floor:
        reasons.append(f"K1 {rain} mm onder de ondergrens van {floor} mm")
    if m.get("aquifer_at_risk") and m.get("needs_groundwater"):
        reasons.append("K7 grondwatervoorraad en riesgo en het plan hangt eraan")
    return (not reasons), reasons


def parcel_gates(p: dict) -> tuple[bool | None, list[str]]:
    """Tier 3, de drie echte poorten.

    Retourneert None als geen enkele poort te toetsen is op de aanwezige velden.
    Dat is geen 'goedgekeurd': het is 'niet beoordeeld', en dat verschil is de
    hele reden dat deze functie geen bool teruggeeft.
    """
    known = [g for g in GATES if p.get(g.k.lower() + "_ok") is not None]
    if not known:
        return None, ["geen van de drie poorten toetsbaar op deze velden"]
    fails = [f"{g.k} {g.label}" for g in GATES if p.get(g.k.lower() + "_ok") is False]
    return (not fails), fails


def parcel_flags(p: dict, intent: Intent = "dehesa",
                 min_ha: float = MIN_HA_FALLBACK) -> list[dict]:
    """Voorwaarden en kostenposten. Geen afwijzingen."""
    out: list[dict] = []
    ha = p.get("ha") or 0
    if ha and ha < min_ha:
        out.append({"k": "K3", "category": "score",
                    "note": "een jaar terugkooprecht van aangrenzende eigenaren"})
    juris = p.get("jurisdiction") or p.get("region_code")
    if juris == BY_K["K2"].jurisdiction and ha > 100:
        out.append({"k": "K2", "category": "cond",
                    "note": ("beweidings- of kurkverplichting op 80 procent van het "
                             "potentieel") if intent == "dehesa" else
                            "strijdig met strikt niet-ingrijpen"})
    if ha > 400:
        out.append({"k": "K8", "category": "score",
                    "note": "verplicht brandpreventieplan, herziening elke vier jaar"})
    return out


def candidate_window(intent: Intent = "dehesa") -> tuple[float, float]:
    """De oppervlaktevensters die de longlist tot een kandidatenlijst maakten.

    rewild: 16 tot 100 ha, want K2 bindt hier wel: strikt niet-ingrijpen boven
            100 ha beweidbaar is in Extremadura in strijd met Ley 1/1986.
    dehesa: 16 tot 400 ha.

    De bovengrens van 400 komt uit K8, en daar zit een inconsistentie: het model
    noemt K8 een scorepost, maar de eerdere telling van 22 kandidaten behandelde
    het als uitsluiting. Beide getallen worden gerapporteerd, niet een stil gekozen.
    """
    return (MIN_HA_FALLBACK, 100.0) if intent == "rewild" else (MIN_HA_FALLBACK, 400.0)


def profile_match(p: dict, lo: float = PROFILE_HA[0], hi: float = PROFILE_HA[1]) -> str:
    ha = p.get("ha")
    if ha is None:
        return "unknown"
    return "small" if ha < lo else ("large" if ha > hi else "fit")


def readiness(cells: Iterable[dict], var_comparable: dict[str, bool],
              thresholds=(80, 100, 95)) -> dict:
    """Dezelfde rekensom als de poort op de site, maar over echte observaties."""
    cells = list(cells)
    n = len(cells)
    present = [c for c in cells if c["quality"] != "mis"]
    ver = [c for c in present if c["quality"] == "ver"]
    vars_ = set(c["variable"] for c in cells)
    cmp_ok = sum(1 for v in vars_ if var_comparable.get(v))
    rel = round(100 * len(ver) / len(present)) if present else 0
    cmp_pct = round(100 * cmp_ok / len(vars_)) if vars_ else 0
    cov = round(100 * len(present) / n) if n else 0
    tr, tc, tv = thresholds
    return {"cells": n, "present": len(present), "verified": len(ver),
            "reliable_pct": rel, "comparable_pct": cmp_pct, "complete_pct": cov,
            "gate_open": rel >= tr and cmp_pct >= tc and cov >= tv}
