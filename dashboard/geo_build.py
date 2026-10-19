import json, shapely
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from pyproj import Transformer
T = Transformer.from_crs(4326, 25832, always_xy=True)
def q(x, y): return [round((x - 600000) / 50), round((y - 5150000) / 50)]
def rings_of(g):
    polys = [g] if g.geom_type == 'Polygon' else list(g.geoms)
    out = []
    for p in polys:
        out.append(list(p.exterior.coords))
        out += [list(r.coords) for r in p.interiors]
    return out
def enc(coords):
    pts = [q(x, y) for x, y in coords]
    dd = [pts[0]]
    for a in pts[1:]:
        if a != dd[-1]: dd.append(a)
    if len(dd) > 1 and dd[0] == dd[-1]: dd = dd[:-1]
    if len(dd) < 3: return None
    flat = [dd[0][0], dd[0][1]]
    for a, b in zip(dd, dd[1:]): flat += [b[0] - a[0], b[1] - a[1]]
    return flat
def build(cidx, path='bz_comuni.geojson', tol=70):
    d = json.load(open(path))
    feats = []
    for f in d['features']:
        g = shape(f['geometry'])
        g = shapely.transform(g, lambda a: __import__('numpy').column_stack(T.transform(a[:, 0], a[:, 1])))
        feats.append((int(f['properties']['com_istat_code_num']), f['properties']['name'], g))
    simp = shapely.coverage_simplify([g for _, _, g in feats], tol)
    items = []
    for (code, name, _), g in zip(feats, simp):
        if code not in cidx: print('comune senza indice:', code, name); continue
        rp = g.representative_point()
        rings = [r for r in (enc(c) for c in rings_of(g)) if r]
        items.append(dict(c=cidx[code], r=rings, l=q(rp.x, rp.y)))
    outline = unary_union(list(simp))
    # outline = solo anelli esterni
    outer = [enc(list(p.exterior.coords)) for p in ([outline] if outline.geom_type == 'Polygon' else outline.geoms)]
    n = sum(len(i['r']) for i in items)
    print('comuni:', len(items), 'anelli:', n, 'vertici:', sum(len(r) // 2 for i in items for r in i['r']))
    return dict(comuni=items, outline=[o for o in outer if o])
