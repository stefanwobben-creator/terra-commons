"""Kandidaat-URL's per bron, met meer dan een per bron.

Waarom een lijst en geen constante: de werkomgeving waarin deze code geschreven is
heeft geen uitgaand netwerk. De sonde draait waar dat wel is (de Actions-runner) en
rapporteert wat er staat. Pas daarna wordt er iets opgehaald.

**Uitslag van de eerste sonde, 31 juli 2026, GitHub-runner.**

    OK    GISCO LAU 2021   122,8 MB   application/geo+json
    OK    GISCO LAU 2023   123,0 MB   application/geo+json    <- gebruiken we
    OK    GISCO datasets.json          application/json
    OK    CHELSA bio12     655,2 MB   image/tiff              <- jaarneerslag, 1 km
    FOUT  CNIG LineasLimite            HTTP 404
    FOUT  archive.open-meteo.com       DNS: hostnaam bestaat niet (was archive-api)
    ?     EFFIS WFS        0,0 MB     text/html               <- 200, maar geen XML

Die laatste is het interessante geval. Een GetCapabilities hoort XML te geven; een
200 met text/html en nul bytes betekent dat we een pagina kregen en geen document.
"Bereikbaar" is dus niet hetzelfde als "bruikbaar", en daarom kan de sonde sinds
deze ronde ook in de inhoud kijken (`--peek`).
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
                  "LAU_RG_01M_2023_3035.geojson",
                  "GEVERIFIEERD 31-07-2026: 123,0 MB, application/geo+json. Standaard."),
        Candidate("https://gisco-services.ec.europa.eu/distribution/v2/lau/geojson/"
                  "LAU_RG_01M_2021_3035.geojson",
                  "GEVERIFIEERD: 122,8 MB. Terugval als 2023 iets raars doet."),
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
                  "GEVERIFIEERD 31-07-2026: 655,2 MB, image/tiff. Jaarneerslag, 1 km, "
                  "uniforme periode 1981-2010. Dit lost de vergelijkbaarheidsfout op."),
        Candidate("https://os.zhdk.cloud.switch.ch/chelsav2/GLOBAL/climatologies/"
                  "1981-2010/bio/CHELSA_bio1_1981-2010_V.2.1.tif",
                  "bio1 = jaargemiddelde temperatuur, zelfde raster, voor later"),
        Candidate("https://archive-api.open-meteo.com/v1/archive?latitude=39.5"
                  "&longitude=-6.0&start_date=2020-01-01&end_date=2020-12-31"
                  "&daily=precipitation_sum&timezone=UTC",
                  "hostnaam gecorrigeerd: archive-api, niet archive. Alleen nodig als "
                  "het raster wegvalt; levert een puntwaarde en geen bereik"),
    ])

FIRES = FetchSource(
    "effis-fires", "brandperimeters, meerjarig",
    candidates=[
        Candidate("https://maps.effis.emergency.copernicus.eu/gwis?service=WFS&version=2.0.0"
                  "&request=GetCapabilities",
                  "gaf 200 met text/html, dus vermoedelijk een pagina en geen XML. "
                  "Draai de sonde met --peek om te zien wat er echt terugkomt."),
        Candidate("https://maps.effis.emergency.copernicus.eu/effis?service=WFS&version=2.0.0"
                  "&request=GetCapabilities", "andere endpointnaam: effis in plaats van gwis"),
        Candidate("https://maps.effis.emergency.copernicus.eu/gwis?service=WMS&version=1.3.0"
                  "&request=GetCapabilities", "WMS in plaats van WFS, voor de laagnamen"),
        Candidate("https://forest-fire.emergency.copernicus.eu/apps/data.request.form/",
                  "aanvraagformulier: als dit de enige weg is, is brand handmatig werk "
                  "en hoort het in v_manual_debt en niet in een fetcher"),
    ])

ALL = [LAU, LAU_ES, CLIMATE, FIRES]


def all_candidates() -> list[tuple[str, str, str]]:
    return [(s.id, c.url, c.note) for s in ALL for c in s.candidates]
