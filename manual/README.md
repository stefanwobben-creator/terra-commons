# Handmatige inname

> Op zoek naar **wie je moet mailen en wat je moet vragen** per bron? Dat staat in
> [BRONNEN.md](BRONNEN.md). Begin daar met punt 0: een van de acht hoeft mogelijk
> helemaal niet handmatig.

Acht van de achttien bronnen zijn niet te automatiseren. Dit is de plek waar die
bestanden binnenkomen, met dezelfde herkomstplicht als een advertentie: waar komt
het vandaan, wanneer heb je het opgehaald, en wie was dat.

## Werkwijze

1. Zet het bestand in deze map.
2. Voeg een regel toe aan `manifest.json`.
3. Draai `python -m terra.manual` om te laten keuren en innemen.

De hash mag je leeglaten: `python -m terra.manual --stempel` vult hem in en schrijft
het manifest terug. Een **bestaande** hash wordt nooit overschreven, want dat zou de
controle uitzetten op precies het moment dat hij zou aanslaan.

## Waarom een sha256

Zonder die controle is het manifest een bewering over een bestand. Met die controle
is het een bewering die je kunt weerleggen. Wordt het bestand later vervangen zonder
dat het manifest meebeweegt, dan stopt de inname in plaats van dat er stilletjes iets
anders binnenkomt.

## Velden

| Veld | Verplicht | Toelichting |
|---|---|---|
| `file` | ja | bestandsnaam in deze map |
| `source_id` | ja | moet in `terra/registry.py` bestaan |
| `origin` | ja | waar het vandaan komt: een URL, een e-mail, een loket |
| `obtained_at` | ja | jjjj-mm-dd, niet in de toekomst |
| `obtained_by` | ja | een naam; een bestand zonder eigenaar is een bestand zonder verhaal |
| `sha256` | nee | wordt aangevuld, daarna gecontroleerd |
| `note` | nee | wat je zou willen weten als je dit over een jaar terugleest |
| `bewust_handmatig` | soms | verplicht als de bron ook automatisch kan |


## Tabelvormige bronnen

Fiscale minimumwaarden, kaveleenheden, brandrisicozones en IBI-tarieven gaan
allemaal door dezelfde handler, want ze hebben dezelfde vorm: een onderwerp, een
variabele, een waarde. Lever een CSV aan met minstens twee kolommen.

```
gemeente;variabele;waarde;eenheid;kwaliteit;opmerking
ES_10148;fiscal_min_eur_ha;1045;EUR/ha;ind;matorral, tabel 2021
ES_10149;fiscal_min_eur_ha;614;EUR/ha;ind;matorral
```

Kolomnamen mogen Nederlands of Engels, gescheiden door puntkomma of komma. Wat er
niet in staat wordt aangevuld: het niveau is `municipality` tenzij je iets anders
zegt, en de kwaliteit is `ind` tenzij je hem op `ver` zet.

**Drie dingen die met opzet zo zijn:**

- **Gedeeltelijk is geldig.** Veertig gemeenten van de 2.949 is geen mislukte upload
  maar precies wat je krijgt als iemand veertig PDF's heeft doorgeploegd. De rest
  blijft ongemeten, en dat is de eerlijke weergave.
- **Een onbekende code is een rapport, geen fout.** Je krijgt de lijst terug; de rest
  gaat gewoon door.
- **Handmatige waarden staan op `comparable = false`.** Een overgetypte waarde is niet
  met dezelfde methode gemeten als de rest. Zou dat wel zo zijn, dan was er een bron
  geweest om hem uit te halen.

En: `python -m terra.manual` eindigt met exit 0, ook als er iets geweigerd is. Een
fout in een los PDF hoort de hele keten niet stil te zetten. Wil je het wel laten
falen, bijvoorbeeld in een controle-workflow, draai dan met `--strict`.


## Advertenties

Advertenties gaan **niet** door de tabelhandler maar door een eigen handler, want
ze belanden in `parcel` en daar hangt de herkomstconstraint aan. Gebruik
`advertenties-template.csv` als vertrekpunt; daar staan de zeven overgebleven
waarnemingen uit de eerste longlist al in, met lege kolommen voor URL en kijkdatum.

```
gemeente;regio;ha;prijs;url;kijkdatum;bron;opmerking
Trujillo;Extremadura;315;1.550.000;https://...;2026-07-31;Cocampo;
```

Vul URL en kijkdatum in en de regel gaat naar `parcel`. Laat je er een leeg, dan
gaat de regel naar `listing_quarantine` met de reden erbij: niet geweigerd, niet
stilzwijgend overgeslagen, apart gezet.

**Een advertentie is een waarneming en geen object.** De sleutel is (url, kijkdatum).
Dezelfde advertentie op een nieuwe datum is een nieuwe rij, dus als de vraagprijs
zakt zie je dat terug in `v_listing_history` in plaats van dat de oude prijs
verdwijnt. Twee keer dezelfde dag innemen verandert niets.

Getallen mogen Nederlands of Engels: `34.500`, `34,500`, `21,2` en `21.2` worden
allemaal goed gelezen. Een scheidingsteken dat de cijfers in groepen van precies
drie hakt geldt als duizendtalscheiding, de rest als decimaalteken.


## Namen in plaats van codes

Mensen typen namen, geen codes. De tabelhandler zoekt daarom een gemeente op naam
op als de waarde geen bestaande code is, en rapporteert wat hij aan welke code heeft
gekoppeld. Accenten en het achtergeplaatste lidwoord worden onderweg gladgestreken:
`Cáceres` en `CACERES` zijn hetzelfde, en `Puebla de Sanabria, La` vindt
`La Puebla de Sanabria`.

**Twee treffers is geen treffer.** Spaanse gemeentenamen zijn niet uniek; er zijn
meerdere Valverdes en die liggen in verschillende provincies. Gokken zou data op de
verkeerde plek zetten zonder dat iemand het merkt, dus zo'n regel belandt in de
lijst `dubbelzinnig` met de kandidaten erbij. Zet er een kolom `regio` bij en het
probleem is meestal weg.

## De kaveleenheid, en waarom dit bestand onvolledig is

`umc-extremadura-template.csv` bevat wat uit Decreto 46/1997 te verifiëren viel:
Badajoz groep 1 staat op **4 ha secano en 1,5 ha regadío**, en voor wijnstok en
olijf geldt overal 2 ha. De municipiolijst per groep zit achter een betaalmuur, dus
in dit bestand staan alleen de gemeenten die de bron zelf noemde. Alles op `ind`,
want dit is overgetypt uit een samenvatting en niet uit de DOE-bijlage.

Wie het volledige anexo te pakken krijgt (DOE nr. 50 van 29 april 1997) vult de rest
aan; gedeeltelijk aanleveren is nadrukkelijk toegestaan. Dat maakt K3 exact in plaats
van de landelijke terugval van 16 ha die er nu voor staat.
