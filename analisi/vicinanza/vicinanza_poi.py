#!/usr/bin/env python3
"""
Vicinanza degli eventi di soccorso (escursionismo) a rifugi, bivacchi, malghe e impianti di risalita.

File richiesti nella stessa cartella dello script:
  incidenti_altoadige_con_quota.csv   (quello che ti ho inviato)
  poi.geojson                         (export di overpass_poi.overpassql da Overpass Turbo)
Facoltativo, per il confronto con i sentieri:
  sentieri.json                       (export di overpass_sentieri_baseline.overpassql)

Uso:
  python3 vicinanza_poi.py                       # anno 2025, solo escursionismo
  python3 vicinanza_poi.py --anno 2024
  python3 vicinanza_poi.py --anno tutti --stagione estate
  python3 vicinanza_poi.py --scarica             # scarica poi.geojson e sentieri.json da Overpass
  python3 vicinanza_poi.py --raggi 250,500,1000,2000,3000

Solo libreria standard di Python 3.8+. Produce:
  eventi_vicinanza.csv   un evento per riga con le distanze (m) dal punto più vicino di ogni tipo
  riepilogo_vicinanza.csv   quota di eventi entro ciascun raggio (ed eventuale confronto con i sentieri)
"""
import argparse, csv, json, math, os, random, statistics, sys, time, urllib.request, urllib.parse

CSV_EVENTI = "incidenti_altoadige_con_quota.csv"
POI_FILE = "poi.geojson"
SENTIERI_FILE = "sentieri.json"
OVERPASS = "https://overpass-api.de/api/interpreter"

MAIN_LIFTS = {"cable_car", "gondola", "mixed_lift", "chair_lift", "funicular"}
SKI_LIFTS = {"j-bar", "t-bar", "platter", "rope_tow", "magic_carpet", "drag_lift"}

# Proiezione piana locale (metri). Per l'Alto Adige l'errore è inferiore all'1,5%.
LAT0, LON0 = 46.65, 11.45
KY = 110574.0
KX = 111320.0 * math.cos(math.radians(LAT0))


def proj(lon, lat):
    return ((lon - LON0) * KX, (lat - LAT0) * KY)


# ---------------------------------------------------------------- lettura dati
def read_query_text(path):
    txt = open(path, encoding="utf-8").read()
    return txt[txt.index("[out:json]"):]


def fetch(query_file, out_file):
    q = read_query_text(query_file)
    print(f"Scarico {out_file} da Overpass (può richiedere qualche minuto)...")
    data = urllib.parse.urlencode({"data": q}).encode()
    req = urllib.request.Request(OVERPASS, data=data, headers={"User-Agent": "vicinanza-poi/1.0 (uso personale)"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=400) as r:
                payload = r.read()
            open(out_file, "wb").write(payload)
            print(f"  salvato {out_file} ({len(payload)//1024} KB)")
            return
        except Exception as e:  # noqa: BLE001
            wait = 30 * (attempt + 1)
            print(f"  errore ({e}); riprovo tra {wait}s")
            time.sleep(wait)
    sys.exit("Overpass non risponde: riprova più tardi o usa Overpass Turbo a mano.")


def feat_from_geojson(f):
    props = dict(f.get("properties") or {})
    if isinstance(props.get("tags"), dict):
        props.update(props["tags"])
    g = f.get("geometry") or {}
    t, c = g.get("type"), g.get("coordinates")
    if t == "Point":
        return props, "point", [tuple(c[:2])]
    if t == "LineString":
        return props, "line", [tuple(p[:2]) for p in c]
    if t == "MultiLineString":
        return props, "line", [tuple(p[:2]) for part in c for p in part]
    if t == "Polygon":
        return props, "area", [tuple(p[:2]) for p in c[0]]
    if t == "MultiPolygon":
        return props, "area", [tuple(p[:2]) for poly in c for p in poly[0]]
    return None


def load_features(path):
    """Restituisce [(tags, kind, [(lon,lat),...])] da GeoJSON (Overpass Turbo) o JSON grezzo Overpass."""
    d = json.load(open(path, encoding="utf-8"))
    out = []
    if d.get("type") == "FeatureCollection":
        for f in d["features"]:
            r = feat_from_geojson(f)
            if r:
                out.append(r)
    else:
        for e in d.get("elements", []):
            tags = e.get("tags", {})
            if e["type"] == "node":
                out.append((tags, "point", [(e["lon"], e["lat"])]))
            elif "geometry" in e:
                pts = [(p["lon"], p["lat"]) for p in e["geometry"]]
                closed = len(pts) > 2 and pts[0] == pts[-1]
                out.append((tags, "area" if closed else "line", pts))
            elif "center" in e:
                out.append((tags, "point", [(e["center"]["lon"], e["center"]["lat"])]))
    return out


# ---------------------------------------------------------------- indice spaziale
class Grid:
    def __init__(self, cell=500.0):
        self.cell = cell
        self.cells = {}
        self.n = 0

    def add(self, x, y, label):
        k = (int(x // self.cell), int(y // self.cell))
        self.cells.setdefault(k, []).append((x, y, label))
        self.n += 1

    def nearest(self, x, y, rmax=20000.0):
        cx, cy = int(x // self.cell), int(y // self.cell)
        best, bl = float("inf"), None
        kmax = int(rmax // self.cell) + 1
        for k in range(kmax + 1):
            for i in range(cx - k, cx + k + 1):
                for j in range(cy - k, cy + k + 1):
                    if max(abs(i - cx), abs(j - cy)) != k:
                        continue
                    for (px, py, lab) in self.cells.get((i, j), ()):
                        d = math.hypot(px - x, py - y)
                        if d < best:
                            best, bl = d, lab
            if best <= k * self.cell:
                break
        return (best, bl) if best <= rmax else (None, None)


def densify(pts, step=25.0):
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(L // step))
        for i in range(n):
            t = i / n
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    out.append(pts[-1])
    return out


def centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def num(v):
    try:
        return float(str(v).lower().replace("m", "").replace(",", ".").strip())
    except ValueError:
        return None


def build_indexes(features, ele_min_malghe):
    g_main_st, g_ski, g_rif, g_biv, g_malga = (Grid() for _ in range(5))
    main_pts = Grid(100.0)       # linee degli impianti principali (per riconoscere le stazioni)
    stations = []
    counts = dict(rifugi=0, bivacchi=0, malghe=0, impianti_principali=0, skilift=0, stazioni=0)
    for tags, kind, ll in features:
        pts = [proj(lon, lat) for lon, lat in ll]
        name = tags.get("name") or tags.get("name:it") or tags.get("name:de") or ""
        aw = tags.get("aerialway")
        if aw in MAIN_LIFTS and kind in ("line", "area"):
            counts["impianti_principali"] += 1
            for p in densify(pts):
                main_pts.add(p[0], p[1], name)
            for p in (pts[0], pts[-1]):  # capilinea
                g_main_st.add(p[0], p[1], name or "capolinea " + aw)
        elif aw in SKI_LIFTS and kind in ("line", "area"):
            counts["skilift"] += 1
            for p in densify(pts):
                g_ski.add(p[0], p[1], name or aw)
        elif aw == "station" and kind == "point":
            stations.append((pts[0], name))
        elif tags.get("tourism") == "alpine_hut":
            counts["rifugi"] += 1
            c = centroid(pts) if kind != "point" else pts[0]
            g_rif.add(c[0], c[1], name or "rifugio senza nome")
        elif tags.get("tourism") == "wilderness_hut" or (tags.get("amenity") == "shelter" and tags.get("shelter_type") == "basic_hut"):
            counts["bivacchi"] += 1
            c = centroid(pts) if kind != "point" else pts[0]
            g_biv.add(c[0], c[1], name or "bivacco senza nome")
        elif tags.get("amenity") in ("restaurant", "cafe", "pub", "fast_food"):
            ele = num(tags.get("ele"))
            if ele is not None and ele < ele_min_malghe:
                continue
            counts["malghe"] += 1
            c = centroid(pts) if kind != "point" else pts[0]
            g_malga.add(c[0], c[1], name or "ristoro senza nome")
    # stazioni (nodi) che stanno su un impianto principale (entro 50 m dalla linea)
    for (x, y), name in stations:
        d, _ = main_pts.nearest(x, y, rmax=50.0)
        if d is not None:
            counts["stazioni"] += 1
            g_main_st.add(x, y, name or "stazione")
    return dict(impianto=g_main_st, skilift=g_ski, rifugio=g_rif, bivacco=g_biv, malga=g_malga), counts


# ---------------------------------------------------------------- eventi
def find_events_csv():
    import glob
    if os.path.exists(CSV_EVENTI):
        return CSV_EVENTI
    alt = sorted(glob.glob("incidenti*quota*.csv"))
    if alt:
        return alt[0]
    sys.exit(f"Manca {CSV_EVENTI} in questa cartella (" + os.getcwd() + ").\n"
             "Copia qui il file CSV degli incidenti con la quota (quello che ti ho inviato in chat) e rilancia.")


def read_events(anno, stagione, solo_escursionismo):
    ev = {}
    path = find_events_csv()
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            d = r["data"]
            if anno != "tutti" and not d.startswith(anno):
                continue
            m = int(d[5:7])
            if stagione == "estate" and not (5 <= m <= 10):
                continue
            if stagione == "inverno" and (5 <= m <= 10):
                continue
            e = ev.setdefault(r["id_evento"], dict(
                id=r["id_evento"], data=d, comune=r["comune"],
                lat=float(r["lat"].replace(",", ".")), lon=float(r["lon"].replace(",", ".")),
                quota=int(r["quota_m"]), escursionismo=0, persone=0))
            e["persone"] += 1
            if r["attivita"] == "Escursionismo":
                e["escursionismo"] = 1
    rows = list(ev.values())
    if solo_escursionismo:
        rows = [e for e in rows if e["escursionismo"]]
    return rows


def distances(points_xy, idx):
    res = []
    for (x, y) in points_xy:
        r = {}
        for k, g in idx.items():
            d, lab = g.nearest(x, y)
            r[k] = (d, lab)
        cand = [v[0] for k, v in r.items() if k in ("impianto", "rifugio", "bivacco", "malga") and v[0] is not None]
        r["qualsiasi"] = (min(cand) if cand else None, None)
        cand2 = [r[k][0] for k in ("rifugio", "bivacco") if r[k][0] is not None]
        r["rifugio_o_bivacco"] = (min(cand2) if cand2 else None, None)
        res.append(r)
    return res


def share(values, raggio):
    return sum(1 for x in values if x is not None and x <= raggio) / len(values) if values else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anno", default="2025", help="anno (es. 2025) oppure 'tutti'")
    ap.add_argument("--stagione", default="tutte", choices=["tutte", "estate", "inverno"])
    ap.add_argument("--tutte-le-attivita", action="store_true", help="non limitare all'escursionismo")
    ap.add_argument("--raggi", default="250,500,1000,2000,3000")
    ap.add_argument("--quota-minima-malghe", type=float, default=1000, help="scarta ristori con tag ele inferiore (m)")
    ap.add_argument("--scarica", action="store_true", help="scarica poi.geojson e sentieri.json da Overpass")
    ap.add_argument("--campioni-sentieri", type=int, default=5000)
    a = ap.parse_args()
    raggi = [int(x) for x in a.raggi.split(",")]

    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)
    if a.scarica:
        fetch("overpass_poi.overpassql", POI_FILE)
        fetch("overpass_sentieri_baseline.overpassql", SENTIERI_FILE)
    if not os.path.exists(POI_FILE):
        sys.exit(f"Manca {POI_FILE}: esegui overpass_poi.overpassql su Overpass Turbo e salva l'export GeoJSON, oppure lancia con --scarica.")

    feats = load_features(POI_FILE)
    idx, cnt = build_indexes(feats, a.quota_minima_malghe)
    print("Punti di interesse letti:", ", ".join(f"{k}={v}" for k, v in cnt.items()))
    if cnt["rifugi"] == 0 and cnt["impianti_principali"] == 0:
        sys.exit("Nessun rifugio né impianto trovato: controlla poi.geojson.")

    events = read_events(a.anno, a.stagione, not a.tutte_le_attivita)
    print(f"Eventi analizzati: {len(events)} (anno {a.anno}, stagione {a.stagione}, "
          f"{'tutte le attività' if a.tutte_le_attivita else 'solo escursionismo'})")
    if not events:
        sys.exit("Nessun evento con questi filtri.")
    dist = distances([proj(e["lon"], e["lat"]) for e in events], idx)

    labels = dict(impianto="impianti principali (funivie, cabinovie, seggiovie)", skilift="skilift",
                  rifugio="rifugi serviti", bivacco="bivacchi", malga="malghe/ristori", rifugio_o_bivacco="rifugi o bivacchi",
                  qualsiasi="rifugio, bivacco, malga o impianto principale")
    order = ["impianto", "rifugio", "rifugio_o_bivacco", "malga", "skilift", "qualsiasi"]

    # file per evento
    with open("eventi_vicinanza.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id_evento", "data", "comune", "lat", "lon", "quota_m", "escursionismo", "persone"]
                   + [f"dist_{k}_m" for k in order] + ["nome_impianto", "nome_rifugio", "nome_malga"])
        for e, r in zip(events, dist):
            def dv(k):
                v = r[k][0]
                return "" if v is None else round(v)
            w.writerow([e["id"], e["data"], e["comune"], str(e["lat"]).replace(".", ","), str(e["lon"]).replace(".", ","),
                        e["quota"], e["escursionismo"], e["persone"]] + [dv(k) for k in order]
                       + [r["impianto"][1] or "", r["rifugio"][1] or "", r["malga"][1] or ""])

    # baseline: centri dei sentieri
    base = None
    if os.path.exists(SENTIERI_FILE):
        tr = [proj(*ll[0]) for (_, _kind, ll) in load_features(SENTIERI_FILE) if ll]
        random.seed(1)
        if len(tr) > a.campioni_sentieri:
            tr = random.sample(tr, a.campioni_sentieri)
        base = distances(tr, idx)
        print(f"Confronto con {len(tr)} punti su sentieri segnati.")

    # riepilogo
    print()
    head = f"{'Distanza da':<48}" + "".join(f"{'≤'+str(r)+' m':>10}" for r in raggi) + f"{'mediana':>10}"
    print(head)
    print("-" * len(head))
    rows_out = []
    for k in order:
        vals = [r[k][0] for r in dist]
        known = [v for v in vals if v is not None]
        med = statistics.median(known) if known else float("nan")
        line = f"{'Eventi - ' + labels[k]:<48}" + "".join(f"{share(vals, r)*100:>9.0f}%" for r in raggi) + f"{med:>9.0f}m"
        print(line)
        rows_out.append(["eventi", labels[k]] + [round(share(vals, r) * 100, 1) for r in raggi] + [round(med)])
        if base:
            bv = [r[k][0] for r in base]
            bm = statistics.median([v for v in bv if v is not None])
            print(f"{'  sentieri (confronto) - ' + labels[k]:<48}" + "".join(f"{share(bv, r)*100:>9.0f}%" for r in raggi) + f"{bm:>9.0f}m")
            rows_out.append(["sentieri", labels[k]] + [round(share(bv, r) * 100, 1) for r in raggi] + [round(bm)])
    with open("riepilogo_vicinanza.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["gruppo", "distanza_da"] + [f"entro_{r}_m_%" for r in raggi] + ["mediana_m"])
        w.writerows(rows_out)
    print("\nScritti: eventi_vicinanza.csv, riepilogo_vicinanza.csv")
    print("Nota: le quote % sono sul totale degli eventi; con pochi eventi i valori sono instabili.")


if __name__ == "__main__":
    main()
