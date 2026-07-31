# Lees dit voordat je de ZAR-lijst gebruikt

`zar-extremadura.csv` bevat 202 gemeenten die volgens Anexo I van Decreto 260/2014 in
een zone met hoog brandrisico liggen. Het bestand is bruikbaar, maar het is **geen
gelezen bron**. Dit is waarom, en wat er nog moet gebeuren.

## Hoe het tot stand kwam

De PDF staat openbaar op infoex.info, maar is vanuit deze werkomgeving niet te
downloaden: de proxy geeft 403 op dat domein. De inhoud is daarom opgehaald via een
ophaaldienst die de PDF omzet en er een taalmodel op laat lezen. Dat model heeft de
namen overgetypt. Niemand heeft daarna Anexo I ernaast gelegd.

Dat is een wezenlijk ander soort bron dan CHELSA of GISCO. Daar staat aan het eind van
de keten een bestand met een sha256 die je kunt narekenen. Hier staat een taalmodel dat
een PDF heeft samengevat, en de sha256 in het manifest dekt alleen de CSV die daaruit
rolde, niet de juistheid ervan. Vandaar `quality = ind` op elke regel.

## Waarom het wantrouwen concreet is en niet principieel

Bij het overtypen zijn twee dingen misgegaan die je kunt zien zonder het origineel:

**De aantallen spreken zichzelf tegen.** Gevraagd om een samenvatting kwam het model op
188 gemeenten, verdeeld over 13 zones. Gevraagd om de namen zelf kwam het op 210 regels
en 202 unieke gemeenten. Dat verschil van veertien is niet te verklaren uit de acht
gemeenten die in twee zones liggen. Ergens is iets weggevallen of bijgekomen.

**Twee gemeenten staan er twee keer in, verschillend gespeld.** MONTÁNCHEZ naast
MONTANCHEZ, MEMBRÍO naast MEMBRIO. De normalisatie van `terra/enrich.py` vangt dat op,
maar het laat zien dat de transcriptie niet letterlijk is: een echte overname uit een
PDF spelt dezelfde naam twee keer hetzelfde.

## Wat het bestand hoe dan ook niet kan weten

Anexo I wijst geen hele gemeenten aan maar **polígonos catastrales binnen gemeenten**,
met uitsluitingen per geval. Deze CSV plet dat tot ja of nee per gemeente. Voor een
grote gemeente als Badajoz of Cáceres is dat een grove benadering: het overgrote deel
van zo'n gemeente ligt buiten de zone.

Voor de gemeentelaag is dat te verdedigen, want daar is de vraag "kan een perceel hier
in een ZAR liggen". Voor een concreet perceel is het dat niet. Zodra K8 op een echt
perceel wordt toegepast, moet de polígono erbij, en die staat alleen in de PDF.

## Wat er moet gebeuren

1. Anexo I openen en de 202 namen ernaast leggen. Een half uur werk, en daarna mag de
   kwaliteitscode naar `ver`.
2. De polígonos catastrales per gemeente overnemen, of vaststellen dat dat te veel werk
   is en de gemeentelaag als bovengrens accepteren, met die keuze opgeschreven.
3. Vragen of de afbakening van 2014 nog geldt. Die vraag staat in `BRONNEN.md` als
   conceptbrief aan INFOEX en is de enige reden dat die brief nog bestaat.

Tot stap 1 gedaan is telt deze laag als indicatief. Dat is precies wat `ind` betekent en
het is niet erg: 202 indicatieve gemeenten zijn meer dan nul gemeten gemeenten. Maar een
besluit dat op deze laag alleen leunt, leunt op een taalmodel dat een PDF heeft gelezen,
en dat hoort niemand te overkomen zonder het te weten.
