"""Tests tegen een echte database, plus de driftcontrole tussen database en site.

Overslaan als er geen verbinding is, zodat de pure tests ook draaien op een machine
zonder Postgres. Waar deze tests op letten: dat de database dezelfde getallen
produceert als de pagina. Zodra die twee uiteenlopen is een van beide een verhaal.
"""
import json
import re
from pathlib import Path

import pytest

from terra import db, export, load_seed
from terra.config import THRESHOLDS
from terra.tiers import t0_country, t1_region, t3_parcel

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql"
DATA_JSON = ROOT / "site" / "data.json"


@pytest.fixture(scope="module")
def c():
    try:
        with db.conn() as conn:
            load_seed.main()
            t0_country.run(conn)
            t1_region.run(conn)
            conn.commit()
            yield conn
    except Exception as e:                                    # pragma: no cover
        pytest.skip(f"geen database: {e}")


def test_drempels_staan_niet_dubbel_uit_elkaar():
    """De poort staat in Python en in SQL. Lopen ze uiteen, dan meet de site iets
    anders dan de database, en dat is een fout die je nooit ziet."""
    nums = [int(n) for n in re.findall(r">=\s*(\d+)", (SQL / "002_views.sql").read_text())]
    assert set(THRESHOLDS) <= set(nums), (THRESHOLDS, nums)


def test_regio_rijpheid_reproduceert_de_pagina(c):
    r = [x for x in db.q(c, "select * from v_readiness") if x["tier"] == "region"][0]
    assert (int(r["reliable_pct"]), int(r["comparable_pct"]), int(r["complete_pct"])) == (62, 50, 81)
    assert r["gate_open"] is False


def test_bulgarije_is_ongemeten_en_niet_afgewezen(c):
    assert db.q(c, "select gate_open from country where code='BG'")[0]["gate_open"] is None


def test_roemenie_is_afgewezen(c):
    row = db.q(c, "select gate_open, gate_reason from country where code='RO'")[0]
    assert row["gate_open"] is False and "80" in row["gate_reason"]


def test_regio_zonder_brandscore_krijgt_geen_rangnummer(c):
    st = t1_region.run(c)
    c.commit()
    assert st["scores"]["ext"]["status"] == "pending"
    assert st["scores"]["ext"]["missing"] == ["G"]


def test_regiofilter_wijst_niets_af_zolang_de_poort_dicht_is(c):
    """Een streng filter op dunne data wijst geen regio's af maar meetfouten."""
    st = t1_region.run(c)
    c.commit()
    assert st["filtering"] is False
    afgewezen = [k for k, v in st["scores"].items() if v["status"] == "rejected"]
    assert afgewezen == ["rom"], afgewezen        # alleen op de landpoort


def test_geen_advertentie_zonder_herkomst(c):
    assert db.q(c, "select count(*) n from parcel")[0]["n"] == 0
    assert db.q(c, "select count(*) n from listing_quarantine")[0]["n"] > 0


def test_constraint_weigert_een_advertentie_zonder_url(c):
    with pytest.raises(Exception):
        db.x(c, "insert into parcel (kind,region_code,ha) values ('listing','ext',25)")
    c.rollback()


def test_trechter_reproduceert_22_en_2108(c):
    """Slaat zichzelf over zolang seed/parcels.json onvolledig is. Zie seed/README.md:
    23 van de 30 waarnemingen gingen verloren toen de werkomgeving herstartte."""
    d = t3_parcel.dry_run_quarantine(c, "dehesa")
    if d["n"] < 30:
        pytest.skip(f"seed onvolledig: {d['n']} van 30 waarnemingen")
    assert d["candidates_window"] == 22 and d["ha_in_window"] == 2108
    r = t3_parcel.dry_run_quarantine(c, "rewild")
    assert r["candidates_window"] == 15 and r["ha_in_window"] == 441


def test_site_en_database_lopen_niet_uiteen(c):
    """De belangrijkste test van dit bestand.

    site/data.json is wat de bezoeker ziet. Als dat bestand iets anders beweert dan
    de database, ziet niemand dat, want beide kanten zien er kloppend uit. Deze test
    faalt dan, en de deploy stopt.
    """
    if not DATA_JSON.exists():
        pytest.skip("site/data.json bestaat nog niet; draai python -m terra.export")
    op_schijf = json.loads(DATA_JSON.read_text())
    vers = export.build(c, generated_at=op_schijf["generated_at"])
    verschillen = [k for k in vers if json.dumps(vers[k], sort_keys=True, default=str)
                   != json.dumps(op_schijf.get(k), sort_keys=True, default=str)]
    assert not verschillen, (
        f"site/data.json is verouderd op: {verschillen}. "
        f"Draai `python -m terra.export` en commit het resultaat.")
