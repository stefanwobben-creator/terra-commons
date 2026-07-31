# De handmatige bronnen: wie mailen, wat vragen

Acht van de achttien bronnen staan als niet-automatiseerbaar in het register. Dit is
de lijst om ze weg te werken, op volgorde van wat ze opleveren gedeeld door wat ze
kosten.

De aangewezen route voor al deze bronnen is **vragen en niet scrapen**. Elk van deze
instanties heeft de data nodig om zijn eigen werk te doen, dus hij bestaat; en een
bestand dat je krijgt komt met een herkomst die je mag opschrijven.

---

## 0. Eerst dit: IBI hoeft misschien niet handmatig

**Bevinding van 31 juli 2026.** Het Ministerio de Hacienda publiceert de gemeentelijke
belastingtarieven centraal, als open dataset ("Imposición local. Tipos de gravamen,
índices y coeficientes") en via een raadpleegdienst per provincie en gemeente. Als dat
klopt, is `ibi-ordenanzas` geen kwestie van 8.132 gemeentelijke verordeningen maar één
download, en verhuist die bron van de handmatige naar de automatiseerbare lijst.

**Nagekeken, diezelfde dag, en het antwoord is half ja.** De vraag was of de dataset
ook **rustiek** onroerend goed dekt. Dat doet hij: rústica staat apart van urbana, en
per gemeente. Maar er zit een afkapping op die precies de verkeerde kant op valt:

> gedetailleerd per gemeente, **alleen voor gemeenten met meer dan 1.000 inwoners**

Onze zoekruimte is landelijk Extremadura, en daar zit het merendeel van de gemeenten
onder die grens. De centrale dataset dekt dus juist de gemeenten die wij níét zoeken.
Voor de rest blijft er de raadpleegdienst per gemeente, en die is nog niet gesondeerd.

Het adres bij datos.gob.es dat hier eerst stond geeft nu 404. De twee andere adressen
staan nog als kandidaat in `terra/fetch/sources.py`.

**Conclusie:** `ibi-ordenanzas` verhuist nog niet. De hoop was één download; het is
waarschijnlijk een download voor de grote gemeenten en handwerk voor de kleine. Dat is
nog steeds beter dan alles met de hand, maar het is niet de doorbraak van vanochtend.

---

## 0b. En ZAR en de fiscale waarden misschien ook niet

**Bevinding van 31 juli 2026, bij het opzoeken van de e-mailadressen.** Twee van de
drie brieven bleken bij het zoeken naar de juiste dienst overbodig te kunnen zijn,
omdat de data al openbaar staat:

- **ZAR:** INFOEX zet Anexo I van Decreto 260/2014, de afbakening van de zones met
  hoog risico, zelf als PDF online. Dat is de lijst waar de brief om zou vragen.
- **Fiscale waarden:** het Portal Tributario heeft een openbare rekentool
  *Valoración de bienes inmuebles de naturaleza rústica* die per gemeente en
  gewasklasse een waarde teruggeeft.

**Correctie op dat tweede punt, een uur later.** Ik schreef erbij dat de waarden
jaarlijks bij orden in het DOE worden vastgesteld en dat de tabel dus mogelijk gewoon
in die orden staat. Ik heb de orden van 11 december 2025 nagekeken en dat klopt niet.
Die gaat over *precios medios de mercado voor edificaciones en suelo rústico*: schuren
en huizen, in euro per vierkante meter bebouwd, en Anexo II geeft één rij voor **alle**
gemeenten tegelijk. Geen gemeenten, geen gewasklassen, geen grond. Verkeerd document.

De grondwaarden zitten dus wél achter de rekentool en zijn niet als tabel in het DOE
gevonden. Dat maakt de brief in paragraaf 3 belangrijker dan hij een uur geleden leek.

Beide staan nu als kandidaat in `terra/fetch/sources.py`. **Sondeer eerst.** Dat
verandert niets aan `automatable`: een PDF-bijlage en een JSP-formulier zijn geen
bestand dat je periodiek ophaalt, dus dit blijft handwerk. Maar het is handwerk
zonder wachttijd, en dat is een ander soort werk dan een brief die drie weken ligt.

Let op bij de rekentool: een volledige laag betekent 2.949 bevragingen. Dat mag pas
als de voorwaarden van het portaal dat toestaan. Sonderen is hier lezen wat er staat,
niet oogsten.

---

## 1. Kaveleenheid, Decreto 46/1997 (`umc-decreto-46-1997`)

**Waarom het bovenaan staat:** dit is de enige handmatige bron die een **poort**
raakt. K3 gebruikt nu een landelijke terugval van 16 ha; met de echte tabel wordt hij
exact per gemeente. Eén bijlage dekt heel Extremadura, dus volledige dekking in één
levering.

**Wat we hebben:** Badajoz groep 1 staat op 4 ha secano en 1,5 ha regadío; wijnstok en
olijf overal 2 ha. De municipiolijst per groep zit achter een betaalmuur.

**Waar het zit:** de Junta de Extremadura heeft een dienst voor de
*autorización de segregación de fincas de dimensión inferior a la unidad mínima de
cultivo*. Zo'n loket kan zijn werk niet doen zonder die tabel. Volgens de
trámitepagina (juntaex.es/w/3809) is dat:

> Consejería de Agricultura, Ganadería y Medio Natural
> Dirección General de Regadíos e Infraestructuras Rurales
> Servicio de Infraestructuras Rurales
> Avenida Luis Ramallo s/n, 06800 Mérida

Op die pagina staat geen e-mailadres, alleen het postadres. Loop de directory van de
Consejería na voor het adres van dat Servicio, of gebruik het algemene contactformulier
van de Junta. Verifieer het adres voor je verstuurt: dit is overgenomen van een
webpagina en diensten worden hernoemd bij elke herindeling.

**Wat te vragen:** de bijlage bij Decreto 46/1997 (DOE nr. 50, 29 april 1997) met de
indeling van gemeenten in groepen, bij voorkeur als tabel of spreadsheet.

> Asunto: Solicitud del anexo del Decreto 46/1997 (unidades mínimas de cultivo)
>
> Buenos días,
>
> Estoy realizando un estudio abierto y sin ánimo de lucro sobre la restauración
> ecológica de fincas rústicas en Extremadura, y necesito aplicar correctamente la
> unidad mínima de cultivo por municipio.
>
> ¿Sería posible obtener el anexo completo del Decreto 46/1997, con la clasificación
> de los municipios por grupos y los valores en hectáreas para secano y regadío,
> preferiblemente en formato de tabla o CSV?
>
> Los datos se utilizarán en un proyecto de código abierto y la fuente quedará
> citada. Muchas gracias por su tiempo.

**Levert op:** K3 exact in plaats van bij benadering, voor alle Extremadurese gemeenten.

---

## 2. Zones met hoog brandrisico (`zar-fire-zones`)

**Waarom:** K8 hangt eraan (boven 200 ha in een ZAR is een brandpreventieplan
verplicht in plaats van boven 400 ha), en het is een gemeentelijke aanwijzing, dus
een afgebakende lijst.

**Stand: binnengehaald, maar niet nagelopen.** `manual/zar-extremadura.csv` bevat 202
gemeenten uit Anexo I van Decreto 260/2014. De PDF is vanuit de werkomgeving niet te
downloaden (403 op dat domein), dus de inhoud is via een ophaaldienst overgetypt door
een taalmodel. Dat werkte, maar het is geen gelezen bron: de transcriptie sprak zichzelf
tegen over de aantallen (188 in de samenvatting, 202 in de namenlijst) en spelde twee
gemeenten twee keer verschillend. Alles staat op `quality = ind`.

**Lees `manual/ZAR-WAARSCHUWING.md` voordat een besluit hierop leunt.** Daar staat ook
het punt dat deze CSV niet kan oplossen: Anexo I wijst polígonos catastrales aan binnen
gemeenten, niet hele gemeenten, en dat verschil telt zodra K8 op een echt perceel wordt
toegepast.

De brief hieronder blijft staan voor wat er niet in de PDF staat: een GIS-laag, en de
vraag of de afbakening van 2014 nog geldt.

**Waar:** Dirección General de Prevención y Extinción de Incendios Forestales
(INFOEX), Junta de Extremadura. Die dienst beheert ook het PREIFEX.

**Wat te vragen:** een actuele en machineleesbare versie, en of Anexo I nog geldt.

> Asunto: Zonas de Alto Riesgo (Decreto 260/2014): versión vigente y capa SIG
>
> Buenos días,
>
> Estoy realizando un estudio abierto y sin ánimo de lucro sobre la restauración
> ecológica de fincas rústicas en Extremadura. He localizado el Anexo I del Decreto
> 260/2014 con la delimitación de las Zonas de Alto Riesgo, publicado en su web.
>
> Quisiera confirmar dos cosas: si esa delimitación sigue vigente o ha sido
> modificada posteriormente, y si existe una versión en formato de datos (tabla,
> CSV o capa SIG) de las zonas y de los municipios incluidos.
>
> Los datos se utilizarán en un proyecto de código abierto y la fuente quedará
> citada. Muchas gracias por su tiempo.

**Levert op:** de drempel van K8 per gemeente in plaats van een landelijke aanname.

---

## 3. Fiscale minimumwaarden per gewasklasse (`ex-fiscal-values`)

**Waarom:** dit is de enige bron die de prijs op **gemeenteniveau** brengt. Het model
gebruikt nu 614 tot 1.045 EUR/ha voor matorral als bandbreedte, terwijl dat in
werkelijkheid een spreiding over gemeenten is die wij hebben platgeslagen.

**Eerst dit:** het Portal Tributario van de Junta heeft een openbare rekentool voor de
*valoración de bienes inmuebles de naturaleza rústica*. De DOE-route is doodgelopen:
de orden van december 2025 gaat over gebouwen en niet over grond (zie 0b). De tool is
dus voorlopig de enige vindplaats, en die geeft één gemeente per keer. Daarmee is deze
brief van de drie de meest kansrijke om echt iets op te leveren.

**Waar:** Junta de Extremadura, Portal Tributario, via het contactformulier
(*buzón de atención*). Ook hier staat geen direct e-mailadres op de site.

**Wat te vragen:** de onderliggende tabel in plaats van de rekentool.

> Asunto: Valores unitarios de bienes inmuebles rústicos: solicitud de la tabla completa
>
> Buenos días,
>
> Estoy realizando un estudio abierto y sin ánimo de lucro sobre la restauración
> ecológica de fincas rústicas en Extremadura. He utilizado la herramienta de
> valoración de bienes inmuebles de naturaleza rústica del Portal Tributario.
>
> Para poder trabajar con todos los municipios a la vez, ¿sería posible obtener la
> tabla completa de valores unitarios por municipio y tipo de cultivo en formato de
> hoja de cálculo o CSV, así como la referencia de la orden vigente en el DOE?
>
> Consultar la herramienta municipio por municipio supondría varios miles de
> consultas, y prefiero no hacerlo sin su conformidad.
>
> Los datos se utilizarán en un proyecto de código abierto y la fuente quedará
> citada. Muchas gracias por su tiempo.

**Levert op:** prijs per gemeente in plaats van per regio. Let op: dit is een fiscale
waarde en geen marktprijs. Het is een ondergrens, en dat hoort in de notitiekolom.

---

## 4. Brandperimeters (`effis-fires`)

**Status:** wacht op de sonde. Het endpoint gaf 200 met `text/html`, dus mogelijk een
pagina in plaats van een document. Blijkt het alleen via het aanvraagformulier te
lopen, dan verhuist `automatable` naar false en gaat het bestand gewoon door de
handmatige inname; de code hoeft daar niets voor te weten.

**Wat te vragen als het zover komt:** brandperimeters voor de provincies Cáceres,
Badajoz, Zamora, Salamanca, León, Ourense en Lugo, periode 2011 tot heden, als
shapefile of GeoJSON.

**Levert op:** de cel die de rangorde Extremadura tegen Castilla y León beslecht.

---

## 5. Nota simple (`registro-propiedad`)

**Waarom het anders is dan de rest:** dit is geen bestand maar een handeling **per
perceel**, tegen betaling, bij het Registro de la Propiedad. Er valt niets te vragen
wat de hele laag oplost.

**Wanneer:** pas bij de shortlist. Dit is de poort (K5) die de nachtelijke taak per
definitie niet kan nemen, en dat is geen tekortkoming maar de grens van wat
automatisering hier kan.

**Levert op:** K5 per perceel, plus eigenaar en lasten.

---

## 6. Advertenties (`listings`)

**Route:** handmatig, met URL en kijkdatum, via `advertenties-template.csv`. Scrapen
is in strijd met de voorwaarden van de portals en dat blijft zo. De idealista-API zit
achter goedkeuring met een quotum in de orde van honderd verzoeken per maand: genoeg
om een handvol percelen te verrijken, niet om een dataset op te bouwen.

**Levert op:** de trechter terug op dertig waarnemingen, en vanaf dan een prijsverloop
per advertentie in plaats van een momentopname.

---

## 7. Wetteksten (`legal-country`)

**Openstaand:** alleen Bulgarije, en dat land staat buiten de scope. `lex.bg` gaf 403
en EUR-Lex is niet op te halen. Zolang dat zo blijft staat de landpoort daar op `null`
en niet op `false`: ongemeten, niet afgewezen.

**Levert op:** niets binnen de huidige scope. Laten liggen.

---

## 8. Stationsnormalen (`station-normals`)

**Actie: geen.** Deze bron is met opzet afgesplitst van CHELSA omdat hij ten onrechte
onder diens vlag stond. Hij is vervangen door het raster en hoeft niet opnieuw
ingelezen te worden. Hij staat in het register om te laten zien waar de oude
regiocijfers vandaan kwamen.

---

## Samengevat

| Bron | Actie | Kosten | Levert op |
|---|---|---|---|
| ibi-ordenanzas | deels centraal, alleen boven 1.000 inwoners | onbekend | tarief per gemeente |
| umc-decreto-46-1997 | **e-mail versturen**, enige echte brief | een e-mail | K3 exact, hele regio |
| zar-fire-zones | **binnen, 202 gemeenten**, nog nalopen | half uur nalezen | K8-drempel per gemeente |
| ex-fiscal-values | rekentool bekijken, dan mailen | half uur | prijs per gemeente |
| effis-fires | wacht op de sonde | onbekend | beslist de rangorde |
| registro-propiedad | pas bij de shortlist | per perceel, betaald | K5 |
| listings | handmatig invullen | een half uur | trechter terug op 30 |
| legal-country | laten liggen | n.v.t. | buiten scope |

De diensten staan er nu bij voor zover een openbare pagina ze noemt. **De
e-mailadressen niet**, en dat is geen slordigheid: geen van de drie diensten publiceert
er een. Het loopt via een contactformulier of via de directory van de Consejería. Zoek
het adres op het moment dat je verstuurt, want een dienst die je vandaag opzoekt heet
volgend jaar anders.

En de belangrijkste les van deze ronde: **het opzoeken van een adres is soms al het
antwoord.** Twee van de drie brieven bleken niet nodig zodra ik zocht waar ze heen
moesten. Zoek eerst waar de data staat, schrijf daarna pas.
