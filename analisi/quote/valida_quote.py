#!/usr/bin/env python3
"""
Validazione delle quote degli incidenti (Alto Adige).

Serve a rispondere a tre domande, in ordine:
  0. Ci sono coordinate sospette (segnaposto, punti ripetuti) che falsano la quota?        [senza internet]
  A. La quota cambia se la chiedo a un'altra fonte altimetrica indipendente?              [Open-Meteo / Copernicus]
  B. Quanto cambia la quota se la posizione registrata e' sbagliata di 50-100 m?          [OpenTopoData EU-DEM]
  C. Le fonti altimetriche riproducono le quote 'ele' note di rifugi, selle e cime (OSM)? [Overpass + le due fonti]

Uso (nella cartella con incidenti_altoadige_con_quota.csv):
    python3 valida_quote.py                 # tutti i test, 400 eventi campione
    python3 valida_quote.py --n 600         # campione piu' grande
    python3 valida_quote.py --test 0        # solo il controllo senza internet
    python3 valida_quote.py --test 0,B      # scegli i test
Solo libreria standard (Python 3.8+). Si puo' interrompere e rilanciare: le risposte gia' ricevute sono in
cache_quote.json. Servizi gratuiti: 1 richiesta ogni DELAY secondi; per il campione di 400 eventi servono
circa 80 richieste (3-4 minuti). In caso di errore 429 aspetta e riprova da solo.

Produce: validazione_quote_report.txt, validazione_quote_dettaglio.csv, quote_sospette.csv
"""
import argparse, csv, glob, json, math, os, random, statistics, sys, time, urllib.parse, urllib.request, urllib.error

CSV_EVENTI = "incidenti_altoadige_con_quota.csv"
CACHE = "cache_quote.json"
DELAY = 2.0
HEADERS = {"User-Agent": "valida-quote/1.0 (uso personale)"}
OVERPASS = "https://overpass-api.de/api/interpreter"
BBOX = "46.15,10.30,47.15,12.60"
BANDE = [1000, 1500, 2000, 2500]           # le fasce di quota usate nelle analisi
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 46.15, 47.15, 10.30, 12.60
ELE_MIN, ELE_MAX = 190, 3910               # quote plausibili per l'Alto Adige (m)

OUT = []                                    # righe del report


def say(s=""):
    print(s)
    OUT.append(s)


# ------------------------------------------------------------------ dati
def find_csv():
    if os.path.exists(CSV_EVENTI):
        return CSV_EVENTI
    alt = sorted(glob.glob("incidenti*quota*.csv"))
    if alt:
        return alt[0]
    sys.exit(f"Manca {CSV_EVENTI} in {os.getcwd()}: copialo qui e rilancia.")


def num(v):
    try:
        return float(str(v).lower().replace("m", "").replace(",", ".").strip())
    except ValueError:
        return None


def read_events():
    ev = {}
    with open(find_csv(), newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            e = ev.setdefault(r["id_evento"], dict(
                id=r["id_evento"], data=r["data"], comune=r["comune"],
                lat=float(r["lat"].replace(",", ".")), lon=float(r["lon"].replace(",", ".")),
                quota=float(r["quota_m"]), escursionismo=0))
            if r["attivita"] == "Escursionismo":
                e["escursionismo"] = 1
    return list(ev.values())


def banda(q):
    return sum(1 for b in BANDE if q >= b)


def nome_banda(i):
    lim = [0] + BANDE + [4000]
    return f"{lim[i]}-{lim[i + 1]} m"


# ------------------------------------------------------------------ statistiche
def pct(vals, p):
    v = sorted(vals)
    if not v:
        return float("nan")
    k = (len(v) - 1) * p / 100
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def riga_stat(nome, diffs):
    """diffs = differenze con segno (altra fonte - quota nel file), in metri."""
    d = [x for x in diffs if x is not None]
    if not d:
        return f"  {nome:<34} nessun dato"
    a = [abs(x) for x in d]
    return (f"  {nome:<34} n={len(d):<4} bias {statistics.mean(d):+6.1f} m | |err| mediano {statistics.median(a):5.1f} m"
            f" | p90 {pct(a, 90):5.1f} m | entro 10 m {100 * sum(x <= 10 for x in a) / len(a):4.0f}%"
            f" | entro 25 m {100 * sum(x <= 25 for x in a) / len(a):4.0f}%")


# ------------------------------------------------------------------ servizi di quota (con cache)
_cache = {}


def load_cache():
    global _cache
    if os.path.exists(CACHE):
        try:
            _cache = json.load(open(CACHE))
        except Exception:  # noqa: BLE001
            _cache = {}


def save_cache():
    json.dump(_cache, open(CACHE, "w"))


def key(ds, lat, lon):
    return f"{ds}|{lat:.6f}|{lon:.6f}"


def http_json(url, data=None):
    req = urllib.request.Request(url, data=data, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _opentopo(ds):
    def f(batch):
        locs = "|".join(f"{lat:.6f},{lon:.6f}" for lat, lon in batch)
        d = http_json(f"https://api.opentopodata.org/v1/{ds}?locations={locs}")
        if d.get("status") != "OK":
            raise ValueError(d.get("error", "risposta non OK"))
        return [x["elevation"] for x in d["results"]]
    return f


def _openmeteo(batch):
    url = ("https://api.open-meteo.com/v1/elevation?latitude=" + ",".join(f"{la:.6f}" for la, _ in batch)
           + "&longitude=" + ",".join(f"{lo:.6f}" for _, lo in batch))
    return http_json(url)["elevation"]


PROVIDERS = {
    "eudem": ("OpenTopoData EU-DEM 25 m", _opentopo("eudem25m")),
    "cop90": ("Open-Meteo / Copernicus 90 m", _openmeteo),
}


def elev(prov, pts, batch=100):
    """Restituisce {(lat,lon): quota} per la fonte prov, usando/aggiornando la cache."""
    name, fn = PROVIDERS[prov]
    todo = [p for p in dict.fromkeys(pts) if key(prov, *p) not in _cache]
    for i in range(0, len(todo), batch):
        b = todo[i:i + batch]
        for attempt in range(5):
            try:
                res = fn(b)
                if len(res) != len(b):
                    raise ValueError("risposta incompleta")
                break
            except (urllib.error.URLError, ValueError, KeyError) as e:
                wait = (30 if isinstance(e, urllib.error.HTTPError) and e.code == 429 else 5) * (attempt + 1)
                print(f"    {name}: errore ({e}); riprovo tra {wait}s")
                time.sleep(wait)
        else:
            save_cache()
            sys.exit(f"{name} non risponde: il lavoro fatto e' in cache, riprova piu' tardi (o cambia rete/VPN).")
        for p, z in zip(b, res):
            _cache[key(prov, *p)] = z
        save_cache()
        print(f"    {name}: {min(i + batch, len(todo))}/{len(todo)}")
        time.sleep(DELAY)
    return {p: _cache.get(key(prov, *p)) for p in pts}


def overpass_ele_points():
    """Rifugi, selle e cime con tag ele, da OSM. Restituisce [(tipo, lat, lon, ele, nome)]."""
    q = (f'[out:json][timeout:180][bbox:{BBOX}];'
         '(node["tourism"="alpine_hut"]["ele"];node["natural"="saddle"]["ele"];node["natural"="peak"]["ele"];);out;')
    data = urllib.parse.urlencode({"data": q}).encode()
    for attempt in range(4):
        try:
            d = http_json(OVERPASS, data)
            break
        except Exception as e:  # noqa: BLE001
            wait = 30 * (attempt + 1)
            print(f"    Overpass: errore ({e}); riprovo tra {wait}s")
            time.sleep(wait)
    else:
        return None
    out = []
    for e in d.get("elements", []):
        t = e.get("tags", {})
        ele = num(t.get("ele"))
        if ele is None or not (ELE_MIN <= ele <= ELE_MAX):
            continue
        tipo = "rifugio" if t.get("tourism") == "alpine_hut" else ("sella" if t.get("natural") == "saddle" else "cima")
        out.append((tipo, e["lat"], e["lon"], ele, t.get("name", "")))
    return out


# ------------------------------------------------------------------ TEST 0: coordinate sospette (offline)
def suspects(events):
    from collections import Counter
    c = Counter((round(e["lat"], 5), round(e["lon"], 5)) for e in events)
    bad = {}
    for e in events:
        k = (round(e["lat"], 5), round(e["lon"], 5))
        grid3 = abs(e["lat"] * 1000 - round(e["lat"] * 1000)) < 0.01 and abs(e["lon"] * 1000 - round(e["lon"] * 1000)) < 0.01
        if c[k] >= 5 and grid3:
            bad[e["id"]] = ("segnaposto", c[k])
        elif c[k] >= 10:
            bad[e["id"]] = ("punto ripetuto", c[k])
        if not (LAT_MIN <= e["lat"] <= LAT_MAX and LON_MIN <= e["lon"] <= LON_MAX):
            bad[e["id"]] = ("fuori Alto Adige", 1)
        if not (ELE_MIN <= e["quota"] <= ELE_MAX):
            bad[e["id"]] = ("quota fuori range", 1)
    return bad


def test0(events):
    say("=" * 100)
    say("TEST 0 - coordinate sospette e controlli di coerenza (senza internet)")
    say("=" * 100)
    bad = suspects(events)
    by = {}
    for e in events:
        if e["id"] in bad:
            by.setdefault(bad[e["id"]][0], []).append(e)
    for motivo, lst in by.items():
        qs = sorted({e["quota"] for e in lst})
        say(f"  {motivo}: {len(lst)} eventi, comuni: {sorted({e['comune'] for e in lst})[:5]}, "
            f"quote: {qs[:4]}{'...' if len(qs) > 4 else ''}, periodo {min(e['data'] for e in lst)} -> {max(e['data'] for e in lst)}")
    if not by:
        say("  Nessun punto sospetto.")
    with open("quote_sospette.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id_evento", "data", "comune", "lat", "lon", "quota_m", "motivo", "volte_stesse_coordinate"])
        for e in events:
            if e["id"] in bad:
                m, n = bad[e["id"]]
                w.writerow([e["id"], e["data"], e["comune"], str(e["lat"]).replace(".", ","), str(e["lon"]).replace(".", ","),
                            round(e["quota"]), m, n])
    say("  -> quote_sospette.csv")
    say("  Nota: i 'punti ripetuti' sono spesso luoghi reali (rifugi, parcheggi, forcelle) dove il soccorso registra sempre la")
    say("  stessa posizione. Per la quota va bene, ma significa che la coordinata non e' il punto esatto dell'incidente.")
    return bad


# ------------------------------------------------------------------ campione
def campione(events, bad, n, seed):
    pool = [e for e in events if e["id"] not in bad or bad[e["id"]][0] == "punto ripetuto"]
    random.seed(seed)
    strati = {}
    for e in pool:
        strati.setdefault(banda(e["quota"]), []).append(e)
    out = []
    per = max(1, n // len(strati))
    for b, lst in sorted(strati.items()):
        random.shuffle(lst)
        out += lst[:per]
    return out


# ------------------------------------------------------------------ TEST A: seconda fonte indipendente
def testA(sample):
    say("")
    say("=" * 100)
    say("TEST A - la quota cambia se la chiedo a un'altra fonte? (Copernicus 90 m e' indipendente da EU-DEM)")
    say("=" * 100)
    pts = [(e["lat"], e["lon"]) for e in sample]
    z_eu = elev("eudem", pts)
    z_cp = elev("cop90", pts)
    rows = []
    for e in sample:
        p = (e["lat"], e["lon"])
        e["z_eudem"], e["z_cop"] = z_eu[p], z_cp[p]
    say(riga_stat("EU-DEM (richiesta ora) - file", [None if e["z_eudem"] is None else e["z_eudem"] - e["quota"] for e in sample]))
    say(riga_stat("Copernicus 90 m - file", [None if e["z_cop"] is None else e["z_cop"] - e["quota"] for e in sample]))
    say("  (la prima riga deve essere ~0: conferma che il file e' riproducibile)")
    say("")
    say("  Copernicus - file, per fascia di quota:")
    for b in sorted({banda(e["quota"]) for e in sample}):
        s = [e for e in sample if banda(e["quota"]) == b]
        say("  " + riga_stat(nome_banda(b), [None if e["z_cop"] is None else e["z_cop"] - e["quota"] for e in s]).lstrip())
    cambio = [e for e in sample if e["z_cop"] is not None]
    flip = sum(1 for e in cambio if banda(e["z_cop"]) != banda(e["quota"]))
    say(f"\n  Eventi che cambierebbero fascia ({'/'.join(map(str, BANDE))} m) usando Copernicus: {flip}/{len(cambio)} = {100 * flip / len(cambio):.1f}%")
    return sample


# ------------------------------------------------------------------ TEST B: errore di posizione
OFFS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]


def ring(lat, lon, d):
    out = []
    for dy, dx in OFFS:
        k = 1 / math.hypot(dx, dy)
        out.append((lat + dy * k * d / 110574.0, lon + dx * k * d / (111320.0 * math.cos(math.radians(lat)))))
    return out


def testB(sample):
    say("")
    say("=" * 100)
    say("TEST B - quanto cambia la quota se la posizione registrata e' sbagliata? (EU-DEM, 8 direzioni)")
    say("=" * 100)
    allpts = []
    for e in sample:
        for d in (50, 100):
            allpts += ring(e["lat"], e["lon"], d)
    z = elev("eudem", allpts)
    for e in sample:
        for d in (50, 100):
            zz = [z[p] for p in ring(e["lat"], e["lon"], d)]
            zz = [x for x in zz if x is not None]
            e[f"dmax{d}"] = max(abs(x - e["quota"]) for x in zz) if zz else None
            e[f"dmed{d}"] = statistics.median([abs(x - e["quota"]) for x in zz]) if zz else None
            e[f"flip{d}"] = int(any(banda(x) != banda(e["quota"]) for x in zz)) if zz else None
    for d in (50, 100):
        say(f"\n  Posizione spostata di {d} m:")
        for lab, f in [("tutti", lambda e: True), ("solo escursionismo", lambda e: e["escursionismo"])]:
            s = [e for e in sample if f(e) and e[f"dmed{d}"] is not None]
            if not s:
                continue
            tip = [e[f"dmed{d}"] for e in s]
            worst = [e[f"dmax{d}"] for e in s]
            say(f"    {lab:<20} n={len(s):<4} variazione tipica (mediana 8 dir.): mediana {statistics.median(tip):5.1f} m, p90 {pct(tip, 90):5.1f} m"
                f" | caso peggiore: mediana {statistics.median(worst):5.1f} m, p90 {pct(worst, 90):5.1f} m")
            say(f"    {'':<20} cambiano fascia in almeno una direzione: {100 * sum(e[f'flip{d}'] for e in s) / len(s):.0f}%"
                f"  (fasce {'/'.join(map(str, BANDE))} m)")
    say("\n  Per fascia di quota (spostamento 100 m, variazione tipica / caso peggiore, mediana):")
    for b in sorted({banda(e["quota"]) for e in sample}):
        s = [e for e in sample if banda(e["quota"]) == b and e["dmed100"] is not None]
        if s:
            say(f"    {nome_banda(b):<12} n={len(s):<4} {statistics.median([e['dmed100'] for e in s]):5.1f} m / {statistics.median([e['dmax100'] for e in s]):5.1f} m")
    return sample


# ------------------------------------------------------------------ TEST C: verita' a terra (OSM ele)
def testC(n, seed):
    say("")
    say("=" * 100)
    say("TEST C - le fonti altimetriche riproducono le quote note di rifugi, selle e cime? (tag 'ele' di OpenStreetMap)")
    say("=" * 100)
    pts = overpass_ele_points()
    if not pts:
        say("  Overpass non raggiungibile: salto il test C.")
        return []
    random.seed(seed)
    rows = []
    for tipo in ("rifugio", "sella", "cima"):
        lst = [p for p in pts if p[0] == tipo]
        random.shuffle(lst)
        rows += lst[:max(50, n // 3)]
    say(f"  Punti OSM con quota nota: {len(pts)} (usati {len(rows)})")
    pp = [(r[1], r[2]) for r in rows]
    z_eu, z_cp = elev("eudem", pp), elev("cop90", pp)
    det = []
    for tipo, lat, lon, ele, nome in rows:
        det.append(dict(tipo=tipo, nome=nome, lat=lat, lon=lon, ele=ele, z_eudem=z_eu[(lat, lon)], z_cop=z_cp[(lat, lon)]))
    for tipo in ("rifugio", "sella", "cima"):
        s = [d for d in det if d["tipo"] == tipo]
        say(riga_stat(f"EU-DEM - ele OSM ({tipo})", [None if d["z_eudem"] is None else d["z_eudem"] - d["ele"] for d in s]))
        say(riga_stat(f"Copernicus - ele OSM ({tipo})", [None if d["z_cop"] is None else d["z_cop"] - d["ele"] for d in s]))
    say("  Come leggerla: rifugi e selle sono punti 'tipici' dove si cammina; sulle cime le fonti sottostimano sempre")
    say("  (la vetta e' un picco stretto, la griglia lo smussa). Anche il tag 'ele' di OSM puo' essere impreciso.")
    return det


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400, help="eventi nel campione (test A e B)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--test", default="0,A,B,C", help="quali test: 0,A,B,C")
    a = ap.parse_args()
    tests = {t.strip().upper() for t in a.test.split(",")}
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    load_cache()
    events = read_events()
    say(f"Eventi nel file: {len(events)}")
    bad = test0(events) if "0" in tests else suspects(events)
    sample = campione(events, bad, a.n, a.seed)
    dettaglio = []
    if "A" in tests or "B" in tests:
        say(f"\nCampione per i test A e B: {len(sample)} eventi, stratificato per fascia di quota, senza segnaposto.")
    if "A" in tests:
        testA(sample)
    if "B" in tests:
        testB(sample)
    det_c = testC(a.n, a.seed) if "C" in tests else []
    if sample and ("A" in tests or "B" in tests):
        with open("validazione_quote_dettaglio.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            cols = ["id", "data", "comune", "lat", "lon", "quota", "escursionismo", "z_eudem", "z_cop", "dmed50", "dmax50", "dmed100", "dmax100", "flip100"]
            w.writerow(cols)
            for e in sample:
                w.writerow([str(round(e[c], 2) if isinstance(e.get(c), float) else e.get(c, "")).replace(".", ",") for c in cols])
    if det_c:
        with open("validazione_quote_osm.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["tipo", "nome", "lat", "lon", "ele_osm", "z_eudem", "z_cop"])
            for d in det_c:
                w.writerow([d["tipo"], d["nome"], d["lat"], d["lon"], d["ele"], d["z_eudem"], d["z_cop"]])
    open("validazione_quote_report.txt", "w", encoding="utf-8").write("\n".join(OUT) + "\n")
    print("\nScritti: validazione_quote_report.txt" + (", validazione_quote_dettaglio.csv" if sample else "")
          + (", validazione_quote_osm.csv" if det_c else "") + ", quote_sospette.csv")


if __name__ == "__main__":
    main()
