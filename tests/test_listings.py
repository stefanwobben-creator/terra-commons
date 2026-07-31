"""Tests op de inname van advertenties.

De bron die het project een les heeft geleerd: dertig advertenties zonder URL en
zonder kijkdatum, en dus geen enkele na te lopen. Deze tests leggen vast dat die
fout niet terug kan komen, en dat een regel zonder herkomst apart wordt gezet in
plaats van geweigerd of stilzwijgend overgeslagen.
"""
import pytest

from terra import db, listings

CSV = """gemeente;regio;ha;prijs;url;kijkdatum;bron
Rionegro del Puente;Castilla y Leon;21,2;34.500;https://www.idealista.com/inmueble/107962771/;2026-07-31;idealista
Pasaron de la Vera;Extremadura;154;540.000;https://agroanuncios.es/x1;2026-07-31;AgroAnuncios
Llerena;Extremadura;240;960.000;;2026-07-31;AgroAnuncios
Trujillo;Extremadura;315;1.550.000;https://cocampo.com/x2;;Cocampo
"""


@pytest.fixture
def c():
    try:
        with db.conn() as conn:
            db.x(conn, "delete from listing_quarantine")
            yield conn
            conn.rollback()
    except Exception as e:
        if "connect" in str(e).lower():
            pytest.skip(f"geen database: {e}")
        raise


def test_nederlandse_getallen_en_regionamen():
    """21,2 is eenentwintig komma twee en 34.500 is vierendertigduizend vijfhonderd.
    Een Nederlandse Excel levert het zo aan, en dat is geen reden om te weigeren."""
    t = listings.lees(CSV)
    assert t["rows"][0]["ha"] == 21.2
    assert t["rows"][0]["price_eur"] == 34500.0
    assert t["rows"][0]["region_code"] == "cyl"      # "Castilla y Leon" vertaald
    assert t["rows"][1]["region_code"] == "ext"


@pytest.mark.parametrize("tekst,verwacht", [
    ("34.500", 34500.0),        # Nederlandse duizendtalscheiding
    ("1.550.000", 1550000.0),
    ("34,500", 34500.0),        # Engelse duizendtalscheiding
    ("21,2", 21.2),             # Nederlands decimaalteken
    ("21.2", 21.2),             # Engels decimaalteken
    ("1.234,56", 1234.56),      # allebei, komma is decimaal
    ("1,234.56", 1234.56),      # allebei, punt is decimaal
    ("\u20ac 34.500", 34500.0),
    ("", None), ("n.v.t.", None),
])
def test_de_dubbelzinnigheid_van_punt_en_komma(tekst, verwacht):
    """34.500 is vierendertigduizend in Nederland en vierendertig komma vijf in
    Engeland. Een prijs die duizend keer te laag binnenkomt ziet er in een tabel
    nog steeds uit als een getal."""
    assert listings._getal(tekst) == verwacht


def test_alleen_met_herkomst_naar_parcel(c, tmp_path):
    p = tmp_path / "adv.csv"; p.write_text(CSV)
    res = listings.load(c, p)
    assert res["opgenomen"] == 2          # Rionegro en Pasaron
    assert res["in_quarantaine"] == 2     # een zonder URL, een zonder datum


def test_de_reden_staat_erbij(c, tmp_path):
    """Niet weigeren, niet stil overslaan: apart zetten met de reden."""
    p = tmp_path / "adv.csv"; p.write_text(CSV)
    res = listings.load(c, p)
    assert "geen URL" in res["redenen"]
    assert "geen bruikbare kijkdatum" in res["redenen"]
    q = db.q(c, "select reason from listing_quarantine order by reason")
    assert len(q) == 2 and all(r["reason"] for r in q)


def test_dezelfde_advertentie_op_dezelfde_dag_verandert_niets(c, tmp_path):
    p = tmp_path / "adv.csv"; p.write_text(CSV)
    listings.load(c, p)
    n1 = db.q(c, "select count(*) n from parcel where kind='listing'")[0]["n"]
    listings.load(c, p)
    n2 = db.q(c, "select count(*) n from parcel where kind='listing'")[0]["n"]
    assert n1 == n2 == 2


def test_een_nieuwe_kijkdatum_is_een_nieuwe_waarneming(c, tmp_path):
    """Een advertentie is een waarneming en geen object. Wie de laatste prijs
    overschrijft, gooit weg dat de vraagprijs in vier maanden twintig procent zakte."""
    p = tmp_path / "adv.csv"; p.write_text(CSV)
    listings.load(c, p)
    p.write_text(CSV.replace("2026-07-31;idealista", "2026-09-30;idealista")
                    .replace("34.500", "29.500"))
    listings.load(c, p)
    rijen = db.q(c, """select seen_at, price_eur from parcel
                       where listing_url like '%%idealista%%' order by seen_at""")
    assert len(rijen) == 2
    assert float(rijen[0]["price_eur"]) == 34500 and float(rijen[1]["price_eur"]) == 29500
    h = db.q(c, "select * from v_listing_history")
    assert h and h[0]["waarnemingen"] == 2 and int(h[0]["spreiding_pct"]) == 14


def test_de_constraint_blijft_de_baas(c):
    """De handler gaat niet om de constraint heen; hij respecteert hem. Direct
    invoegen zonder URL hoort nog steeds te falen."""
    with pytest.raises(Exception):
        db.x(c, """insert into parcel (kind, region_code, ha)
                   values ('listing','ext',25)""")
    c.rollback()
