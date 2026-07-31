"""Stap 0, landniveau. Wat hier staat is onderzocht, met de kwaliteitscode erbij.
'ind' betekent: gevonden, maar niet tegen de primaire wettekst geverifieerd.
'mis' betekent: niet vastgesteld, dus geen poort die open staat maar een poort
die we niet gemeten hebben.
"""
from __future__ import annotations

COUNTRIES: tuple[dict, ...] = (
    dict(
        code="ES", name="Spanje",
        buy_allowed=True, buy_conditions=None, use_obligation=False,
        exit_levy_pct=None, exit_levy_years=None, parcel_geometry_open=True,
        quality="ver",
        note=("Ley 19/1995 art. 27: alleen retracto voor aangrenzende eigenaren onder "
              "tweemaal de kaveleenheid, geen tanteo, plus zes jaar doorverkoopverbod "
              "bij fiscaal begunstigde overdracht. Ley 1/1986 Extremadura nog geldend, "
              "de heffing uit art. 21 tot 27 is geschrapt door Ley 8/2002."),
    ),
    dict(
        code="PT", name="Portugal",
        buy_allowed=True, buy_conditions=None, use_obligation=False,
        exit_levy_pct=None, exit_levy_years=None, parcel_geometry_open=True,
        quality="ver",
        note=("Geen kwalificatie-eis voor EU-particulieren. Het BUPi-kadaster is nog in "
              "opbouw, wat een perceelrisico is en geen landpoort."),
    ),
    dict(
        code="RO", name="Roemenie",
        buy_allowed=True,
        buy_conditions=("vijf jaar woonplaats, vijf jaar landbouwactiviteit en fiscale "
                        "inschrijving in Roemenie (Legea 17/2014 zoals gewijzigd door "
                        "Legea 175/2020)"),
        use_obligation=True, exit_levy_pct=80, exit_levy_years=8,
        parcel_geometry_open=True, quality="ind",
        note=("De combinatie sluit de poort: een Nederlandse stichting zonder vijf jaar "
              "geschiedenis ter plaatse valt buiten de gekwalificeerde kopers, en de "
              "heffing van 80 procent bij doorverkoop binnen acht jaar maakt een fout "
              "onherstelbaar."),
    ),
    dict(
        code="IT", name="Italie",
        buy_allowed=True, buy_conditions=None, use_obligation=False,
        exit_levy_pct=None, exit_levy_years=None, parcel_geometry_open=True,
        quality="ind",
        note=("Prelazione agraria voor pachter en aangrenzende beroepslandbouwer is een "
              "procesrisico bij de akte, geen verbod. Klimaat- en brandcijfers zijn hier "
              "niet ingewonnen, dus de regioscore blijft leeg."),
    ),
    dict(
        code="BG", name="Bulgarije",
        buy_allowed=None,
        buy_conditions=("vijfjaarseis uit ZSPZZ art. 3v; status na de EU-toetreding niet "
                        "geverifieerd"),
        use_obligation=None, exit_levy_pct=None, exit_levy_years=None,
        parcel_geometry_open=None, quality="mis",
        note=("Openstaand. lex.bg gaf 403 en EUR-Lex is niet op te halen, dus de wettekst "
              "is niet gelezen. Zolang dit zo staat is Bulgarije niet afgewezen maar "
              "ongemeten."),
    ),
)

BY_CODE = {c["code"]: c for c in COUNTRIES}

# Regiosleutel -> rechtsgebied waarin regionale wetgeving geldt. Los van NUTS, want
# K2 hangt aan Ley 1/1986 van Extremadura en niet aan een statistiekcode.
JURISDICTION: dict[str, str] = {
    "ext": "ES-EX", "cyl": "ES-CL", "gal": "ES-GA", "bei": "PT-C", "ale": "PT-ALT",
}


def jurisdiction_of(region_code: str | None) -> str | None:
    return JURISDICTION.get(region_code or "")


# Regiosleutel -> land en NUTS2, voor zover de regio met een NUTS2 samenvalt.
REGION_COUNTRY: dict[str, tuple[str, str | None]] = {
    "ext": ("ES", "ES43"),
    "cyl": ("ES", "ES41"),
    "gal": ("ES", "ES11"),
    "bei": ("PT", "PT16"),   # Beira Interior valt binnen Centro, niet gelijk eraan
    "ale": ("PT", "PT18"),
    "rom": ("RO", None),     # bewust geen NUTS2: het dossier dekt meerdere regio's
    "ita": ("IT", None),
    "bul": ("BG", None),
}
