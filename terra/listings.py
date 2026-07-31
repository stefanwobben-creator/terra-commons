"""Advertenties innemen, met de herkomstplicht overeind.

Dit is de bron die het hele project een les heeft geleerd: van de dertig
advertenties in de eerste longlist had er geen enkele een URL of een kijkdatum, en
daarmee was er geen enkele na te lopen. Ze staan sindsdien in quarantaine.

Deze handler is de weg terug. Hij doet twee dingen die de generieke tabelhandler
niet doet:

**Hij respecteert de constraint in plaats van eromheen te gaan.** Een regel zonder
URL of kijkdatum gaat niet naar `parcel` maar naar `listing_quarantine`, met de
reden erbij. Niet weigeren, niet stilzwijgend overslaan: apart zetten.

**Hij behandelt een advertentie als een waarneming en niet als een object.**
Dezelfde finca kan drie keer op een portal staan met drie prijzen. De sleutel is
(url, kijkdatum), dus een nieuwe datum is een nieuwe rij en een dubbele inname op
dezelfde dag verandert niets. Zo wordt het prijsverloop zichtbaar in plaats van
overschreven.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from . import db, enrich

KOLOMMEN = {
    "url": ("url", "listing_url", "link", "adres"),
    "seen_at": ("seen_at", "gezien", "kijkdatum", "datum"),
    "muni": ("muni", "gemeente", "muni_name", "municipality", "plaats"),
    "region": ("region", "regio", "region_code"),
    "ha": ("ha", "hectare", "oppervlakte", "area_ha"),
    "price": ("price", "prijs", "price_eur", "vraagprijs"),
    "source": ("source", "bron", "portal", "src"),
    "note": ("note", "opmerking", "notitie"),
}
REGIO_ALIAS = {"extremadura": "ext", "castilla y leon": "cyl", "castilla y león": "cyl",
               "galicie": "gal", "galicië": "gal", "galicia": "gal",
               "beira interior": "bei", "alentejo": "ale"}


def _getal(x):
    """Een getal uit iets wat een mens heeft getypt.

    Hier zit een echte dubbelzinnigheid in: "34.500" is in Nederland
    vierendertigduizend vijfhonderd en in Engeland vierendertig komma vijf. Een
    prijs die duizend keer te laag binnenkomt ziet er in een tabel nog steeds uit
    als een getal, dus dit hoort niet op gevoel.

    De regel: een scheidingsteken dat de cijfers in groepen van precies drie hakt
    is een duizendtalscheiding, en anders is het een decimaalteken. Dus 34.500 en
    1.550.000 worden gehele getallen, en 21.2 en 21,2 blijven eenentwintig komma
    twee. Wat allebei kan (bijvoorbeeld 1.500) valt onder dezelfde regel en wordt
    vijftienhonderd; in een kolom met prijzen en hectares is dat de veilige kant.
    """
    if x is None or str(x).strip() == "":
        return None
    t = str(x).strip().replace("\u20ac", "").replace(" ", "").replace("\u00a0", "")
    if not t:
        return None
    heeft_beide = "," in t and "." in t
    if heeft_beide:
        # De laatste van de twee is het decimaalteken, de andere groepeert.
        decimaal = "," if t.rfind(",") > t.rfind(".") else "."
        groep = "." if decimaal == "," else ","
        t = t.replace(groep, "").replace(decimaal, ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")          # 34.500 en 1.550.000
    elif re.fullmatch(r"-?\d{1,3}(,\d{3})+", t):
        t = t.replace(",", "")          # 34,500
    else:
        t = t.replace(",", ".")         # 21,2
    try:
        return float(t)
    except ValueError:
        return None


def lees(tekst: str) -> dict:
    import csv, io
    try:
        dialect = csv.Sniffer().sniff(tekst[:2048], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    lezer = csv.DictReader(io.StringIO(tekst), dialect=dialect)
    laag = {v.strip().lower(): v for v in (lezer.fieldnames or [])}
    kol = {d: laag[o] for d, opts in KOLOMMEN.items() for o in opts if o in laag}
    rijen = []
    for n, r in enumerate(lezer, start=2):
        def g(veld):
            k = kol.get(veld)
            return (r.get(k) or "").strip() if k else ""
        regio = g("region").lower()
        rijen.append({
            "regel": n, "url": g("url") or None, "seen_at": g("seen_at") or None,
            "muni": g("muni") or None,
            "region_code": REGIO_ALIAS.get(regio, regio or None),
            "ha": _getal(g("ha")), "price_eur": _getal(g("price")),
            "src": g("source") or None, "note": g("note") or None,
        })
    return {"rows": rijen, "kolommen": kol, "koppen": lezer.fieldnames}


PARCEL = """
insert into parcel (kind, region_code, muni_name, ha, price_eur, listing_url,
                    source_id, seen_at)
values ('listing',%s,%s,%s,%s,%s,'listings',%s)
on conflict (listing_url, seen_at) where kind='listing' do update set
  ha=excluded.ha, price_eur=excluded.price_eur, muni_name=excluded.muni_name,
  region_code=excluded.region_code
"""
QUARANTAINE = """
insert into listing_quarantine (region_code, muni_name, ha, price_eur, src_name,
                                reason, raw)
values (%s,%s,%s,%s,%s,%s,%s)
"""


def load(c, path: Path, source_id: str = "listings", observed_at=None) -> dict:
    """Neemt op wat herkomst heeft, zet de rest apart. Blokkeert nooit."""
    import json

    tabel = lees(Path(path).read_text(encoding="utf-8-sig"))
    goed, apart = [], []
    for r in tabel["rows"]:
        datum = r["seen_at"] or (str(observed_at) if observed_at else None)
        try:
            datum = str(date.fromisoformat(datum)) if datum else None
        except ValueError:
            datum = None
        redenen = []
        if not r["url"]:
            redenen.append("geen URL")
        if not datum:
            redenen.append("geen bruikbare kijkdatum")
        if redenen:
            apart.append((r["region_code"], r["muni"], r["ha"], r["price_eur"],
                          r["src"], " en ".join(redenen), json.dumps(r, default=str)))
        else:
            goed.append((r["region_code"], r["muni"], r["ha"], r["price_eur"],
                         r["url"], datum))
    n_goed = db.many(c, PARCEL, goed)
    n_apart = db.many(c, QUARANTAINE, apart)
    return {"regels": len(tabel["rows"]), "opgenomen": n_goed,
            "in_quarantaine": n_apart, "kolommen": tabel["kolommen"],
            "redenen": sorted({a[5] for a in apart})}
