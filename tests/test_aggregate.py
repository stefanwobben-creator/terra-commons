"""Tests op de afleiding van regiowaarden uit de gemeentelaag.

Bouwt zijn eigen kleine gemeentelaag op, met opzet ongelijke oppervlakten, zodat
het verschil tussen gewogen en ongewogen middelen zichtbaar wordt.
"""
import pytest

from terra import aggregate, db

GEMEENTEN = [("TT_1", "ext", 100_000, 1200.0),   # groot en nat
             ("TT_2", "ext", 1_000, 400.0),      # klein en droog
             ("TT_3", "cyl", 50_000, 700.0),
             ("TT_4", "cyl", 50_000, 500.0)]


@pytest.fixture
def c():
    """Alles in een transactie die aan het eind terugdraait.

    Eerder committe deze fixture zijn invoer, en dan bleven de regiowaarden die
    de afleiding schrijft achter in de database. Daar struikelde vervolgens de
    driftcontrole over, die site/data.json naast de database legt. Een test die
    sporen achterlaat is geen test maar een migratie.
    """
    try:
        with db.conn() as conn:
            for code, reg, ha, mm in GEMEENTEN:
                db.x(conn, """insert into municipality (code,region_code,name,area_ha)
                              values (%s,%s,%s,%s)""", (code, reg, code, ha))
                for var, val, der in (("rain_mm", mm, False),
                                      ("rain_mm_min", mm * 0.6, True),
                                      ("rain_mm_max", mm * 1.4, True)):
                    db.x(conn, """insert into observation (subject_type,subject_id,variable,
                                  value_num,unit,quality,comparable,source_id,observed_at,derived)
                                  values ('municipality',%s,%s,%s,'mm/jaar','ver',true,
                                  'chelsa-climate',current_date,%s)""", (code, var, val, der))
            yield conn
            conn.rollback()
    except Exception as e:
        if "connect" in str(e).lower():
            pytest.skip(f"geen database: {e}")
        raise


def test_regioneerslag_is_oppervlaktegewogen(c):
    """Een regio is geen verzameling gemeenten van gelijke grootte. Ongewogen zou
    Extremadura op 800 mm uitkomen, gewogen op 1.192. Dat is geen afronding."""
    per = {r["subject_id"]: float(r["value_num"]) for r in aggregate.region_rain(c)}
    assert round(per["ext"]) == 1192          # (1200*100000 + 400*1000) / 101000
    assert round(per["cyl"]) == 600           # gelijke oppervlakten, dus het midden
    assert per["ext"] != 800                  # het ongewogen gemiddelde


def test_afleiding_vermeldt_de_spreiding_binnen_de_regio(c):
    notes = {r["subject_id"]: r["note"] for r in aggregate.region_rain(c)}
    assert "400" in notes["ext"] and "1200" in notes["ext"]
    assert "oppervlaktegewogen" in notes["ext"]


def test_afgeleiden_tellen_niet_mee_in_de_poort(c):
    """Vijf uitdrukkingen van dezelfde meting zijn geen vijf metingen.

    Relatief geformuleerd, niet absoluut: op de runner staan er 2.949 echte
    gemeenten in dezelfde tabel. Een test die een vast getal verwacht, werkt tot
    het moment dat het project begint te werken. Die les kostte al een deploy."""
    r = [x for x in db.q(c, "select * from v_readiness") if x["tier"] == "municipality"][0]
    echt = db.q(c, """select count(*) n from v_observation_current
                      where subject_type='municipality' and not derived""")[0]["n"]
    alles = db.q(c, """select count(*) n from v_observation_current
                       where subject_type='municipality'""")[0]["n"]
    assert r["cells"] == echt
    assert alles > echt, "er zijn geen afgeleiden, dan toetst deze test niets"


def test_een_vergelijkbare_cel_maakt_de_variabele_nog_niet_vergelijkbaar(c):
    """De fout die in de poort zelf zat: vergelijkbaarheid gold zodra EEN cel
    vergelijkbaar was. Bij gemengde invoer kleurde een variabele dan ten onrechte
    groen, en dat is precies de overschatting waar deze poort tegen bedoeld is."""
    aggregate.region_rain(c)                  # twee van de acht regio's krijgen raster
    blok = {b["variable"]: b["comparable"] for b in db.q(c, "select * from v_blocking_vars")}
    assert blok.get("rain_mm") is False
    r = [x for x in db.q(c, "select * from v_readiness") if x["tier"] == "region"][0]
    assert int(r["comparable_pct"]) == 50     # nog steeds 3 van 6, niet 4


def test_drempels_zijn_een_reeks_en_geen_getal(c):
    """De ondergrens is een keuze en geen eigenschap: 450 mm hoort bij dehesa,
    500 bij Atlantisch loofbos."""
    rijen = aggregate.rain_thresholds(c)
    per = {int(r["drempel"]): int(r["gemeenten"]) for r in rijen}
    boven400 = db.q(c, """select count(*) n from v_observation_current
                          where subject_type='municipality' and variable='rain_mm'
                            and value_num >= 400""")[0]["n"]
    assert per[400] == boven400
    drempels = sorted(per)
    assert all(per[a] >= per[b] for a, b in zip(drempels, drempels[1:]))  # monotoon
    assert per[400] > per[800], "geen enkele gemeente valt af, dan zegt de reeks niets"


def test_gemeentewaarden_gaan_mee_naar_buiten(c):
    """De database van de workflow is een wegwerpmachine. Wat niet in de export
    komt, bestaat na afloop niet meer."""
    rows = {r["code"]: r for r in aggregate.municipality_rain(c)}
    assert set(rows) >= {g[0] for g in GEMEENTEN}
    assert rows["TT_1"]["mm"] == 1200.0 and rows["TT_1"]["mm_max"] == 1680.0
    assert rows["TT_1"]["spread"] == round(1680 / 720, 2)
