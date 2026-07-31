"""Tests op de wachtlijst die op de site staat.

De wachtlijst is de enige plek waar het project uit zichzelf toegeeft wat het nog
niet weet. Precies daarom is hij het makkelijkst om stilletjes te laten verlopen:
een bron die binnenkomt en toch blijft staan, of een regel die in het Engels leeg
is, ziet er op het scherm allebei prima uit.

De drie controles hieronder zijn de manieren waarop die lijst kan gaan liegen:
een regel zonder uitleg, een bron die zowel bij de mensen als bij de machines
staat, en een handmatige regel voor iets dat allang automatisch kan.
"""
import pytest

from terra import db, export, load_seed


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


@pytest.fixture(scope="module")
def data(c):
    return export.build(c)


def test_elke_wachtregel_zegt_wat_hij_oplevert(data):
    """Een regel zonder uitleg is een lijst met huiswerk zonder reden erbij.

    Beide talen, want de site heeft een schakelaar: een lege Engelse tekst valt
    terug op het Nederlands en dan staat er ineens Nederlands in een Engelse zin.
    """
    rijen = data["waiting_automatable"] + [d for d in data["manual_debt"] if d["unlocks"]]
    assert rijen, "de wachtlijst is leeg; dat klopt bijna zeker niet"
    zonder = [r["id"] for r in rijen if not (r["unlocks"] or "").strip()
              or not (r["unlocks_en"] or "").strip()]
    assert not zonder, f"wachtregels zonder uitleg in beide talen: {zonder}"


def test_geen_bron_staat_bij_zowel_de_mensen_als_de_machines(data):
    """Dubbel tellen zou het werk groter laten lijken dan het is, en erger: het
    zou verbergen wie er aan zet is."""
    mensen = {d["id"] for d in data["manual_debt"]}
    machines = {w["id"] for w in data["waiting_automatable"]}
    assert not (mensen & machines), f"staat twee keer op de lijst: {mensen & machines}"


def test_handmatig_werk_is_echt_handmatig(data):
    """Iemand een middag laten overtypen wat een ophaler in twintig regels doet,
    is de duurste fout die deze lijst kan maken."""
    from terra.registry import BY_ID

    onterecht = [d["id"] for d in data["manual_debt"]
                 if d["id"] in BY_ID and BY_ID[d["id"]].automatable]
    assert not onterecht, (
        f"staat als handwerk op de lijst maar is automatiseerbaar: {onterecht}")
