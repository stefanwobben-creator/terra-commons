"""Inname van handmatig verkregen bestanden.

Acht van de achttien bronnen zijn niet te automatiseren: wetteksten, fiscale
minimumwaarden per gemeente, de kaveleenheid uit een DOE-bijlage, de aanwijzing
als brandrisicozone, IBI-verordeningen, de nota simple, advertenties, en mogelijk
de brandperimeters. Voor de tien automatiseerbare bronnen staan er ophalers klaar;
voor deze acht stond er tot nu toe niets. Dat is scheef, want juist hier zit de
poort die de nachtelijke taak niet kan nemen.

**De regel is dezelfde als voor advertenties.** Van de dertig advertenties in de
eerste longlist had er geen enkele een URL of kijkdatum, en daarmee was geen ervan
na te lopen. Voor een handmatig binnengehaald bestand geldt precies hetzelfde: waar
komt het vandaan, wanneer is het opgehaald, en door wie. Ontbreekt een van die drie,
dan gaat het bestand er niet in.

**De sha256 maakt het manifest falsifieerbaar.** Zonder die controle is het manifest
een bewering over een bestand; met die controle is het een bewering die je kunt
weerleggen. Wordt het bestand vervangen zonder dat het manifest meebeweegt, dan
stopt de inname in plaats van dat er stilletjes iets anders binnenkomt.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from . import db
from .fetch.base import sha256
from .registry import BY_ID

DROP = Path(__file__).resolve().parent.parent / "manual"
MANIFEST = DROP / "manifest.json"

VERPLICHT = ("file", "source_id", "origin", "obtained_at", "obtained_by")


def lees_manifest(path: Path | None = None) -> list[dict]:
    path = path or MANIFEST
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return data.get("entries", data) if isinstance(data, dict) else data


def keur(entry: dict, root: Path | None = None) -> tuple[bool, list[str]]:
    """Mag dit bestand erin? Geeft de redenen terug, niet alleen een oordeel."""
    root = root or DROP
    fouten = []
    for veld in VERPLICHT:
        if not entry.get(veld):
            fouten.append(f"{veld} ontbreekt")
    bron = entry.get("source_id")
    if bron and bron not in BY_ID:
        fouten.append(f"onbekende bron: {bron}")
    elif bron and BY_ID[bron].automatable:
        # Geen verbod, wel een waarschuwing die je moet uitzetten: een bron die
        # automatisch kan, met de hand innemen betekent dat je de herkomst van een
        # download vervangt door die van een mens.
        if not entry.get("bewust_handmatig"):
            fouten.append(f"{bron} is automatiseerbaar; zet bewust_handmatig op true "
                          f"als je hem toch met de hand wilt innemen")
    pad = root / entry["file"] if entry.get("file") else None
    if pad and not pad.exists():
        fouten.append(f"bestand niet gevonden: {entry['file']}")
    elif pad and entry.get("sha256"):
        werkelijk = sha256(pad)
        if werkelijk != entry["sha256"]:
            fouten.append(f"sha256 komt niet overeen; manifest zegt "
                          f"{entry['sha256'][:12]}, bestand is {werkelijk[:12]}")
    if entry.get("obtained_at"):
        try:
            wanneer = date.fromisoformat(str(entry["obtained_at"]))
            if wanneer > date.today():
                fouten.append("obtained_at ligt in de toekomst")
        except ValueError:
            fouten.append("obtained_at is geen datum in de vorm jjjj-mm-dd")
    return (not fouten), fouten


def stempel(entries: list[dict], root: Path | None = None) -> list[dict]:
    """Vult ontbrekende hashes aan, zodat een mens ze niet hoeft over te tikken.

    Bewust alleen als hij nog leeg is: een bestaande hash overschrijven zou de
    controle uitschakelen op precies het moment dat hij zou aanslaan.
    """
    root = root or DROP
    for e in entries:
        pad = root / e.get("file", "")
        if pad.is_file() and not e.get("sha256"):
            e["sha256"] = sha256(pad)
    return entries


# Tabelvormige bronnen gaan allemaal door dezelfde handler. Fiscale minimumwaarden,
# kaveleenheden, brandrisicozones en IBI-tarieven zijn qua vorm hetzelfde: een
# onderwerp, een variabele, een waarde. Elke parser die er niet is, is er een die
# niet stuk kan.
# listings staat er bewust NIET bij. Advertenties gaan niet naar observation maar
# naar parcel, en daar hangt de herkomstconstraint aan: geen URL en geen kijkdatum,
# geen opname. Die verdient een eigen handler die dat respecteert, geen tabel die
# er langs glipt.
TABEL_BRONNEN = ("ex-fiscal-values", "umc-decreto-46-1997", "zar-fire-zones",
                 "ibi-ordenanzas", "registro-propiedad", "legal-country")

HANDLERS = {
    "effis-fires": "terra.fetch.fires:load",
    "listings": "terra.listings:load",
    **{b: "terra.enrich:load" for b in TABEL_BRONNEN},
}


# Welke sleutel een handler ook gebruikt om te zeggen hoeveel er landde: als geen van
# deze boven nul komt, is er niets binnengekomen.
TELLERS = ("weggeschreven", "observaties", "perimeters", "opgenomen")


def landde(res) -> bool:
    """Is er echt iets binnengekomen, of alleen iets aangeboden?

    Dit onderscheid kostte bijna een leugen. De ZAR-levering van 31 juli bood 404
    regels aan en schreef er nul weg, omdat de gemeentelaag in die database niet
    stond. De inname stempelde toch `last_run`, en daarmee verdween de bron uit de
    lijst met openstaand handwerk: het bestand was aangeboden, dus de schuld leek
    voldaan. Precies andersom dus. Een levering die niets raakt is geen levering.
    """
    if not isinstance(res, dict):
        return False
    if any((res.get(k) or 0) > 0 for k in TELLERS):
        return True
    # Geneste resultaten, zoals de brandhandler die zijn tellingen onder 'rates' zet.
    return any(landde(v) for v in res.values() if isinstance(v, dict))


def innemen(c, entries: list[dict] | None = None, root: Path | None = None) -> dict:
    """Neemt op wat door de keuring komt, en zegt van de rest waarom niet."""
    import importlib

    root = root or DROP
    entries = entries if entries is not None else lees_manifest()
    uitslag = {"aangeboden": len(entries), "ingenomen": [], "zonder_effect": [],
               "geweigerd": [], "zonder_handler": []}
    for e in entries:
        ok, fouten = keur(e, root)
        if not ok:
            uitslag["geweigerd"].append({"file": e.get("file"), "redenen": fouten})
            continue
        handler = HANDLERS.get(e["source_id"])
        if not handler:
            uitslag["zonder_handler"].append(
                {"file": e["file"], "source_id": e["source_id"],
                 "note": "keuring doorstaan, maar er is nog geen inname voor deze bron"})
            continue
        mod, fn = handler.split(":")
        f = getattr(importlib.import_module(mod), fn)
        # De tabelhandler wil weten van welke bron en van welke datum de waarden
        # zijn; de brandhandler haalt dat uit het bestand zelf.
        res = (f(c, root / e["file"], e["source_id"], e["obtained_at"])
               if mod in ("terra.enrich", "terra.listings")
               else f(c, root / e["file"]))
        raak = landde(res)
        if raak:
            db.x(c, """update source set last_run = now(), notes = coalesce(notes,'')
                       where id = %s""", (e["source_id"],))
        regel = {"file": e["file"], "source_id": e["source_id"],
                 "origin": e["origin"], "obtained_at": e["obtained_at"],
                 "obtained_by": e["obtained_by"],
                 "sha256": e.get("sha256", "")[:12], "resultaat": res}
        if raak:
            uitslag["ingenomen"].append(regel)
        else:
            regel["note"] = ("aangeboden en door de keuring, maar er landde niets. "
                             "last_run is niet gestempeld: de bron staat dus nog "
                             "steeds als openstaand handwerk, en dat klopt")
            uitslag["zonder_effect"].append(regel)
    return uitslag


def openstaand(c) -> list[dict]:
    """Welke handmatige bronnen wachten nog. De tegenhanger van een groene cron."""
    aangeleverd = {e.get("source_id") for e in lees_manifest()}
    return [{"id": r["id"], "name": r["name"], "tier": r["tier"],
             "aangeleverd": r["id"] in aangeleverd}
            for r in db.q(c, "select * from v_manual_debt")]


def main(argv: list[str] | None = None) -> int:
    import sys

    argv = argv or sys.argv[1:]
    entries = lees_manifest()
    if "--stempel" in argv:
        stempel(entries)
        MANIFEST.write_text(json.dumps({"entries": entries}, indent=2, ensure_ascii=False))
        print(f"manifest bijgewerkt: {len(entries)} regels")
        return 0
    if not entries:
        print("manifest is leeg; zie manual/README.md")
        return 0
    with db.conn() as c:
        with db.Run(c, "manual_intake") as run:
            uitslag = innemen(c, entries)
            run.stats = uitslag
            c.commit()
    print(json.dumps(uitslag, indent=1, ensure_ascii=False, default=str))
    if uitslag["geweigerd"]:
        print(f"\nLET OP: {len(uitslag['geweigerd'])} bestand(en) geweigerd, zie "
              f"hierboven waarom.", file=sys.stderr)
    # Standaard exit 0, ook bij weigeringen. Handmatige verrijking mag nooit een
    # run blokkeren: dat zou betekenen dat een fout in een los PDF de hele
    # nachtelijke keten stilzet. Wie het wel wil laten falen, draait met --strict.
    return 1 if ("--strict" in argv and uitslag["geweigerd"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
