# Seed

`regions.json`, `variables.json`, `region_scores.json` en `criteria.json` zijn compleet
en komen uit de site en uit paragraaf 13 van het zoekprofiel.

`parcels.json` is **onvolledig: 7 van de 30 waarnemingen**. De sandbox waarin de
eerste versie stond is herstart en 23 records zijn daarbij verloren gegaan. Ze staan
nog wel in de opgeleverde zip `terra-pipeline.zip`.

Herstellen: pak `seed/parcels.json` uit die zip, zet hem hier terug en draai
`python -m terra.load_seed`. De tests die op 30 waarnemingen rekenen
(`test_trechter_reproduceert_22_en_2108`) slaan zichzelf over zolang het bestand
onvolledig is, en gaan vanzelf weer meedoen zodra het compleet is.

Wat de volledige set opleverde, ter controle na herstel:

```
  30 waarnemingen        14 ext, 9 cyl, 7 bei
  mediaan EUR/ha         5.022 ext, 1.627 cyl, 5.000 bei
  profiel                9 groot, 12 passend, 9 klein
  vlaggen                K2 9x, K3 6x, K8 2x
  dehesa-venster         22 kandidaten, 2.108 ha
  rewild-venster         15 kandidaten, 441 ha
```

Geen van de dertig had een URL of kijkdatum. Ze horen daarom in
`listing_quarantine` en niet in `parcel`. Dat is geen fout in de inname.
