from terra.scoring import (fire_base_rate, region_score, tipping_point,
                           transaction_cost, weight_audit)


def test_kantelpunt_extremadura():
    """Het verschil tussen eerste en tweede plaats zat volledig in het lege
    brandvak. Vijftien van de vijfentwintig punten is het omslagpunt."""
    assert tipping_point({"A": 20, "E": 18, "F": 21, "G": None}, 74) == 15


def test_score_met_gaten_is_niet_vergelijkbaar():
    assert region_score({"A": 20, "E": 18, "F": 21, "G": None})["comparable"] is False
    assert region_score({"A": 15, "E": 14, "F": 23, "G": 22})["comparable"] is True


def test_brandbasis_is_meerjarig():
    """Een staartjaar zei niets. Het terugkeerinterval is de leesbare vorm."""
    cyl = fire_base_rate([200, 100, 12000, 300, 150, 80, 500, 4000, 200, 100], 9_422_600)
    assert cyl["n_years"] == 10 and cyl["return_years"] > 300


def test_transactiekosten_schalen_met_het_aantal_fincas():
    """Rionegro del Puente: 21,2 ha voor 34.500 euro, maar 260 aparte parcelas.
    Met een finca kost de akte 12 procent, met 260 het meervoudige."""
    een = transaction_cost(34500, 1)
    veel = transaction_cost(34500, 260)
    assert een["extra_pct_of_price"] < 15
    assert veel["extra_pct_of_price"] > 50
    assert veel["registry"] == round(24.04 * 260)


def test_gewichten_lopen_niet_stil_uit_elkaar():
    """Deze test hoort te falen zodra iemand de keuze maakt: de zeven dimensies
    tellen op tot 135 en het model belooft 100. Werk hem dan bij, verwijder hem niet."""
    a = weight_audit()
    assert a["sum"] == 135 and a["documented"] == 100
    assert a["consistent"] is False
