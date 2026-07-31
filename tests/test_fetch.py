"""Tests op het ophalen, zonder netwerk.

Wat hier getest wordt is de vertaalslag, niet de download. Dat is met opzet: de
parser hoort te kloppen voordat er ergens tientallen megabytes over de lijn gaan,
en een test die van een externe server afhangt is geen test maar een weerbericht.
"""
import json
from pathlib import Path

import pytest

from terra import db
from terra.fetch import base, lau
from terra.fetch.sources import ALL, all_candidates

FIX = Path(__file__).parent / "fixtures"


def test_srid_wordt_uit_de_getallen_afgeleid():
    """GISCO publiceert GeoJSON in EPSG:3035, wat tegen de conventie in gaat.
    Aan de coordinaten is te zien welke van de twee het is; aan de bestandsnaam
    niet betrouwbaar."""
    assert lau.detect_srid(lau.read(FIX / "lau_sample.geojson")) == 3035
    assert lau.detect_srid(lau.read(FIX / "lau_wgs84.geojson")) == 4326


def test_alleen_gemeenten_in_onze_regios():
    parsed = lau.to_rows(lau.read(FIX / "lau_sample.geojson"))
    codes = sorted(r["code"] for r in parsed["rows"])
    assert codes == ["TEST_CYL_1", "TEST_EXT_1"]
    assert {r["region_code"] for r in parsed["rows"]} == {"ext", "cyl"}


def test_wat_afvalt_wordt_geteld_en_niet_verzwegen():
    parsed = lau.to_rows(lau.read(FIX / "lau_sample.geojson"))
    assert sum(parsed["skipped"].values()) == 2
    assert any("FR" in k for k in parsed["skipped"])
    assert "zonder code of geometrie" in parsed["skipped"]


def test_parser_zegt_welke_veldnamen_hij_gebruikte():
    """Wij weten niet zeker hoe GISCO zijn velden noemt in de jaargang die straks
    binnenkomt. Dan is 'welke kolom heb je gepakt' een vraag met een antwoord."""
    used = lau.to_rows(lau.read(FIX / "lau_sample.geojson"))["fields_used"]
    assert used["id"] == "GISCO_ID" and used["nuts"] == "NUTS3_CODE"


def test_elke_bron_heeft_meer_dan_een_kandidaat_of_een_reden():
    for s in ALL:
        assert s.candidates, s.id
        assert all(c.url.startswith("https://") for c in s.candidates), s.id
    assert len(all_candidates()) >= 8


def test_sonde_geeft_een_leesbare_regel_bij_een_dood_adres():
    p = base.probe("https://terra-commons.invalid/bestaat-niet")
    assert p.ok is False and p.error
    assert "FOUT" in p.line()


def test_gemeente_belandt_in_de_database_met_oppervlakte():
    """Alleen over de eigen twee rijen, niet over de hele tabel.

    Deze test faalde toen de echte gemeentelaag er eenmaal in zat: hij ging ervan
    uit dat de tabel leeg was. Een test die aanneemt dat hij alleen op de wereld is,
    werkt tot het moment dat het project begint te werken.
    """
    try:
        with db.conn() as c:
            r = lau.load(c, FIX / "lau_sample.geojson")
            assert r["inserted"] == 2 and r["srid"] == 3035
            rows = db.q(c, """select code, region_code, round(area_ha) ha
                              from municipality where code like 'TEST\\_%%'
                              order by code""")
            assert [x["code"] for x in rows] == ["TEST_CYL_1", "TEST_EXT_1"]
            assert [x["region_code"] for x in rows] == ["cyl", "ext"]
            # 4 km bij 4 km is 1.600 ha, 3 bij 3 is 900 ha, gelijkoppervlakte-CRS
            assert [int(x["ha"]) for x in rows] == [1600, 900]
            c.rollback()
    except Exception as e:
        if "connection" in str(e).lower() or "connect" in str(e).lower():
            pytest.skip(f"geen database: {e}")
        raise


def test_regio_uit_de_gemeentecode_als_nuts_ontbreekt():
    """Tweede weg naar dezelfde regio. Een INE-code is vijf cijfers waarvan de
    eerste twee de provincie zijn, en provincies liggen vast binnen een regio."""
    assert lau._region_from_code("ES_10148", "ES") == "ext"   # Caceres
    assert lau._region_from_code("49177", "ES") == "cyl"      # Zamora
    assert lau._region_from_code("ES_28079", "ES") is None    # Madrid, niet van ons
    assert lau._region_from_code("FR_75056", "FR") is None


def test_nul_herkende_gemeenten_levert_een_diagnose():
    """Zonder dit is een mislukte run alleen 'nul gemeenten' en moet je zelf
    123 MB gaan openen."""
    vreemd = [{"properties": {"MUNI_CODE": "X", "MUNI_NAAM": "Y"},
               "geometry": {"type": "Point", "coordinates": [0, 0]}}]
    d = lau.to_rows(vreemd)
    assert not d["rows"] and "diagnose" in d
    assert d["diagnose"]["beschikbare_velden"] == ["MUNI_CODE", "MUNI_NAAM"]
    assert "gezocht_naar" in d["diagnose"]
