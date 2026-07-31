"""Handmatige verrijking als tabel, voor elke bron en elke laag.

Uitgangspunt: data moet altijd verzameld en met de hand verrijkt kunnen worden, en
dat mag nooit blokkeren. Daar volgen drie eigenschappen uit die niet vanzelf spreken.

**Gedeeltelijk is een geldige levering.** Veertig gemeenten van de 2.949 is niet een
mislukte upload maar precies wat je krijgt als iemand veertig PDF's heeft doorgeploegd.
De rijpheidspoort ziet de rest gewoon als ongemeten, en dat is de eerlijke weergave.
Wachten tot een levering compleet is, is wachten tot niemand meer iets aanlevert.

**Onbekende onderwerpen zijn een rapport, geen fout.** Een gemeentecode die niet in
de database staat kan een tikfout zijn of een gemeente die wij nog niet hebben
ingeladen. Beide gevallen wil je zien; geen van beide hoort de rest tegen te houden.

**Eén tabelvorm voor alles.** Fiscale minimumwaarden, kaveleenheden, brandrisicozones
en IBI-tarieven zijn allemaal hetzelfde: een onderwerp, een variabele, een waarde. Er
is geen reden om daar vier parsers voor te schrijven, en elke parser die er niet is,
is er een die niet stuk kan.

De kwaliteitscode staat standaard op 'ind'. Wie een waarde met de hand overtypt uit
een PDF heeft geen primaire bron ingelezen maar een mens vertrouwd, en dat verschil
hoort in de data te staan en niet in iemands geheugen.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

from . import db

# Kolomnamen die we accepteren, per veld. Ruim genomen, want een mens die een
# CSV maakt is geen API.
KOLOMMEN = {
    "subject_type": ("subject_type", "tier", "niveau", "laag"),
    "subject_id": ("subject_id", "code", "id", "gemeente", "muni_code", "naam", "name"),
    "region_code": ("region_code", "regio", "region"),
    "variable": ("variable", "var", "variabele", "veld"),
    "value_num": ("value_num", "value", "waarde", "getal", "num"),
    "value_txt": ("value_txt", "tekst", "txt"),
    "unit": ("unit", "eenheid"),
    "quality": ("quality", "kwaliteit"),
    "note": ("note", "notitie", "opmerking", "toelichting"),
}
TIERS = ("country", "region", "municipality", "parcel")
KWALITEIT = ("ver", "ind", "mis")


def _map_kolommen(veldnamen: list[str]) -> dict[str, str]:
    gevonden, laag = {}, {v.strip().lower(): v for v in veldnamen}
    for doel, opties in KOLOMMEN.items():
        for o in opties:
            if o in laag:
                gevonden[doel] = laag[o]
                break
    return gevonden


def lees_tabel(tekst: str) -> dict:
    """CSV naar rijen, met een rapport over wat er niet doorheen kwam.

    Puntkomma of komma, allebei goed: een Nederlandse Excel levert het eerste en
    de rest van de wereld het tweede.
    """
    monster = tekst[:2048]
    try:
        dialect = csv.Sniffer().sniff(monster, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    lezer = csv.DictReader(io.StringIO(tekst), dialect=dialect)
    kol = _map_kolommen(lezer.fieldnames or [])
    ontbreekt = [k for k in ("subject_id", "variable") if k not in kol]
    if ontbreekt:
        return {"rows": [], "kolommen": kol, "gevonden_koppen": lezer.fieldnames,
                "fout": f"verplichte kolommen ontbreken: {', '.join(ontbreekt)}"}

    rijen, afgekeurd = [], []
    for n, r in enumerate(lezer, start=2):
        code = (r.get(kol["subject_id"]) or "").strip()
        var = (r.get(kol["variable"]) or "").strip()
        if not code or not var:
            afgekeurd.append({"regel": n, "reden": "subject_id of variable is leeg"})
            continue
        tier = (r.get(kol.get("subject_type", ""), "") or "municipality").strip().lower()
        if tier not in TIERS:
            afgekeurd.append({"regel": n, "reden": f"onbekend niveau: {tier}"})
            continue
        ruw = (r.get(kol.get("value_num", ""), "") or "").strip()
        getal = None
        if ruw:
            try:
                getal = float(ruw.replace(".", "").replace(",", ".")
                              if ruw.count(",") == 1 and ruw.count(".") > 1 else
                              ruw.replace(",", "."))
            except ValueError:
                getal = None
        kwal = (r.get(kol.get("quality", ""), "") or "ind").strip().lower()
        if kwal not in KWALITEIT:
            kwal = "ind"
        rijen.append({
            "subject_type": tier, "subject_id": code, "variable": var,
            "value_num": getal,
            "value_txt": (r.get(kol.get("value_txt", ""), "") or None) or (ruw if getal is None else None),
            "unit": (r.get(kol.get("unit", ""), "") or None),
            "quality": kwal,
            "note": (r.get(kol.get("note", ""), "") or None),
            "region_code": (r.get(kol.get("region_code", ""), "") or None),
        })
    return {"rows": rijen, "afgekeurd": afgekeurd, "kolommen": kol}


def normaliseer(naam: str) -> str:
    """Naam naar een vorm waarop je kunt vergelijken.

    Accenten eraf, kleine letters, dubbele spaties weg, en het lidwoord achteraan
    naar voren: Spaanse bronnen schrijven "Puebla de Sanabria, La" waar een mens
    "La Puebla de Sanabria" typt. Zonder die omzetting mist elke tweede gemeente.
    """
    import unicodedata

    t = unicodedata.normalize("NFKD", (naam or "").strip())
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    t = " ".join(t.split())
    if "," in t:
        romp, _, lidwoord = t.rpartition(",")
        if lidwoord.strip() in ("el", "la", "los", "las", "o", "a", "os", "as"):
            t = f"{lidwoord.strip()} {romp.strip()}"
    return t


def zoek_op_naam(c, naam: str, region_code: str | None = None) -> dict:
    """Een gemeente vinden op naam, en eerlijk zijn over dubbelzinnigheid.

    Spaanse gemeentenamen zijn niet uniek: er zijn meerdere Valverdes, en die
    liggen in verschillende provincies. Gokken zou hier data op de verkeerde plek
    zetten zonder dat iemand het merkt, dus twee treffers is geen treffer.
    """
    doel = normaliseer(naam)
    if not doel:
        return {"status": "leeg"}
    sql = "select code, name, region_code from municipality"
    params: tuple = ()
    if region_code:
        sql += " where region_code = %s"
        params = (region_code,)
    kandidaten = [r for r in db.q(c, sql, params) if normaliseer(r["name"]) == doel]
    if len(kandidaten) == 1:
        return {"status": "gevonden", "code": kandidaten[0]["code"],
                "naam": kandidaten[0]["name"]}
    if not kandidaten:
        return {"status": "onbekend"}
    return {"status": "dubbelzinnig",
            "kandidaten": [{"code": k["code"], "region_code": k["region_code"]}
                           for k in kandidaten]}


BESTAAT = {
    "country": "select 1 from country where code = %s",
    "region": "select 1 from region where code = %s",
    "municipality": "select 1 from municipality where code = %s",
    "parcel": "select 1 from parcel where id::text = %s",
}

OBS = """
insert into observation (subject_type,subject_id,variable,value_num,value_txt,unit,
                         quality,comparable,source_id,observed_at,note,derived)
values (%s,%s,%s,%s,%s,%s,%s,false,%s,%s,%s,false)
on conflict (subject_type,subject_id,variable,observed_at) do update set
  value_num=excluded.value_num, value_txt=excluded.value_txt,
  quality=excluded.quality, note=excluded.note
"""


def schrijf(c, rijen: list[dict], source_id: str, observed_at) -> dict:
    """Schrijft weg wat naar een bestaand onderwerp verwijst, rapporteert de rest.

    comparable staat op false. Een handmatig overgetypte waarde is per definitie
    niet met dezelfde methode gemeten als de rest; zou dat wel zo zijn, dan was er
    een bron geweest om hem uit te halen.
    """
    goed, onbekend, opgezocht, dubbelzinnig = [], [], [], []
    for r in rijen:
        code = r["subject_id"]
        if not db.q(c, BESTAAT[r["subject_type"]], (code,)):
            # Geen code? Dan is het waarschijnlijk een naam. Mensen typen namen.
            if r["subject_type"] == "municipality":
                uit = zoek_op_naam(c, code, r.get("region_code"))
                if uit["status"] == "gevonden":
                    opgezocht.append({"ingevoerd": code, "code": uit["code"],
                                      "naam": uit["naam"]})
                    code = uit["code"]
                elif uit["status"] == "dubbelzinnig":
                    dubbelzinnig.append({"ingevoerd": code,
                                         "kandidaten": uit["kandidaten"]})
                    continue
                else:
                    onbekend.append({"subject_type": r["subject_type"],
                                     "subject_id": code, "variable": r["variable"]})
                    continue
            else:
                onbekend.append({"subject_type": r["subject_type"],
                                 "subject_id": code, "variable": r["variable"]})
                continue
        goed.append((r["subject_type"], code, r["variable"], r["value_num"],
                     r["value_txt"], r["unit"], r["quality"], source_id,
                     observed_at, r["note"]))
    n = db.many(c, OBS, goed)
    return {"weggeschreven": n, "onbekend_onderwerp": len(onbekend),
            "onbekende_voorbeelden": onbekend[:10],
            "opgezocht_op_naam": len(opgezocht), "opzoekingen": opgezocht[:10],
            "dubbelzinnig": dubbelzinnig[:10],
            "variabelen": sorted({r["variable"] for r in rijen})}


def load(c, path: Path, source_id: str = "manual", observed_at=None) -> dict:
    """Handler voor de handmatige inname. Blokkeert nooit; rapporteert altijd."""
    from datetime import date

    tekst = Path(path).read_text(encoding="utf-8-sig")
    tabel = lees_tabel(tekst)
    res = {"regels": len(tabel["rows"]), "kolommen": tabel.get("kolommen"),
           "afgekeurde_regels": tabel.get("afgekeurd", [])[:10]}
    if tabel.get("fout"):
        res["fout"] = tabel["fout"]
        res["gevonden_koppen"] = tabel.get("gevonden_koppen")
        return res
    if not tabel["rows"]:
        res["note"] = "geen bruikbare regels; het bestand is leeg of alles viel af"
        return res
    res.update(schrijf(c, tabel["rows"], source_id, observed_at or date.today()))
    return res
