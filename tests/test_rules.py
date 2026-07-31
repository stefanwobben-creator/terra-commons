"""Tests op de beslisfuncties. Elke test hier hoort bij een fout die in het
onderzoek echt gemaakt is, zodat hij niet twee keer gemaakt wordt.
"""
from terra.criteria import GATES, MIN_HA_FALLBACK
from terra.rules import (candidate_window, country_gate, municipality_filter,
                         parcel_flags, parcel_gates, profile_match, readiness)


def test_romania_gate_dicht():
    ok, reasons = country_gate({
        "buy_allowed": True, "use_obligation": True,
        "buy_conditions": "vijf jaar woonplaats", "exit_levy_pct": 80,
        "exit_levy_years": 8, "parcel_geometry_open": True})
    assert ok is False
    assert any("80" in r for r in reasons)


def test_spanje_gate_open():
    ok, _ = country_gate({"buy_allowed": True, "use_obligation": False,
                          "parcel_geometry_open": True})
    assert ok is True


def test_onbekende_poort_is_geen_open_poort():
    """De kern: niet gemeten is niet goedgekeurd."""
    ok, reasons = parcel_gates({"ha": 25})
    assert ok is None
    assert "toetsbaar" in reasons[0]


def test_een_gefaalde_poort_wijst_af():
    ok, reasons = parcel_gates({"ha": 25, "k4_ok": False, "k6_ok": True})
    assert ok is False and reasons and reasons[0].startswith("K4")


def test_drie_poorten_en_niet_meer():
    assert [g.k for g in GATES] == ["K4", "K5", "K6"]


def test_k2_bindt_alleen_in_extremadura():
    assert any(f["k"] == "K2" for f in parcel_flags({"ha": 154, "jurisdiction": "ES-EX"}))
    assert not any(f["k"] == "K2" for f in parcel_flags({"ha": 154, "jurisdiction": "ES-CL"}))


def test_k2_is_geen_afwijzing():
    """Een vlag is een voorwaarde, geen poort. Dat verschil kostte 28 procent op de
    prijs per hectare toen K2 nog als knock-out gold."""
    flags = parcel_flags({"ha": 154, "jurisdiction": "ES-EX"}, "dehesa")
    assert all(f["category"] != "gate" for f in flags)


def test_neerslag_onbekend_is_geen_pas():
    ok, reasons = municipality_filter({"rain_mm": None})
    assert ok is False and "niet vastgesteld" in reasons[0]


def test_neerslagdrempel_hangt_aan_de_intentie():
    assert municipality_filter({"rain_mm": 470}, "dehesa")[0] is True
    assert municipality_filter({"rain_mm": 470}, "rewild")[0] is False


def test_kandidatenvenster():
    assert candidate_window("dehesa") == (MIN_HA_FALLBACK, 400.0)
    assert candidate_window("rewild") == (MIN_HA_FALLBACK, 100.0)


def test_profiel():
    assert profile_match({"ha": 154}) == "large"
    assert profile_match({"ha": 25}) == "fit"
    assert profile_match({"ha": 8.89}) == "small"
    assert profile_match({}) == "unknown"


def test_rijpheid_rekent_zoals_de_site():
    cells = ([{"variable": "price", "quality": "ind"}] * 8
             + [{"variable": "cost", "quality": "ver"}] * 8)
    r = readiness(cells, {"cost": True, "price": False})
    assert r["complete_pct"] == 100 and r["reliable_pct"] == 50
    assert r["comparable_pct"] == 50 and r["gate_open"] is False
