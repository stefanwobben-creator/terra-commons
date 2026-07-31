"""Twee scores, twee eenheden van analyse. Bewust in een bestand zodat de
verwarring die ze eerder veroorzaakten hier zichtbaar naast elkaar staat.

Regiofilter: vier componenten van elk 25 punten (A water, E recht, F verwerving,
G brand). Een regio is een filter, geen aankoop.

Perceelscore: zeven dimensies. Dit is wat je koopt.

Beide leveren een score plus de lijst dimensies die niet te berekenen waren. Een
score zonder die lijst is een halve waarheid.
"""
from __future__ import annotations

from typing import Iterable

REGION_COMPONENTS = {"A": "waterbalans", "E": "recht", "F": "verwerving", "G": "brand"}
REGION_MAX = 25

PARCEL_DIMS = {
    "A": ("water, aanvoer en recht", 30),
    "B": ("vasthouden, relief en bodemdiepte", 15),
    "C": ("bodem, textuur en organische stof", 15),
    "D": ("deltaruimte, herstelpotentieel", 25),
    "E": ("titel en toegang", 15),
    "F": ("verwervingskosten", 20),
    "G": ("brandrisico", 15),
}
PARCEL_TOTAL = sum(w for _, w in PARCEL_DIMS.values())
PARCEL_TOTAL_DOCUMENTED = 100     # wat paragraaf 2 van het model belooft


def weight_audit() -> dict:
    """De gewichten tellen op tot 135, terwijl het model 100 punten belooft.

    Niet stil rechttrekken. Twee uitwegen die verschillende antwoorden geven: de
    gewichten herwegen naar 100, of het model bijstellen naar 135. Zolang die
    keuze niet gemaakt is, rapporteert elke perceelscore het gemeten maximum en
    niet een percentage van een verzonnen noemer.
    """
    return {"sum": PARCEL_TOTAL, "documented": PARCEL_TOTAL_DOCUMENTED,
            "delta": PARCEL_TOTAL - PARCEL_TOTAL_DOCUMENTED,
            "consistent": PARCEL_TOTAL == PARCEL_TOTAL_DOCUMENTED}


def region_score(components: dict[str, float | None]) -> dict:
    known = {k: v for k, v in components.items() if v is not None}
    missing = sorted(k for k in REGION_COMPONENTS if components.get(k) is None)
    measured_max = REGION_MAX * len(known)
    return {
        "points": sum(known.values()),
        "measured_max": measured_max,
        "nominal_max": REGION_MAX * len(REGION_COMPONENTS),
        "pct_of_measured": round(100 * sum(known.values()) / measured_max) if measured_max else None,
        "missing": missing,
        "comparable": not missing,
    }


def tipping_point(components: dict[str, float | None], rival_total: float) -> float | None:
    """Bij welke waarde van de ontbrekende component kantelt de rangorde?

    Voor precies de situatie die de eerste top twee onbetrouwbaar maakte:
    Extremadura stond eerste met een leeg brandvak.
    """
    missing = [k for k in REGION_COMPONENTS if components.get(k) is None]
    if len(missing) != 1:
        return None
    have = sum(v for v in components.values() if v is not None)
    need = rival_total - have
    return None if need <= 0 else min(need, REGION_MAX)


def delta_per_price(delta_points: float, eur_per_ha: float) -> float | None:
    """De beslissende verhouding: herstelruimte per duizend euro per hectare.

    Je koopt geen kwaliteit, je koopt ruimte om kwaliteit te maken.
    """
    if not eur_per_ha:
        return None
    return round(delta_points / (eur_per_ha / 1000), 2)


def parcel_score(obs: dict[str, float | None]) -> dict:
    """Verwacht per dimensieletter een waarde van 0 tot 1, of None."""
    got = {k: v for k, v in obs.items() if v is not None and k in PARCEL_DIMS}
    pts = sum(PARCEL_DIMS[k][1] * v for k, v in got.items())
    measured_max = sum(PARCEL_DIMS[k][1] for k in got)
    missing = sorted(k for k in PARCEL_DIMS if obs.get(k) is None)
    return {"points": round(pts, 1), "measured_max": measured_max,
            "nominal_max": PARCEL_TOTAL,
            "pct_of_measured": round(100 * pts / measured_max) if measured_max else None,
            "missing": missing, "scorable": len(missing) == 0}


def transaction_cost(price_eur: float, n_fincas: int = 1, itp_pct: float = 8.0,
                     registry_min_eur: float = 24.04,
                     notary_per_finca_eur: float = 40.0) -> dict:
    """Transactiekosten schalen met het AANTAL fincas, niet alleen met de prijs.

    Toegevoegd na Rionegro del Puente: 21,2 ha voor 34.500 euro klonk als 1.627
    EUR/ha, maar het waren 260 aparte parcelas. Inschrijving gaat per finca met een
    minimum van 24,04 euro (RD 1427/1989), plus notariskosten per finca. De
    standaard van 9 tot 10 procent uit het model zat daar een factor vijf naast.
    """
    itp = price_eur * itp_pct / 100
    registry = registry_min_eur * n_fincas
    notary = notary_per_finca_eur * n_fincas
    extra = itp + registry + notary
    return {"itp": round(itp), "registry": round(registry), "notary": round(notary),
            "extra_total": round(extra),
            "extra_pct_of_price": round(100 * extra / price_eur, 1) if price_eur else None,
            "n_fincas": n_fincas}


def fire_base_rate(burned_ha_per_year: Iterable[float], area_ha: float) -> dict:
    """Meerjarig gemiddelde, niet een jaartotaal.

    De correctie die de vergelijking tussen Extremadura en Castilla y Leon omgooide:
    een staartjaar zei niets. Het terugkeerinterval is de leesbare vorm.
    """
    years = list(burned_ha_per_year)
    if not years or not area_ha:
        return {"rate_pct": None, "return_years": None, "n_years": len(years)}
    rate = sum(years) / len(years) / area_ha
    return {"rate_pct": round(100 * rate, 3),
            "return_years": round(1 / rate) if rate else None,
            "n_years": len(years)}
