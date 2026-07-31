"""Tests op de handmatige inname.

De regel is dezelfde als voor advertenties: geen herkomst, geen inname. Wat hier
getest wordt is dat die regel ook echt bijt, en niet alleen in een README staat.
"""
import json
from pathlib import Path

import pytest

from terra import manual


@pytest.fixture
def drop(tmp_path):
    (tmp_path / "zones.geojson").write_text('{"type":"FeatureCollection","features":[]}')
    return tmp_path


def entry(**kw):
    # Een bron die in het register als handmatig staat. effis-fires staat daar
    # (nog) als automatiseerbaar, en dan eist de keuring terecht een bewuste keuze.
    basis = {"file": "zones.geojson", "source_id": "zar-fire-zones",
             "origin": "extremambiente.juntaex.es, per e-mail opgevraagd",
             "obtained_at": "2026-07-31", "obtained_by": "Stefan"}
    basis.update(kw)
    return basis


def test_zonder_herkomst_komt_er_niets_in(drop):
    for ontbreekt in ("origin", "obtained_at", "obtained_by"):
        e = entry(); e.pop(ontbreekt)
        ok, fouten = manual.keur(e, drop)
        assert ok is False and any(ontbreekt in f for f in fouten)


def test_onbekende_bron_wordt_geweigerd(drop):
    ok, fouten = manual.keur(entry(source_id="verzonnen-bron"), drop)
    assert ok is False and any("onbekende bron" in f for f in fouten)


def test_automatiseerbare_bron_vraagt_een_bewuste_keuze(drop):
    """Een bron die automatisch kan met de hand innemen betekent dat je de herkomst
    van een download vervangt door die van een mens. Mag, maar niet per ongeluk."""
    ok, fouten = manual.keur(entry(source_id="gisco-lau"), drop)
    assert ok is False and any("bewust_handmatig" in f for f in fouten)
    ok, _ = manual.keur(entry(source_id="gisco-lau", bewust_handmatig=True), drop)
    assert ok is True


def test_ontbrekend_bestand_wordt_gemeld(drop):
    ok, fouten = manual.keur(entry(file="bestaat-niet.geojson"), drop)
    assert ok is False and any("niet gevonden" in f for f in fouten)


def test_de_hash_maakt_het_manifest_falsifieerbaar(drop):
    """Zonder deze controle is het manifest een bewering; met deze controle is het
    een bewering die je kunt weerleggen."""
    e = entry()
    manual.stempel([e], drop)
    assert len(e["sha256"]) == 64
    ok, _ = manual.keur(e, drop)
    assert ok is True

    (drop / "zones.geojson").write_text('{"type":"FeatureCollection","features":[1]}')
    ok, fouten = manual.keur(e, drop)
    assert ok is False and any("sha256" in f for f in fouten)


def test_een_bestaande_hash_wordt_nooit_overschreven(drop):
    """Anders zet de stempelstap de controle uit op precies het moment dat hij
    zou aanslaan."""
    e = entry(sha256="0" * 64)
    manual.stempel([e], drop)
    assert e["sha256"] == "0" * 64


def test_datum_in_de_toekomst_is_geen_datum(drop):
    ok, fouten = manual.keur(entry(obtained_at="2099-01-01"), drop)
    assert ok is False and any("toekomst" in f for f in fouten)
    ok, fouten = manual.keur(entry(obtained_at="gisteren"), drop)
    assert ok is False and any("jjjj-mm-dd" in f for f in fouten)


def test_de_brandbron_wisselt_van_lijst_als_de_sonde_dat_zegt(drop):
    """effis-fires staat nu als automatiseerbaar in het register, dus de keuring
    eist een bewuste keuze. Blijkt het endpoint alleen via een aanvraagformulier te
    lopen, dan verhuist die vlag naar false en gaat dit bestand er vanzelf in. De
    inname hoeft daar niets voor te weten."""
    ok, fouten = manual.keur(entry(source_id="effis-fires"), drop)
    assert ok is False and any("bewust_handmatig" in f for f in fouten)
    ok, _ = manual.keur(entry(source_id="effis-fires", bewust_handmatig=True), drop)
    assert ok is True


def test_bron_zonder_inname_wordt_niet_stil_genegeerd(drop):
    """Niet elke bron heeft een inname, en dat hoort zichtbaar te zijn.

    station-normals is het voorbeeld: die stond eerder ten onrechte onder de vlag
    van CHELSA en is er bewust uit gehaald. Er is geen reden om hem opnieuw in te
    lezen, maar als iemand het toch probeert hoort dat in een lijst te belanden en
    niet in de prullenbak."""
    e = entry(source_id="station-normals")
    manual.stempel([e], drop)
    uit = manual.innemen(None, [e], drop)
    assert uit["zonder_handler"] and not uit["geweigerd"]
    assert uit["zonder_handler"][0]["source_id"] == "station-normals"


def test_het_lege_manifest_in_de_repo_is_geldig():
    entries = manual.lees_manifest()
    assert isinstance(entries, list)
    for e in entries:
        ok, fouten = manual.keur(e)
        assert ok, (e.get("file"), fouten)
