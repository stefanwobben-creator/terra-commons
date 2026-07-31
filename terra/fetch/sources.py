"""Kandidaat-URL's per bron, met meer dan een per bron.

Waarom een lijst en geen constante: deze werkomgeving heeft geen uitgaand netwerk
naar GISCO, CHELSA, EFFIS of het CNIG, dus geen van deze adressen is hier
geverifieerd. De sonde draait waar wel netwerk is (de CI-runner) en rapporteert
welke werkt. Pas daarna wordt er iets opgehaald.

Dat is geen omweg. Een downloader die een geraden URL aanneemt en faalt in een
parser kost meer tijd dan een sonde die in tien seconden zegt wat er staat.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Candidate:
    url: str
    note: str = ""


@dataclass
class FetchSource:
    id: str                       # verwijst naar source.id in de database
    what: str
    candidates: list[Candidate] = field(default_factory=list)
    parser: str | None = None


# LAU = Local Administrative Unit, het EU-brede equivalent van een gemeente.
# GISCO publiceert per jaargang, per formaat, per CRS en per resolutie. Welke
# combinatie er nu staat weten we niet zeker, vandaar meerdere gokken.
LAU = FetchSource(
    "gisco-lau", "gemeentegrenzen", parser="terra.fetch.lau",
    candidates=[
        Candidate("https://gisco-services.ec.europa.eu/distribution/v2/lau/geojson/"
                  "LAU_RG_01M_2021_3035.geojson", "jaargang 2021, 1:1M, EPSG:3035"),
        Candidate("https://gisco-services.ec.europa.eu/distribution/v2/lau/geojson/"
                  "LAU_RG_01M_2023_3035.geojson", "jaargang 2023"),
        Candidate("https://gisco-services.ec.europa.eu/distribution/v2/lau/"
                  "datasets.json", "index van beschikbare jaargangen en formaten"),
        Candidate("https://ec.europa.eu/eurostat/web/gisco/geodata/"
                  "local-administrative-units", "landingspagina, voor als de rest faalt"),
    ])

# Nationale grenzen als terugval: fijner en betrouwbaarder dan GISCO, maar per land
# een ander formaat, dus meer werk. Alleen gebruiken als LAU niet lukt.
LAU_ES = FetchSource(
    "ign-lineas-limite", "gemeentegrenzen Spanje", parser="terra.fetch.lau",
    candidates=[
        Candidate("https://centrodedescargas.cnig.es/CentroDescargas/"
                  "documentos/LineasLimite.zip", "IGN Lineas Limite, nationaal"),
    ])

CLIMATE = FetchSource(
    "chelsa-climate", "neerslag en temperatuur, uniforme referentieperiode",
    candidates=[
        Candidate("https://os.zhdk.cloud.switch.ch/chelsav2/GLOBAL/climatologies/"
                  "1981-2010/bio/CHELSA_bio12_1981-2010_V.2.1.tif",
                  "bio12 = jaarneerslag, 1 km, periode 1981-2010"),
        Candidate("https://archive.open-meteo.com/v1/archive?latitude=39.5&longitude=-6.0"
                  "&start_date=1991-01-01&end_date=2020-12-31&daily=precipitation_sum"
                  "&timezone=UTC",
                  "lichtgewicht alternatief: per punt in plaats van een raster van "
                  "honderden MB. Geen sleutel nodig. Kost wel een bevraging per "
                  "gemeente, en levert een puntwaarde en geen bereik"),
    ])

FIRES = FetchSource(
    "effis-fires", "brandperimeters, meerjarig",
    candidates=[
        Candidate("https://maps.effis.emergency.copernicus.eu/gwis?service=WFS&version=2.0.0"
                  "&request=GetCapabilities", "WFS-capabilities: hier staat de echte laagnaam in"),
        Candidate("https://forest-fire.emergency.copernicus.eu/apps/data.request.form/",
                  "aanvraagformulier, als de WFS dicht is"),
    ])

ALL = [LAU, LAU_ES, CLIMATE, FIRES]


def all_candidates() -> list[tuple[str, str, str]]:
    return [(s.id, c.url, c.note) for s in ALL for c in s.candidates]
