"""Bronregister. Het eerlijke hart van het woord 'automatisch'.

Elke bron draagt twee velden die bepalen wat een nachtelijke taak wel en niet kan:
`automatable` (kan een machine dit ophalen) en `cadence` (hoe vaak verandert het).
De uitkomst is nuchter: van de drie echte poorten zijn er twee automatiseerbaar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .criteria import GATES


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    tier: str
    cadence: str
    automatable: bool
    url: Optional[str] = None
    licence: Optional[str] = None
    covers: tuple[str, ...] = ()
    notes: Optional[str] = None
    # Wat deze bron oplevert zodra hij binnen is. Staat hier en niet op de site,
    # zodat er een plek is waar het antwoord leeft in plaats van twee.
    unlocks: Optional[str] = None
    unlocks_en: Optional[str] = None


SOURCES: tuple[Source, ...] = (
    Source("legal-country", "Wetteksten per land (BOE, DRE, Monitorul, DV)", "country",
           "once", False, covers=("buy_allowed", "buy_conditions", "use_obligation",
                                  "exit_levy_pct"),
           notes="lezen en uitleggen is mensenwerk; lex.bg blokkeert bovendien",
           unlocks=("De landpoort per land. Voor Spanje rond; alleen Bulgarije is nooit gelezen, en dat land staat buiten de scope."),
           unlocks_en=("The country gate. Settled for Spain; only Bulgaria was never read, and it is out of scope.")),
    Source("eurostat-lprc", "Eurostat land prices and rents", "region", "annual", True,
           url="https://ec.europa.eu/eurostat/web/agriculture/database",
           licence="Eurostat open", covers=("price_eur_ha",)),
    Source("mapa-tierra", "MAPA encuesta de precios de la tierra", "region", "annual",
           True, url="https://www.mapa.gob.es", covers=("price_eur_ha_class",)),
    Source("station-normals", "Stationsnormalen uit nationale weerdiensten", "region",
           "on_demand", False, covers=("rain_mm",),
           notes=("handmatig verzamelde normalen met verschillende referentieperioden "
                  "(1981-2010 naast 1991-2020 naast een reeks 2014-2026). Dit is de bron "
                  "die neerslag onvergelijkbaar maakt, en hij hoorde niet onder de vlag "
                  "van CHELSA te staan"),
           unlocks=("Niets meer. Vervangen door het raster; staat er nog om te laten zien waar de oude regiocijfers vandaan kwamen."),
           unlocks_en=("Nothing anymore. Superseded by the raster; kept to show where the old regional figures came from.")),
    Source("chelsa-climate", "CHELSA V2 klimaatraster 1 km", "region", "once", True,
           url="https://chelsa-climate.org", licence="CC BY 4.0",
           covers=("rain_mm", "tmax_summer", "frost_days"),
           notes="uniforme referentieperiode; lost de vergelijkbaarheidsfout op"),
    Source("effis-fires", "EFFIS brandperimeters", "region", "seasonal", True,
           url="https://effis.jrc.ec.europa.eu", covers=("burned_ha", "fire_base_rate"),
           unlocks=("De cel die de rangorde Extremadura tegen Castilla y Leon beslecht. Wacht op de sonde."),
           unlocks_en=("The cell that settles Extremadura versus Castilla y Leon. Waiting on the probe.")),
    Source("gisco-lau", "GISCO LAU gemeentegrenzen", "municipality", "annual", True,
           url="https://ec.europa.eu/eurostat/web/gisco", covers=("geom", "area_ha")),
    Source("ign-lineas-limite", "IGN Lineas Limite", "municipality", "annual", True,
           url="https://centrodedescargas.cnig.es", covers=("geom",)),
    Source("ex-fiscal-values", "Valores fiscales minimos Extremadura", "municipality",
           "on_demand", False, covers=("fiscal_min_eur_ha",),
           notes="per gemeente per gewasklasse gepubliceerd, als PDF",
           unlocks=("Prijs per gemeente in plaats van per regio. Let op: een fiscale ondergrens, geen marktprijs."),
           unlocks_en=("Price per municipality instead of per region. Note: a tax floor, not a market price.")),
    Source("umc-decreto-46-1997", "Unidad minima de cultivo, Decreto 46/1997",
           "municipality", "once", False, covers=("umc_ha",),
           notes="bijlage met gemeentegroepen alleen als DOE-PDF",
           unlocks=("K3 exact per gemeente in plaats van de landelijke terugval van 16 ha. Een bijlage dekt heel Extremadura."),
           unlocks_en=("K3 exact per municipality instead of the national fallback of 16 ha. One annex covers all of Extremadura.")),
    Source("zar-fire-zones", "Zonas de Alto Riesgo de incendio", "municipality",
           "on_demand", False, covers=("zar",),
           unlocks=("De drempel van K8 per gemeente: boven 200 ha in een risicozone in plaats van boven 400 ha overal."),
           unlocks_en=("The K8 threshold per municipality: above 200 ha in a risk zone instead of above 400 ha everywhere.")),
    Source("ibi-ordenanzas", "Gemeentelijke IBI-verordeningen", "municipality",
           "annual", False, covers=("ibi_pct",),
           unlocks=("Het jaarlijkse tarief per gemeente. Mogelijk helemaal geen handwerk: het ministerie publiceert dit centraal."),
           unlocks_en=("The annual rate per municipality. Possibly no handwork at all: the ministry publishes this centrally.")),
    Source("sigpac-recintos", "SIGPAC recintos", "parcel", "annual", True,
           url="https://sigpac-hubcloud.es", licence="CC BY 4.0",
           covers=("geom", "ha", "slope_pct", "altitude_m", "use_class")),
    Source("catastro-inspire", "Catastro INSPIRE parcelas", "parcel", "on_demand", True,
           url="https://www.catastro.hacienda.gob.es", covers=("refcat", "geom")),
    Source("miteco-vias-pecuarias", "MITECO vias pecuarias WMS", "parcel", "annual",
           True, covers=("k6_ok",)),
    Source("road-network", "Wegennet (IGN of OSM)", "parcel", "annual", True,
           covers=("k4_ok",), notes="benadering van K4; bevestiging blijft nodig"),
    Source("registro-propiedad", "Nota simple, Registro de la Propiedad", "parcel",
           "on_demand", False, covers=("k5_ok", "owner", "charges"),
           notes="per perceel aanvragen en betalen; dit is de poort die de nacht stopt",
           unlocks=("K5 per perceel, plus eigenaar en lasten. Dit is de poort die geen enkele automaat kan nemen."),
           unlocks_en=("K5 per parcel, plus owner and charges. This is the gate no automation can take.")),
    Source("listings", "Advertenties op portals", "parcel", "on_demand", False,
           covers=("price_eur", "listing_url"),
           notes="scrapen is in strijd met de voorwaarden; handmatig met URL en datum",
           unlocks=("De trechter terug op dertig waarnemingen, en vanaf dan prijsverloop in plaats van een momentopname."),
           unlocks_en=("The funnel back to thirty observations, and from then on price history instead of a snapshot.")),
)

BY_ID = {s.id: s for s in SOURCES}


def gate_automation() -> dict[str, bool]:
    """Per echte poort: is er een automatiseerbare bron die hem dekt?"""
    out = {}
    for g in GATES:
        field = g.k.lower() + "_ok"
        out[g.k] = any(s.automatable and field in s.covers for s in SOURCES)
    return out


def manual_debt() -> list[str]:
    return [s.id for s in SOURCES if not s.automatable]


def summary() -> dict:
    per_tier, per_cadence = {}, {}
    for s in SOURCES:
        per_tier[s.tier] = per_tier.get(s.tier, 0) + 1
        per_cadence[s.cadence] = per_cadence.get(s.cadence, 0) + 1
    return {
        "sources": len(SOURCES),
        "automatable": sum(1 for s in SOURCES if s.automatable),
        "manual": sum(1 for s in SOURCES if not s.automatable),
        "per_tier": per_tier,
        "per_cadence": per_cadence,
        "gates_automatable": gate_automation(),
    }
