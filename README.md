# Terra Commons

Samen een stuk gedegradeerde grond in Zuid-Europa kopen en het ecosysteem herstellen.
Dit is het open onderzoek daarnaartoe: de methode, de data, de twijfel, en de code
die de een aan de ander vastknoopt.

**Fase: onderzoek.** Niets op de site is een conclusie. De poort tussen onderzoek en
conclusie staat dicht, met een getal erachter, en dat getal staat hieronder.

- Site: [terracommons.stefanwobben.nl](https://terracommons.stefanwobben.nl)
- Licentie: MIT

## Wat hier staat

```
site/index.html      de site, tweetalig NL/EN, licht en donker
site/data.json       de gemeten cijfers, gegenereerd uit de database
sql/                 schema (10 tabellen), views (7), en de herkomstconstraint
terra/               de pijplijn: land -> regio -> gemeente -> perceel
seed/                wat de site nu toont, als invoer voor de database
terra/fetch/         sonde en ophalers; de sonde eerst, dan pas downloaden
tests/               33 tests, waarvan een de site tegen de database aanhoudt
```

## De drie ideeen waar de rest uit volgt

**1. Kwaliteit hangt aan de cel, niet aan de tabel.** Elke meting in `observation`
draagt `quality` (ver/ind/mis), `comparable`, `source_id` en `observed_at`. Daarmee
is de rijpheidspoort een SQL-view en geen handmatige telling:

```
tier    | cells | present | verified | betrouwbaar | vergelijkbaar | volledig | poort
region  |    48 |      39 |       24 |     62 %    |     50 %      |   81 %   | dicht
```

Drempels 80 / 100 / 95. De poort staat dicht omdat prijs, neerslag en brand per land
met verschillende methoden gemeten zijn. `v_blocking_vars` noemt ze met de reden erbij.

**2. Niet gemeten is niet goedgekeurd.** Drie statussen, en `pending` is de
belangrijkste. `parcel_gates()` geeft `None` terug als geen enkele poort toetsbaar is,
niet `False` en niet `True`. Bulgarije heeft `gate_open = null`, want de wettekst is
nooit gelezen. Zonder dat verschil schuift een ontbrekende meting stil op naar
"geschikt".

**3. Herkomst is niet optioneel.** Van de dertig advertenties in de eerste longlist
had er geen enkele een URL of kijkdatum. Ze zijn daarom niet in `parcel` geladen; de
constraint weigert ze:

```sql
check (kind <> 'listing' or (listing_url is not null
       and seen_at is not null and source_id is not null))
```

Ze staan in `listing_quarantine` met de reden erbij. `v_quarantine_report` rekent wel
door wat de trechter met ze zou doen. Dat is een berekening, geen besluit.

## De site liegt niet tegen de database

De cijfers stonden als JavaScript-constanten in de pagina. Dat is dezelfde
herkomstfout als een advertentie zonder URL, een niveau hoger: de pagina was een bron
zonder bron. Nu genereert `python -m terra.export` het bestand `site/data.json`, en
leest de pagina dat in.

`tests/test_pipeline.py::test_site_en_database_lopen_niet_uiteen` bouwt data.json
opnieuw uit de database en vergelijkt. Loopt het uiteen, dan faalt de CI en stopt de
deploy. Dit is de enige fout in dit project die je nooit ziet, omdat beide kanten er
kloppend uitzien.

## Wat de pijplijn nu zegt, en het gaat tegen de site in

- **Castilla y Leon is de enige regio met een volledige score: 74 van 100.**
- **Extremadura staat op `pending`**, niet op de eerste plaats. Het brandvak is leeg,
  en het kantelpunt ligt op 15 van de 25 punten. Geen ranglijst, een openstaande meting.
- Roemenie is afgewezen op de landpoort: 80 procent heffing bij doorverkoop binnen
  acht jaar, plus een vijfjaarseis voor kopers.
- Bulgarije en Italie staan op `pending` wegens ongelezen bronnen.

Het regiofilter van 60 procent wijst op dit moment **niets** af, en dat is opzet: een
streng filter op dunne data wijst geen regio's af maar meetfouten. Het begint pas te
selecteren zodra de rijpheidspoort opengaat.

## De eerlijke grens van "automatisch"

Zeventien bronnen, tien automatiseerbaar, zeven niet. Van de drie echte poorten:

| Poort | Wat het toetst | Automatisch |
|---|---|---|
| K4 | juridisch verzekerde toegang | ja, uit het wegennet |
| K6 | via pecuaria over het perceel | ja, uit de MITECO-laag |
| K5 | inschrijving in het eigendomsregister | **nee**, nota simple per perceel |

En de cadans van die zeventien: 3 eenmalig, 8 jaarlijks, 1 per seizoen, 5 op afroep.
**Nul dagelijks.** Wat wel dagelijks verandert is het aanbod op de portals, en dat is
precies de bron die we niet mogen automatiseren. Daarom staat er nog geen cronjob in
`render.yaml`. Zie `render.phase2.yaml`.

## Draaien

```bash
export DATABASE_URL=postgresql://terra:terra@127.0.0.1:5432/terra
bash scripts/bootstrap.sh     # schema, views, constraints, inname, export
python -m pytest -q           # 33 tests
python -m http.server 8000 --directory site
```

## Deployen op Render

**Stap 1, nu: de statische site.** Gratis.

1. Push deze repo naar GitHub.
2. Render, New, Blueprint, wijs deze repo aan. `render.yaml` maakt een static site
   met publish path `./site`.
3. Settings, Custom Domains, voeg `terracommons.stefanwobben.nl` toe.
4. Bij je DNS-provider: een **CNAME** van `terracommons` naar de hostnaam die Render
   toont (`<naam>.onrender.com`). Geen A-record, dan blijft het certificaat automatisch.
5. Wachten tot Render "Certificate issued" zegt. Klaar.

**Stap 2, later: database en periodieke taak.** Zie `render.phase2.yaml`, en doe dit
pas als er minstens een werkende fetcher is. Kosten: 6 USD/mnd voor Postgres plus
1 USD/mnd voor de cronjob. Neem niet de gratis database: die verloopt 30 dagen na
aanmaak, heeft geen back-ups, en na 14 dagen respijt wordt hij verwijderd. De tabel
die je dan kwijt bent is `observation`.

## Twee inconsistenties die een keuze vragen

1. **De perceelgewichten tellen op tot 135, het model belooft 100.** Herwegen naar 100
   of het model bijstellen naar 135 geven verschillende uitkomsten.
   `scoring.weight_audit()` rapporteert het verschil; een test houdt de keuze open.
2. **K8 (brandplan boven 400 ha) is in het model een scorepost, maar de telling van 22
   kandidaten behandelde hem als uitsluiting.** Als scorepost zijn het er 24. Beide
   getallen worden gerapporteerd.

## De gemeentelaag ophalen

De volgende stap is de gemeentelaag, en die is **handmatig te starten zonder dat er
iets automatisch gaat draaien**: GitHub, Actions, workflow `data`, Run workflow.

1. **Laat het veld `lau_url` leeg.** De workflow draait dan alleen de sonde en
   rapporteert welke bronadressen kloppen. Het artefact `probe` bevat het antwoord.
   Dit is nodig omdat de adressen van GISCO, CHELSA en EFFIS niet geverifieerd zijn:
   de omgeving waarin deze code geschreven is heeft geen uitgaand netwerk naar die
   domeinen. Beter tien seconden sonderen dan een parser laten struikelen.
2. **Vul daarna `lau_url` met het adres dat werkte.** De workflow haalt op, laadt in,
   herberekent, draait de tests en opent een **pull request** met de nieuwe
   `site/data.json`. Je ziet dus een diff voordat er iets live gaat.

Waarom heel Spanje en niet een paar provincies: de automatiseerbare bronnen zijn
bulkbestanden. Een LAU-bestand bevat alle 8.132 Spaanse gemeenten in een download,
en zonal statistics over die polygonen is minuten rekenwerk. Beperken tot vier
provincies bespaart niets. De trage bronnen (IBI-verordeningen, fiscale
minimumwaarden per gewasklasse) zijn wel per gemeente, maar die haal je pas op voor
de gemeenten die het klimaat- en brandfilter overleven.

En waarom niet op provincie filteren: de provincie is in Spanje bijna nergens de
bevoegde laag. De kaveleenheid, de fiscale minimumwaarde, het IBI-tarief en de
aanwijzing als zone met hoog brandrisico staan per **gemeente**; het ITP-tarief en
de dehesa-drempel per **autonome regio**. De provincie is vooral de eenheid waarin
SIGPAC en het kadaster hun bestanden verpakken. Een downloadbestand, geen regel.
Gemeten op de neerslagnormalen van Extremadura: de spreiding binnen een provincie is
2,14x, die tussen de twee provincies 1,55x.

## Bekende gaten

- `seed/parcels.json` is onvolledig: 7 van de 30 waarnemingen. Zie `seed/README.md`.
- De gemeentelaag is leeg. `t2_municipality` logt zijn eigen leegte. Dit is de
  volgende stap, en ook de stap die de rijpheidspoort opent: de spreiding **binnen**
  een regio was groter dan die **tussen** regio's (2,51 tegen 2,02 voor neerslag).
- De bronadressen in `terra/fetch/sources.py` zijn **niet geverifieerd**. Draai
  eerst de sonde. Er zijn per bron meerdere kandidaten, juist daarom.
- Alleen de gemeentegrenzen hebben een ophaler. Klimaat en brand volgen zodra de
  sonde heeft gezegd welke adressen kloppen.

## Bronnen

[Render blueprint-spec](https://render.com/docs/blueprint-spec) ·
[cronjobs](https://render.com/docs/cronjobs) ·
[Postgres-extensies](https://render.com/docs/postgresql-extensions) ·
[gratis instances](https://render.com/docs/free)
