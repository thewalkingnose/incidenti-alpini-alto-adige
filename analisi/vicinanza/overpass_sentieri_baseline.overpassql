/*
  Sentieri escursionistici segnati: un punto (centro) per ogni tratto di sentiero.
  Serve come CONFRONTO: dove si trovano i punti di partenza e di arrivo dei sentieri
  rispetto a rifugi e impianti, a prescindere dagli incidenti.

  Il risultato è grande (decine di migliaia di elementi): in Overpass Turbo usa
  Esporta -> "Dati OSM grezzi" -> "scarica come JSON" e NON disegnare la mappa.
  Salva il file come  sentieri.json . Oppure lascia fare tutto allo script:
  python3 vicinanza_poi.py --scarica
*/
[out:json][timeout:300][bbox:46.15,10.30,47.15,12.60];
(
  way["highway"~"^(path|footway|steps)$"]["sac_scale"];
  way["highway"="path"]["trail_visibility"];
);
out center;
