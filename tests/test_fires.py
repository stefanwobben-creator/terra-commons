"""Tests op de brandlaag, zonder netwerk.

Twee gemeenten van 10 bij 10 km, drie branden met bekende oppervlakten, en een
feature zonder jaartal om te zien of die netjes afvalt in plaats van door te
glippen.
"""
import pytest

from terra import db
from terra.fetch import fires
from pathlib import Path

FIX = Path(__file__).parent / "fixtures"


def vierkant(x, y, s):
    return {"type": "Polygon", "coordinates": [[[x, y], [x+s, y], [x+s, y+s], [x, y+s], [x, y]]]}


@pytest.fixture
def c():
    try:
        with db.conn() as conn:
            import json
            for code, x in (("FT_A", 2_900_000), ("FT_B", 2_910_000)):
                db.x(conn, """insert into municipality (code,region_code,name,geom,area_ha)
                    values (%s,'ext',%s,
                      st_multi(st_setsrid(st_geomfromgeojson(%s),3035)),
                      st_area(st_setsrid(st_geomfromgeojson(%s),3035))/10000)""",
                     (code, code, json.dumps(vierkant(x, 2_050_000, 10_000)),
                      json.dumps(vierkant(x, 2_050_000, 10_000))))
            yield conn
            conn.rollback()
    except Exception as e:
        if "connect" in str(e).lower():
            pytest.skip(f"geen database: {e}")
        raise


def test_jaartal_uit_van_alles():
    """EFFIS geeft soms een jaar, soms een datum, soms een tijdstempel."""
    assert fires.parse_year(2022) == 2022
    assert fires.parse_year("2022-06-15") == 2022
    assert fires.parse_year("15/06/2022 14:03") == 2022
    assert fires.parse_year("geen jaartal") is None
    assert fires.parse_year(1850) is None       # buiten het venster


def test_perimeter_zonder_jaar_valt_af_en_wordt_geteld():
    parsed = fires.to_rows(fires.lau.read(FIX / "fires_sample.geojson"))
    assert len(parsed["rows"]) == 18          # 3 branden plus 15 dekkingsjaren
    assert parsed["skipped"]["zonder bruikbaar jaartal"] == 1
    assert parsed["fields_used"]["jaar"] == "FIREDATE"


def test_verbrand_oppervlak_is_de_doorsnede_en_niet_de_perimeter(c):
    """Een brand die half over de gemeentegrens ligt, telt maar half mee. Anders
    zou een brand van 30.000 ha elke gemeente die hij raakt volledig zwart maken."""
    fires.load(c, FIX / "fires_sample.geojson")
    per = {(r["muni_code"], r["year"]): float(r["burned_ha"])
           for r in db.q(c, "select * from v_fire_by_municipality_year")}
    assert round(per[("FT_A", 2018)]) == 100      # 1 x 1 km binnen FT_A
    assert round(per[("FT_A", 2022)]) == 200      # 2 x 1 km, volledig binnen FT_A
    assert round(per[("FT_B", 2022)]) == 300      # 3 x 1 km, volledig binnen FT_B


def test_een_enkel_brandjaar_is_geen_basiskans(c):
    """De kernles uit de regiovergelijking, een niveau lager toegepast."""
    fires.load(c, FIX / "fires_sample.geojson")
    per = {r["code"]: r for r in db.q(c, "select * from v_fire_base_rate")}
    assert per["FT_A"]["brandjaren"] == 2 and per["FT_A"]["rust_op_een_jaar"] is False
    assert per["FT_B"]["brandjaren"] == 1 and per["FT_B"]["rust_op_een_jaar"] is True


def test_kwaliteitscode_volgt_het_aantal_brandjaren(c):
    """Twee brandjaren is een kans, een brandjaar is een waarneming."""
    fires.load(c, FIX / "fires_sample.geojson")
    q = {r["subject_id"]: r["quality"] for r in db.q(c, """
        select subject_id, quality from observation
        where subject_type='municipality' and variable='fire_rate_pct'""")}
    assert q["FT_A"] == "ver"
    assert q["FT_B"] == "ind"


def test_terugkeerinterval_is_de_leesbare_vorm(c):
    """0,06 procent per jaar zegt niemand iets; eens per 1.667 jaar wel."""
    fires.load(c, FIX / "fires_sample.geojson")
    a = [r for r in db.q(c, "select * from v_fire_base_rate") if r["code"] == "FT_A"][0]
    # 10 x 10 km is 10.000 ha, 300 ha verbrand, venster 15 jaar (2008 tot 2022).
    # De noemer is het VENSTER en niet het aantal jaren waarin er toevallig brandde.
    assert a["venster_jaren"] == 15 and a["dekking_jaren"] == 15
    assert a["van"] == 2008 and a["tot"] == 2022
    assert round(float(a["rate_pct_per_jaar"]), 2) == 0.20
    assert a["terugkeer_jaren"] == 500


def test_venster_en_dekking_zijn_twee_verschillende_dingen(c):
    """Levert de bron maar een deel van het venster, dan blijft de noemer vijftien
    en zakt de kwaliteitscode. De noemer verkleinen zou de kans mooier maken en het
    gat verbergen, en dat is precies de fout die deze laag moest oplossen."""
    import json as _json
    db.x(c, """insert into fire_perimeter (source_id,ext_id,year,geom)
               values ('effis-fires','LATER',2024,
                 st_multi(st_setsrid(st_geomfromgeojson(%s),3035)))""",
         (_json.dumps(vierkant(2_900_000, 2_050_000, 1000)),))
    r = [x for x in db.q(c, "select * from v_fire_base_rate") if x["code"] == "FT_A"][0]
    assert r["van"] == 2010 and r["tot"] == 2024
    assert r["venster_jaren"] == 15
    assert r["dekking_jaren"] < 15 and r["venster_niet_vol"] is True


def test_venster_in_sql_en_python_lopen_niet_uit_elkaar():
    """Vijftien staat op twee plekken. Twee plekken met hetzelfde getal is een
    belofte die iemand een keer vergeet na te komen."""
    from terra.config import FIRE_WINDOW_YEARS
    sql = (Path(__file__).resolve().parents[1] / "sql" / "007_fire_window.sql").read_text()
    assert f"{FIRE_WINDOW_YEARS} as venster_jaren" in sql
    assert f"- {FIRE_WINDOW_YEARS - 1} as van" in sql
