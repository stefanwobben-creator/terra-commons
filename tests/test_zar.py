"""Tests op de ZAR-levering.

Deze levering is anders dan alle andere: hij komt niet uit een bestand met een
narekenbare herkomst maar uit een taalmodel dat een PDF heeft overgetypt. Dat mag,
maar dan moet het onderscheid hard in de data staan en niet in een leesmij.

Wat hier bewaakt wordt is dus niet of de gemeenten kloppen (dat kan alleen een mens
die Anexo I ernaast legt) maar of de levering blijft toegeven dat ze niet nagekeken
zijn. De verleiding om `ind` een keer op `ver` te zetten omdat het toch wel goed zal
zijn, is precies de fout waar de kwaliteitscode voor bestaat.
"""
import csv
from pathlib import Path

import pytest

from terra import manual

CSV = Path(__file__).resolve().parent.parent / "manual" / "zar-extremadura.csv"
WAARSCHUWING = CSV.parent / "ZAR-WAARSCHUWING.md"


@pytest.fixture(scope="module")
def rijen():
    if not CSV.exists():
        pytest.skip("manual/zar-extremadura.csv bestaat niet")
    with CSV.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_niets_doet_zich_voor_als_geverifieerd(rijen):
    """De enige test die er echt toe doet zolang niemand Anexo I heeft nagelezen."""
    fout = {r["quality"] for r in rijen} - {"ind"}
    assert not fout, (
        f"kwaliteitscodes anders dan 'ind' in de ZAR-levering: {fout}. "
        f"Zet dit pas om als iemand Anexo I ernaast heeft gelegd; zie "
        f"manual/ZAR-WAARSCHUWING.md")


def test_elke_gemeente_heeft_zowel_de_vlag_als_de_zone(rijen):
    """Een gemeente met `zar` maar zonder `zar_zone` is niet na te lopen: je weet dan
    wel dat hij in een zone ligt maar niet in welke, en dus ook niet waar je moet
    kijken om het te controleren."""
    per = {}
    for r in rijen:
        per.setdefault(r["subject_id"], set()).add(r["variable"])
    scheef = {k: sorted(v) for k, v in per.items() if v != {"zar", "zar_zone"}}
    assert not scheef, f"gemeenten met een onvolledig paar: {scheef}"


def test_de_waarschuwing_bestaat_en_wordt_aangewezen():
    """Een levering met dit soort herkomst zonder de waarschuwing ernaast is erger
    dan geen levering: hij ziet er dan uit als de rest."""
    assert WAARSCHUWING.exists(), "manual/ZAR-WAARSCHUWING.md ontbreekt"
    entries = [e for e in manual.lees_manifest() if e.get("source_id") == "zar-fire-zones"]
    assert entries, "de ZAR-levering staat niet in het manifest"
    for e in entries:
        assert "ZAR-WAARSCHUWING" in (e.get("note") or ""), (
            "de manifestregel wijst niet naar de waarschuwing")


def test_de_manifestregel_komt_door_de_keuring():
    """Herkomst, datum en wie: dezelfde eis als voor advertenties. Een bestand dat
    ik zelf heb neergezet is geen reden om die eis te laten vallen."""
    for e in manual.lees_manifest():
        if e.get("source_id") != "zar-fire-zones":
            continue
        ok, fouten = manual.keur(e)
        assert ok, f"de ZAR-levering komt niet door de keuring: {fouten}"


def test_een_levering_die_niets_raakt_stempelt_niet_af():
    """De fout die deze levering zelf blootlegde.

    De ZAR-CSV verwijst naar gemeenten op naam. Staat de gemeentelaag niet in de
    database, dan komt er nul binnen. De inname stempelde toch `last_run`, waarmee de
    bron uit de lijst met openstaand handwerk verdween: aangeboden werd gelezen als
    voldaan. Precies andersom.
    """
    assert manual.landde({"weggeschreven": 12}) is True
    assert manual.landde({"weggeschreven": 0, "onbekend_onderwerp": 404}) is False
    # Genest, zoals de brandhandler die zijn tellingen onder 'rates' zet.
    assert manual.landde({"perimeters": 0, "rates": {"observaties": 7}}) is True
    assert manual.landde({"perimeters": 0, "rates": {"observaties": 0}}) is False
    assert manual.landde("geen dict") is False
