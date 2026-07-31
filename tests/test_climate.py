"""Tests op de rasterbemonstering, zonder netwerk en zonder het echte raster van
655 MB. De fixture is een klein bestand met een bekende gradient en, net als CHELSA,
gehele getallen met een schaalfactor van 0,1.
"""
from pathlib import Path

import pytest

from terra.fetch import climate

FIX = Path(__file__).parent / "fixtures"
RASTER = FIX / "rain_small.tif"


def poly(w, s, e, n):
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def test_schaalfactor_wordt_uit_het_bestand_gelezen():
    """Niet gokken. CHELSA slaat gehele getallen op met een schaal per variabele;
    een gemiste schaalfactor levert tien keer te veel neerslag, en dat ziet er in
    een tabel nog steeds uit als een getal."""
    import rasterio
    with rasterio.open(RASTER) as src:
        assert climate.read_scaling(src) == (0.1, 0.0)


def test_bemonstering_geeft_bereik_en_niet_alleen_een_gemiddelde():
    """De hele reden dat we naar gemeenteniveau gaan is spreiding. Als de
    bemonstering die weggemiddeld had, hadden we de fout een niveau verplaatst."""
    west = climate.sample(RASTER, [{"code": "W", "geometry": poly(-7.0, 40.1, -6.6, 40.9)}])[0]
    heel = climate.sample(RASTER, [{"code": "H", "geometry": poly(-7.0, 40.1, -6.05, 40.9)}])[0]
    assert 300 <= west["p10"] <= west["p90"] <= 700
    assert heel["min"] < 400 and heel["max"] > 1100
    assert heel["spread"] > 3         # 1.200 gedeeld door 300
    assert set(heel) >= {"mean", "min", "max", "p10", "p50", "p90", "n", "spread"}


def test_kleine_gemeente_valt_niet_buiten_de_boot():
    """Een gemeente van een paar vierkante kilometer raakt op een raster van 1 km
    maar een handvol cellen. Zonder all_touched krijgt hij nul cellen en dus geen
    waarde, en dat leest als 'niet gemeten' terwijl het 'te klein' is."""
    piepklein = climate.sample(RASTER, [{"code": "S",
                                         "geometry": poly(-6.51, 40.51, -6.49, 40.53)}])[0]
    assert piepklein["n"] >= 1


def test_sanity_vangt_een_gemiste_schaalfactor():
    assert climate.sanity([650.0, 700.0, 800.0])["ok"] is True
    kapot = climate.sanity([6500.0, 7000.0, 8000.0])
    assert kapot["ok"] is False and "schaalfactor" in kapot["reden"]


def test_er_wordt_niets_weggeschreven_als_de_sanity_faalt(monkeypatch):
    """Bij twijfel niets opslaan. Tien keer te hoge neerslag in de database is
    erger dan een lege kolom, want een lege kolom ziet iemand."""
    monkeypatch.setattr(climate, "municipalities_as_features",
                        lambda c, srid=4326: [{"code": "X",
                                               "geometry": poly(-7, 40.1, -6.05, 40.9)}])
    monkeypatch.setattr(climate, "sanity",
                        lambda v, bereik=None: {"ok": False, "reden": "opzettelijk"})
    res = climate.load(None, RASTER)
    assert res["written"] == 0 and "gestopt" in res


def test_geen_gemeenten_is_een_leesbare_uitkomst(monkeypatch):
    monkeypatch.setattr(climate, "municipalities_as_features", lambda c, srid=4326: [])
    res = climate.load(None, RASTER)
    assert res["municipalities"] == 0 and "load_lau" in res["note"]
