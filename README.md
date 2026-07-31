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
terra/aggregate.py   regiowaarden afleiden uit de gemeentelaag; geen download
terra/manual.py      inname van handmatige bronnen, met herkomstplicht en sha256
terra/enrich.py      handmatige verrijking als tabel; gedeeltelijk mag, blokkeert nooit
terra/listings.py    advertenties, met de herkomstconstraint overeind en prijsverloop
manual/              waar die bestanden binnenkomen, plus het manifest
tests/               95 tests, waarvan een de site tegen de database aanhoudt
```

## De drie ideeen waar de rest uit volgt

**1. Kwaliteit hangt aan de cel, niet aan de tabel.** Elke meting in `observation`
draagt `quality` (ver/ind/mis), `comparable`, `source_id` en `observed_at`. Daarmee
is de rijpheidspoort een SQL-view en geen handmatige telling:

```
tier          cellen  gevuld  betrouw  vergelijk  volledig  poort
country            1       1     100%      100%      100%    OPEN
region            18      18      61%       50%      100%    dicht
```

Drempels 80 / 100 / 95. De scope staat sinds 31 juli op **Spanje**: drie regio's
maal zes variabelen is achttien cellen. De volledigheid sprong daarmee van 81 naar
100 procent, want alle negen lege cellen zaten in Roemenie, Italie en Bulgarije.
De vergelijkbaarheid bleef op 50, en dat is het punt: **een kleinere vraag maakt de
metingen niet beter.** Brand en prijs blokkeren nog steeds.

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

## Scope: Spanje

Sinds 31 juli 2026 rekent de rijpheidspoort alleen over Spanje. Niet omdat het
onderzoek naar de andere landen weg is (dat staat er nog, met de reden erbij in
`v_out_of_scope`), maar omdat Roemenie, Italie en Bulgarije in dit model dossiers
zijn en geen NUTS2-regio's. Ze kunnen dus nooit gemeenten krijgen, en daarmee nooit
een rastergemeten neerslag. Zolang ze in de noemer stonden kon de vergelijkbaarheid
per definitie niet naar 100. Dat was een scopeprobleem en geen datakwaliteitsprobleem.

Portugal ligt er voorlopig uit omdat het BUPi-kadaster nog in opbouw is, en dat maakt
de perceellaag onbetrouwbaar. Beira Interior scoorde goed op water; dat dossier blijft
staan voor later.

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

## De handmatige helft heeft nu ook een pad

Acht van de achttien bronnen zijn niet te automatiseren. Voor de tien andere stonden
er ophalers klaar; voor deze acht stond er niets. Dat was scheef, want juist daar zit
de poort die de nachtelijke taak niet kan nemen.

`terra/manual.py` en de map `manual/` doen daar hetzelfde wat de constraint voor
advertenties doet: **geen herkomst, geen inname.** Verplicht per bestand: waar het
vandaan komt, wanneer het is opgehaald, en door wie. Plus een sha256 die het manifest
falsifieerbaar maakt: wordt het bestand later vervangen zonder dat het manifest
meebeweegt, dan stopt de inname in plaats van dat er stilletjes iets anders binnenkomt.

Een bron die ook automatisch kan, met de hand innemen mag, maar niet per ongeluk:
daar is `bewust_handmatig` voor. Je vervangt dan de herkomst van een download door
die van een mens, en dat hoort een besluit te zijn.

**En het mag nooit blokkeren.** Verzamelen en met de hand verrijken moet altijd
kunnen, dus: een gedeeltelijke levering is geldig, een onbekende gemeentecode is een
rapport en geen fout, en `python -m terra.manual` eindigt met exit 0 ook als er iets
geweigerd is. Een fout in een los PDF hoort de keten niet stil te zetten. Voor een
controle-workflow is er `--strict`.

```bash
# bestand in manual/ zetten, regel in manual/manifest.json, dan:
python -m terra.manual --stempel   # vult ontbrekende hashes aan
python -m terra.manual             # keurt en neemt in
```

## De eerlijke grens van "automatisch"

Achttien bronnen, tien automatiseerbaar, acht niet. Van de drie echte poorten:

| Poort | Wat het toetst | Automatisch |
|---|---|---|
| K4 | juridisch verzekerde toegang | ja, uit het wegennet |
| K6 | via pecuaria over het perceel | ja, uit de MITECO-laag |
| K5 | inschrijving in het eigendomsregister | **nee**, nota simple per perceel |

En de cadans van die achttien: 3 eenmalig, 8 jaarlijks, 1 per seizoen, 6 op afroep.
**Nul dagelijks.** Wat wel dagelijks verandert is het aanbod op de portals, en dat is
precies de bron die we niet mogen automatiseren. Daarom staat er nog geen cronjob in
`render.yaml`. Zie `render.phase2.yaml`.

## Draaien

```bash
export DATABASE_URL=postgresql://terra:terra@127.0.0.1:5432/terra
bash scripts/bootstrap.sh     # schema, views, constraints, inname, export
python -m pytest -q           # 95 tests
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

De bronadressen zijn **gesondeerd op 31 juli 2026** vanaf een GitHub-runner, en de
werkende adressen staan nu als standaardwaarde in de workflow:

```
  OK    GISCO LAU 2023        123,0 MB   application/geo+json
  OK    CHELSA bio12          655,2 MB   image/tiff, jaarneerslag 1 km, 1981-2010
  ?     EFFIS WFS             200 met text/html: bereikbaar, maar geen XML
  FOUT  CNIG LineasLimite     404, niet nodig want GISCO werkt
```

Draaien: GitHub, Actions, workflow **data**, Run workflow. De velden staan al goed.

- **Beide velden gevuld laten** (standaard) → gemeentegrenzen en neerslag worden
  opgehaald, ingeladen en herberekend, en er komt een pull request met de nieuwe
  `site/data.json`. Duurt ongeveer vijf tot tien minuten, vooral door die 655 MB.
- **Beide velden leegmaken** → alleen de sonde, geen database. Dat is de stand voor
  als je wilt weten of een adres nog leeft.
- **`peek` op `true`** → de sonde laat ook de eerste regels van elk antwoord zien.
  Nodig gebleken bij EFFIS: een 200 met `text/html` betekent dat je een pagina kreeg
  en geen document. Bereikbaar is niet hetzelfde als bruikbaar.

**Eenmalig instellen voor de pull request.** Settings, Actions, General, onderaan bij
Workflow permissions: zet **Read and write permissions** aan en vink
**Allow GitHub Actions to create and approve pull requests** aan. Zonder dat faalt
de laatste stap met een permissiefout, terwijl al het werk al gedaan is.

### Waarom heel Spanje en niet een paar provincies

De automatiseerbare bronnen zijn bulkbestanden. Een LAU-bestand bevat alle 8.132
Spaanse gemeenten in een download, en zonal statistics over die polygonen is minuten
rekenwerk. Beperken tot vier provincies bespaart niets. De trage bronnen
(IBI-verordeningen, fiscale minimumwaarden per gewasklasse) zijn wel per gemeente,
maar die haal je pas op voor de gemeenten die het klimaat- en brandfilter overleven.

En waarom niet op provincie filteren: de provincie is in Spanje bijna nergens de
bevoegde laag. De kaveleenheid, de fiscale minimumwaarde, het IBI-tarief en de
aanwijzing als zone met hoog brandrisico staan per **gemeente**; het ITP-tarief en
de dehesa-drempel per **autonome regio**. De provincie is vooral de eenheid waarin
SIGPAC en het kadaster hun bestanden verpakken. Een downloadbestand, geen regel.
Gemeten op de neerslagnormalen van Extremadura: de spreiding binnen een provincie is
2,14x, die tussen de twee provincies 1,55x.

### Niet alleen het gemiddelde

Per gemeente worden vijf waarden bewaard: gemiddelde, minimum, maximum en de
percentielen 10 en 90. Een gemeente kan van 200 tot 1.200 meter lopen, en een
gemiddelde over zo'n polygoon herhaalt op gemeentelijk niveau precies de fout die we
op regionaal niveau net gerepareerd hebben. Een gemeente met p10 400 en p90 1.100 is
geen gemeente met 750 mm.

De schaalfactor van het raster wordt uit het bestand gelezen en daarna getoetst aan
een plausibel bereik. Faalt die toets, dan schrijft de module **niets** weg: tien keer
te hoge neerslag ziet er in een tabel nog steeds uit als een getal, en dat is het
gevaarlijkste soort fout.

## Bekende gaten

- `seed/parcels.json` is onvolledig: 7 van de 30 waarnemingen. Zie `seed/README.md`.
- De gemeentelaag is leeg. `t2_municipality` logt zijn eigen leegte. Dit is de
  volgende stap, en ook de stap die de rijpheidspoort opent: de spreiding **binnen**
  een regio was groter dan die **tussen** regio's (2,51 tegen 2,02 voor neerslag).
- **Brand heeft een ophaler maar nog geen bron.** `terra/fetch/fires.py` en de
  bijbehorende views zijn af en getest op een fixture: verbrand oppervlak per
  gemeente per jaar via de doorsnede (niet de hele perimeter), een meerjarige
  basiskans over de volledige periode (niet alleen de brandjaren), en een
  kwaliteitscode die naar `ind` zakt zodra de kans op een enkel brandjaar rust.
  Het venster staat vast op **vijftien jaar** (`config.FIRE_WINDOW_YEARS`), want
  daarvoor verschilden landgebruik en brandbestrijding in Spanje te veel. Venster en
  dekking zijn twee aparte getallen: levert de bron maar een deel van die vijftien,
  dan blijft de noemer vijftien en zakt de kwaliteitscode. De noemer verkleinen zou
  de kans mooier maken en het gat verbergen.
  Wat ontbreekt is het adres. Zet `peek` op `true` in de workflow en kijk wat het
  EFFIS-endpoint werkelijk teruggeeft.
- **De oude tekst hieronder blijft staan tot dat rond is.** Het EFFIS-endpoint gaf 200 met `text/html`, dus
  waarschijnlijk een pagina en geen capabilities-document. Draai de sonde met `peek`
  op `true` om te zien wat er echt terugkomt. Blijkt het alleen via het
  aanvraagformulier te kunnen, dan is brand handmatig werk en hoort het in
  `v_manual_debt` in plaats van in een fetcher.
- De gemeentelaag dekt alleen regio's die met een NUTS2 samenvallen. Roemenie,
  Italie binnenland en Bulgarije zijn dossiers en geen NUTS-eenheden, dus die
  krijgen voorlopig geen gemeenten.

## Bronnen

[Render blueprint-spec](https://render.com/docs/blueprint-spec) ·
[cronjobs](https://render.com/docs/cronjobs) ·
[Postgres-extensies](https://render.com/docs/postgresql-extensions) ·
[gratis instances](https://render.com/docs/free)
