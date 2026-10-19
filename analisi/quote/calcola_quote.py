#!/usr/bin/env python3
"""Calcola la quota (m s.l.m.) di ogni punto di punti_incidenti.csv.

Usa due API gratuite, in ordine:
  1. OpenTopoData (EU-DEM 25 m, più preciso sulle Alpi)  - max 1 chiamata/s, 1000 chiamate/giorno
  2. Open-Meteo (Copernicus 90 m)                         - usata se la prima fallisce
Solo libreria standard. Uso: python3 calcola_quote.py  (nella cartella di punti_incidenti.csv)
Produce quote_incidenti.csv (id,lat,lon,quota_m). Si può interrompere e rilanciare: riparte da dove era.
"""
import csv, json, os, sys, time, urllib.request, urllib.error

IN, OUT, BATCH = "punti_incidenti.csv", "quote_incidenti.csv", 100
DELAY = 2  # secondi di pausa tra una chiamata e l'altra
HEADERS = {"User-Agent": "quote-incidenti/1.0 (uso personale)"}


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.load(resp)


def opentopodata(batch):
    locs = "|".join(f"{r['lat']},{r['lon']}" for r in batch)
    data = get_json(f"https://api.opentopodata.org/v1/eudem25m?locations={locs}")
    if data.get("status") != "OK":
        raise ValueError(data.get("error", "risposta non OK"))
    return [x["elevation"] for x in data["results"]]


def openmeteo(batch):
    url = ("https://api.open-meteo.com/v1/elevation?latitude="
           + ",".join(r["lat"] for r in batch)
           + "&longitude=" + ",".join(r["lon"] for r in batch))
    return get_json(url)["elevation"]


PROVIDERS = [("OpenTopoData EU-DEM 25 m", opentopodata), ("Open-Meteo 90 m", openmeteo)]


def fetch(batch):
    """Prova ogni provider (con pochi tentativi); restituisce (quote, nome_provider)."""
    for name, fn in PROVIDERS:
        for attempt in range(3):
            try:
                el = fn(batch)
                if len(el) != len(batch):
                    raise ValueError("risposta incompleta")
                return el, name
            except (urllib.error.URLError, ValueError, KeyError) as e:
                limit = isinstance(e, urllib.error.HTTPError) and e.code == 429
                wait = (30 if limit else 5) * (attempt + 1)
                print(f"  {name}: errore ({e}); riprovo tra {wait}s")
                time.sleep(wait)
        print(f"  {name}: non risponde, passo al servizio successivo")
    raise SystemExit("Nessun servizio ha risposto. Il lavoro già fatto è salvato: "
                     "riprova più tardi (o cambia rete/VPN) e rilancia lo script.")


def main():
    rows = list(csv.DictReader(open(IN, newline="")))
    done = set()
    if os.path.exists(OUT):
        done = {r["id"] for r in csv.DictReader(open(OUT, newline=""))}
    todo = [r for r in rows if r["id"] not in done]
    print(f"{len(rows)} punti, {len(done)} già calcolati, {len(todo)} da fare")

    new_file = not os.path.exists(OUT)
    with open(OUT, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["id", "lat", "lon", "quota_m"])
        for i in range(0, len(todo), BATCH):
            b = todo[i:i + BATCH]
            el, name = fetch(b)
            for r, q in zip(b, el):
                w.writerow([r["id"], r["lat"], r["lon"], "" if q is None else q])
            f.flush()
            print(f"  {min(i + BATCH, len(todo))}/{len(todo)}  ({name})")
            time.sleep(DELAY)
    print("Fatto ->", OUT)


if __name__ == "__main__":
    main()
