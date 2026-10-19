/*
  Rifugi, bivacchi, malghe con ristoro e impianti di risalita in Alto Adige e dintorni.
  Incolla in https://overpass-turbo.eu  ->  Esegui  ->  Esporta  ->  "GeoJSON" -> "scarica"
  e salva il file come  poi.geojson  (stessa cartella dello script vicinanza_poi.py).

  Il rettangolo (bbox) copre tutta la provincia di Bolzano con un margine di circa 10 km
  oltre confine: serve perché un evento vicino al confine può avere il rifugio o
  l'impianto più vicino in Trentino, Veneto, Austria o Svizzera.
  bbox = sud, ovest, nord, est
*/
[out:json][timeout:300][bbox:46.15,10.30,47.15,12.60];
(
  // Rifugi serviti (Schutzhütte) e bivacchi / ricoveri non custoditi
  nw["tourism"="alpine_hut"];
  nw["tourism"="wilderness_hut"];
  nw["amenity"="shelter"]["shelter_type"="basic_hut"];

  // Malghe, baite e altri punti di ristoro in quota (riconosciuti dal nome)
  nw["amenity"~"^(restaurant|cafe|pub|fast_food)$"]["name"~"Alm|Hütte|Malga|Rifugio|Baita|Berggasthaus|Schutzhaus|Jausenstation"];

  // Impianti di risalita: linee e stazioni
  way["aerialway"~"^(cable_car|gondola|mixed_lift|chair_lift|funicular|j-bar|t-bar|platter|rope_tow|magic_carpet|drag_lift)$"];
  node["aerialway"="station"];
);
out geom;
