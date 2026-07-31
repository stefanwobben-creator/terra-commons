"""Tests op de scopebeperking tot Spanje.

De kern: buiten de scope is niet hetzelfde als weg. Het onderzoek blijft in de
database staan, het telt alleen niet meer mee in de rijpheidspoort.
"""
import pytest

from terra import db, load_seed


@pytest.fixture(scope="module")
def c():
    try:
        with db.conn() as conn:
            load_seed.main()
            yield conn
    except Exception as e:
        if "connect" in str(e).lower():
            pytest.skip(f"geen database: {e}")
        raise


def test_alleen_spanje_binnen_de_scope(c):
    binnen = [r["code"] for r in db.q(c, "select code from country where in_scope")]
    assert binnen == ["ES"]


def test_de_andere_landen_blijven_bestaan_met_een_reden(c):
    """Wegmoffelen zou goedkoop zijn. De vier dossiers staan er nog, elk met de
    reden waarom ze even niet meetellen."""
    buiten = {r["code"]: r["scope_note"] for r in db.q(c, "select * from v_out_of_scope")}
    assert set(buiten) == {"PT", "RO", "IT", "BG"}
    assert all(len(v or "") > 40 for v in buiten.values()), "een reden van niks is geen reden"
    assert db.q(c, "select count(*) n from country")[0]["n"] == 5


def test_regios_buiten_de_scope_tellen_niet_meer_in_de_poort(c):
    """Drie Spaanse regio's maal zes variabelen is achttien cellen, niet achtenveertig."""
    r = [x for x in db.q(c, "select * from v_readiness") if x["tier"] == "region"][0]
    assert r["cells"] == 18
    assert int(r["complete_pct"]) == 100, "de lege cellen zaten allemaal buiten Spanje"


def test_de_landpoort_is_open_voor_spanje(c):
    """Niet omdat de data beter werd, maar omdat de vraag kleiner werd. Dat is een
    legitieme manier om een poort te openen, zolang je erbij zegt wat je hebt
    weggelaten."""
    r = [x for x in db.q(c, "select * from v_readiness") if x["tier"] == "country"][0]
    assert r["cells"] == 1 and r["gate_open"] is True


def test_de_scope_verbetert_de_vergelijkbaarheid_niet_vanzelf(c):
    """De verleiding was om prijs vergelijkbaar te noemen zodra alleen Spanje
    overblijft: binnen Spanje komt alles immers uit dezelfde MAPA-enquete. Maar dat
    is een redenering en geen meting. Een vlag omzetten omdat de scope verandert is
    precies het soort stille verbetering waar dit project tegen is."""
    blok = {b["variable"] for b in db.q(c, "select * from v_blocking_vars")}
    assert "price_eur_ha" in blok
    assert "burned_ha" in blok
