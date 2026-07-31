"""Tests op handmatige verrijking als tabel.

Uitgangspunt: verzamelen en verrijken mag altijd, en mag nooit blokkeren. Deze
tests leggen vast wat dat concreet betekent.
"""
import pytest

from terra import db, enrich

CSV = """gemeente;variabele;waarde;eenheid;kwaliteit;opmerking
ES_10148;fiscal_min_eur_ha;1045;EUR/ha;ind;matorral, tabel 2021
ES_10149;fiscal_min_eur_ha;614;EUR/ha;ind;matorral
ES_99999;fiscal_min_eur_ha;800;EUR/ha;ind;bestaat niet
;fiscal_min_eur_ha;900;EUR/ha;ind;lege code
"""


@pytest.fixture
def c():
    try:
        with db.conn() as conn:
            for code in ("ES_10148", "ES_10149"):
                db.x(conn, """insert into municipality (code,region_code,name)
                              values (%s,'ext',%s)""", (code, code))
            yield conn
            conn.rollback()
    except Exception as e:
        if "connect" in str(e).lower():
            pytest.skip(f"geen database: {e}")
        raise


def test_puntkomma_en_nederlandse_kopjes(tmp_path):
    """Een mens die een CSV maakt is geen API. Excel in Nederland levert
    puntkomma's en Nederlandse kolomnamen."""
    t = enrich.lees_tabel(CSV)
    assert len(t["rows"]) == 3               # de regel met lege code valt af
    assert t["rows"][0]["subject_id"] == "ES_10148"
    assert t["rows"][0]["value_num"] == 1045.0
    assert t["rows"][0]["subject_type"] == "municipality"   # standaard


def test_lege_regel_valt_af_met_een_reden():
    t = enrich.lees_tabel(CSV)
    assert t["afgekeurd"] and "leeg" in t["afgekeurd"][0]["reden"]


def test_ontbrekende_kolom_is_een_leesbare_fout():
    t = enrich.lees_tabel("van alles;maar niet;wat we zoeken\n1;2;3\n")
    assert "verplichte kolommen ontbreken" in t["fout"]
    assert t["gevonden_koppen"]


def test_gedeeltelijke_levering_is_geldig(c, tmp_path):
    """Veertig gemeenten van de 2.949 is geen mislukte upload maar precies wat je
    krijgt als iemand veertig PDF's heeft doorgeploegd."""
    p = tmp_path / "waarden.csv"; p.write_text(CSV)
    res = enrich.load(c, p, "ex-fiscal-values")
    assert res["weggeschreven"] == 2
    assert res["onbekend_onderwerp"] == 1


def test_onbekend_onderwerp_is_een_rapport_en_geen_fout(c, tmp_path):
    p = tmp_path / "waarden.csv"; p.write_text(CSV)
    res = enrich.load(c, p, "ex-fiscal-values")
    assert res["onbekende_voorbeelden"][0]["subject_id"] == "ES_99999"
    assert "fout" not in res


def test_handmatige_waarden_zijn_niet_vergelijkbaar(c, tmp_path):
    """Een overgetypte waarde is per definitie niet met dezelfde methode gemeten
    als de rest. Zou dat wel zo zijn, dan was er een bron geweest."""
    p = tmp_path / "waarden.csv"; p.write_text(CSV)
    enrich.load(c, p, "ex-fiscal-values")
    r = db.q(c, """select comparable, quality, source_id from observation
                   where subject_id='ES_10148' and variable='fiscal_min_eur_ha'""")[0]
    assert r["comparable"] is False
    assert r["quality"] == "ind"
    assert r["source_id"] == "ex-fiscal-values"


def test_een_leeg_bestand_blokkeert_niet(c, tmp_path):
    p = tmp_path / "leeg.csv"; p.write_text("gemeente;variabele;waarde\n")
    res = enrich.load(c, p, "ex-fiscal-values")
    assert res["regels"] == 0 and "note" in res and "fout" not in res


def test_komma_als_scheidingsteken_werkt_ook(c, tmp_path):
    p = tmp_path / "en.csv"
    p.write_text("code,variable,value,unit\nES_10148,umc_ha,8,ha\n")
    res = enrich.load(c, p, "umc-decreto-46-1997")
    assert res["weggeschreven"] == 1
    assert db.q(c, """select value_num from observation
                      where variable='umc_ha'""")[0]["value_num"] == 8.0


NAAM_CSV = """gemeente;regio;variabele;waarde;eenheid;kwaliteit
Cáceres;ext;umc_ha;10;ha;ind
Puebla de Sanabria, La;cyl;umc_ha;10;ha;ind
Dubbeldorp;;umc_ha;8;ha;ind
Bestaat Niet;ext;umc_ha;4;ha;ind
"""


@pytest.fixture
def namen(c):
    for code, naam, regio in (("ES_10037", "Cáceres", "ext"),
                              ("ES_49173", "Puebla de Sanabria, La", "cyl"),
                              ("ES_06001", "Dubbeldorp", "ext"),
                              ("ES_49001", "Dubbeldorp", "cyl")):
        db.x(c, """insert into municipality (code,region_code,name)
                   values (%s,%s,%s)""", (code, regio, naam))
    return c


def test_namen_worden_vergelijkbaar_gemaakt():
    """Accenten eraf, en het lidwoord van achter naar voren: Spaanse bronnen
    schrijven 'Puebla de Sanabria, La' waar een mens 'La Puebla de Sanabria' typt."""
    assert enrich.normaliseer("Cáceres") == "caceres"
    assert enrich.normaliseer("Puebla de Sanabria, La") == "la puebla de sanabria"
    assert enrich.normaliseer("  dubbele   spaties ") == "dubbele spaties"


def test_een_naam_wordt_opgezocht_en_de_opzoeking_gerapporteerd(namen, tmp_path):
    """Mensen typen namen, geen codes. Dat mag, maar je wilt achteraf kunnen zien
    wat er aan welke code is gekoppeld."""
    p = tmp_path / "umc.csv"; p.write_text(NAAM_CSV)
    res = enrich.load(namen, p, "umc-decreto-46-1997")
    codes = {o["code"] for o in res["opzoekingen"]}
    assert "ES_10037" in codes and "ES_49173" in codes
    assert res["opgezocht_op_naam"] == 2


def test_twee_treffers_is_geen_treffer(namen, tmp_path):
    """Spaanse gemeentenamen zijn niet uniek. Gokken zou data op de verkeerde plek
    zetten zonder dat iemand het merkt."""
    p = tmp_path / "umc.csv"; p.write_text(NAAM_CSV)
    res = enrich.load(namen, p, "umc-decreto-46-1997")
    assert res["dubbelzinnig"] and res["dubbelzinnig"][0]["ingevoerd"] == "Dubbeldorp"
    assert len(res["dubbelzinnig"][0]["kandidaten"]) == 2


def test_een_regio_erbij_lost_de_dubbelzinnigheid_op(namen):
    """Dezelfde naam, wel een regio: dan is er maar een kandidaat."""
    assert enrich.zoek_op_naam(namen, "Dubbeldorp")["status"] == "dubbelzinnig"
    uit = enrich.zoek_op_naam(namen, "Dubbeldorp", "cyl")
    assert uit["status"] == "gevonden" and uit["code"] == "ES_49001"


def test_onvindbare_naam_blijft_een_rapport(namen, tmp_path):
    p = tmp_path / "umc.csv"; p.write_text(NAAM_CSV)
    res = enrich.load(namen, p, "umc-decreto-46-1997")
    assert any(o["subject_id"] == "Bestaat Niet" for o in res["onbekende_voorbeelden"])
    assert "fout" not in res
