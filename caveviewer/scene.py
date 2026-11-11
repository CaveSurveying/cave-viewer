"""The 3D view of one cave: its scene (scene.json and terrain.bin), the
page (index.html, from viewer/viewer.html) and what it needs offline.

From the cave's centreline (a Survex .3d), its names (names.json, from the
survey step), the ground over it (caveviewer.terrain) and, where the config
gives them, its passage walls (a Therion .lox). The centreline also goes in
as a graph, which the page finds routes through. The satellite imagery is
loaded by the page itself, from Esri.
"""
import datetime
import heapq
import html
import json
import math
import os
import re
import sys

from caveviewer.formats import read_3d, read_lox_walls
from caveviewer.geo import TO_LL, fit_affine, grid_ref, mercator
from caveviewer.offline import offline
from caveviewer.preview import preview
from caveviewer.terrain import CREDITS, ground

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.join(HERE, 'viewer')
DRAWN_CREDITS = {'therion-svg': "Drawn survey: the same data's drawings, by Therion", 'scan': 'Drawn survey', 'none': ''}


# -- names and routes -----------------------------------------------------------------

def parts(g, dry=False):
    """The graph's connected parts (dry: without going through a sump), as a
    list of node lists, largest first."""
    n = len(g['stn'])
    adj = [[] for _ in range(n)]
    e, wet = g['edges'], set(g.get('wet', ()))
    for k in range(0, len(e), 2):
        if dry and e[k] in wet and e[k + 1] in wet:
            continue
        adj[e[k]].append(e[k + 1])
        adj[e[k + 1]].append(e[k])
    seen, out = [False] * n, []
    for s in range(n):
        if seen[s]:
            continue
        part, todo, seen[s] = [], [s], True
        while todo:
            i = todo.pop()
            part.append(i)
            for j in adj[i]:
                if not seen[j]:
                    seen[j] = True
                    todo.append(j)
        out.append(part)
    return sorted(out, key=len, reverse=True)


def main_part(g, dry=False):
    """The nodes of the largest connected part of the graph (dry: without
    going through a sump)."""
    return parts(g, dry)[0]

PLACE_R, PLACE_DZ = 25, 15     # metres: how near a place a station takes its name
AVOID = 20                      # names.json's avoid: a leg to or from one of its stations counts as this many times as far


def namer(names, stations, codes_first=True):
    """station name -> passage name, or None: by its top-level survey, else
    by the pattern of its code (a passage's own survey series), else the
    nearest place on the drawn survey (within PLACE_R across and PLACE_DZ up
    or down); or (not codes_first) the nearest place before the code."""
    surveys = names.get('surveys', {})
    codes = [(re.compile(k), v) for k, v in names.get('codes', {}).items()]
    where = {n: p for n, p, f in stations if n}
    cells = {}
    alone = set(names.get('alone', []))
    for t, k in names.get('places', {}).items():
        if k in where and t not in alone:
            p = where[k]
            cells.setdefault((p[0] // PLACE_R, p[1] // PLACE_R), []).append((t, p))
    near = {}

    def place(n):
        if n not in near:
            p, best = where.get(n), None
            if p:
                cx, cy = p[0] // PLACE_R, p[1] // PLACE_R
                for t, q in (x for i in (-1, 0, 1) for j in (-1, 0, 1) for x in cells.get((cx + i, cy + j), ())):
                    d = math.hypot(p[0] - q[0], p[1] - q[1])
                    if d <= PLACE_R and abs(p[2] - q[2]) <= PLACE_DZ and (best is None or d < best[0]):
                        best = (d, t)
            near[n] = best and best[1]
        return near[n]

    def name(n):
        t = surveys.get(n.split('.')[0])
        code = lambda: next((v for r, v in codes if r.search(n)), None)
        return t or (code() or place(n) if codes_first else place(n) or code())
    return name


def place_names(stations, name, at=None):
    """One label per passage name: a place at its own station (at: {name:
    station}), any other name at the station nearest the middle of all its
    stations."""
    at = at or {}
    where = {n: p for n, p, f in stations if n}
    by = {}
    for n, p, f in stations:
        t = n and name(n)
        if t and not f & 1:
            by.setdefault(t, []).append(p)
    out = []
    for t, ps in by.items():
        if at.get(t) in where:
            out.append((t, *where[at[t]]))
            continue
        mx, my = sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps)
        p = min(ps, key=lambda p: math.hypot(p[0] - mx, p[1] - my))
        out.append((t, *p))
    # and the places that lend their name to no passage (names.json's alone), at their own stations
    out += [(t, *where[k]) for t, k in at.items() if t not in by and k in where]
    return out


JOIN = 3.0         # metres: a piece of the survey this near another is joined to it


def join(pos, edges, within=JOIN):
    """Pieces of the survey that were meant to meet but don't quite (an old
    survey's series a metre or two apart where they join): each joined to
    the nearest other piece within `within` metres, smallest first."""
    n = len(pos) // 3
    p = [pos[3 * i:3 * i + 3] for i in range(n)]
    while True:
        par = list(range(n))

        def find(x):
            while par[x] != x:
                par[x] = par[par[x]]
                x = par[x]
            return x
        for i, j in edges:
            par[find(i)] = find(j)
        parts = {}
        for i in range(n):
            parts.setdefault(find(i), []).append(i)
        if len(parts) < 2:
            return
        best = None
        for part in sorted(parts.values(), key=len):
            mine = set(part)
            for i in part:
                for j in range(n):
                    if j not in mine:
                        d = math.dist(p[i], p[j])
                        if d <= within and (best is None or d < best[0]):
                            best = (d, i, j)
            if best:
                break
        if not best:
            return
        edges.add((min(best[1], best[2]), max(best[1], best[2])))


def graph(legs, stations, name, rel, sumps=(), avoid=(), duplicates=True, join_within=JOIN):
    """The centreline as a graph for the page's routes. Stations at the same
    place are one node (the old .3d file has no equates, only shared
    positions). Each node has a station name and, where its survey has
    one, a passage name."""
    key = lambda p: (round(p[0] * 100), round(p[1] * 100), round(p[2] * 100))
    index, pos, edges = {}, [], set()

    def node(p):
        k = key(p)
        if k not in index:
            index[k] = len(index)
            pos.extend(rel(p))
        return index[k]
    for a, b, f in legs:
        if f & (5 if duplicates else 7):  # surface, splay (and duplicates, unless kept: in some surveys they join the parts)
            continue
        i, j = node(a), node(b)
        if i != j:
            edges.add((min(i, j), max(i, j)))
    if join_within:
        join(pos, edges, join_within)
    stn, passage, survey = [''] * len(index), [-1] * len(index), [-1] * len(index)
    plist = sorted({t for n, p, f in stations if n and (t := name(n))})
    slist = sorted({n.split('.')[0] for n, p, f in stations if '.' in n})
    pidx, sidx = {t: i for i, t in enumerate(plist)}, {t: i for i, t in enumerate(slist)}
    for n, p, f in sorted(stations, key=lambda s: len(s[0])):
        i = index.get(key(p))
        if i is None or not n:
            continue
        if not stn[i]:
            stn[i] = n
            survey[i] = sidx.get(n.split('.')[0], -1)
        t = name(n)
        if t and passage[i] < 0:
            passage[i] = pidx[t]
    wet = sorted(i for i, n in enumerate(stn) if n.split('.')[0] in sumps)
    shun = sorted({index[key(p)] for n, p, f in stations if n in avoid and key(p) in index})
    return {'pos': pos, 'edges': [v for e in sorted(edges) for v in e], 'stn': stn,
            'passage': passage, 'passages': plist, 'survey': survey, 'surveys': slist, 'wet': wet, 'avoid': shun}


def ways(g, nm, at):
    """The usual ways through the cave (names.json: each a chain of places
    or entrances), as the nodes along them, the shortest dry way from each
    place in a chain to the next. The routes keep to them where they can."""
    pos = [g['pos'][i:i + 3] for i in range(0, len(g['pos']), 3)]
    adj = [[] for _ in pos]
    wet, shun = set(g['wet']), set(g.get('avoid', ()))
    e = g['edges']
    for k in range(0, len(e), 2):
        a, b = e[k], e[k + 1]
        if not (a in wet and b in wet):
            d = math.dist(pos[a], pos[b]) * (AVOID if a in shun or b in shun else 1)
            adj[a].append((b, d)); adj[b].append((a, d))
    station = {**nm.get('places', {}), **{t: k for k, t in nm.get('entrances', {}).items()}}

    def node(t):
        if station.get(t) not in at:
            print(f'no place {t!r} for a way', file=sys.stderr)
            return None
        p = at[station[t]]
        return min(range(len(pos)), key=lambda i: math.dist(pos[i], p))

    def path(a, b):
        dist, prev, q = {a: 0}, {}, [(0, a)]
        while q:
            d, u = heapq.heappop(q)
            if u == b:
                break
            if d > dist[u]:
                continue
            for v, c in adj[u]:
                if d + c < dist.get(v, math.inf):
                    dist[v], prev[v] = d + c, u
                    heapq.heappush(q, (d + c, v))
        if b not in dist:
            return []
        out = [b]
        while out[-1] != a:
            out.append(prev[out[-1]])
        return out
    on = set()
    for chain in nm.get('ways', []):
        ns = [node(t) for t in chain]
        for a, b in zip(ns, ns[1:]):
            if a is not None and b is not None:
                on.update(path(a, b))
    return sorted(on)


MOVED = 3.0       # metres: walls whose middle is this far above or below their leg are put back on it
SLACK = 1.0       # metres: how far past its splays' reach a wall may go
FLOOR, CAP = 1.5, 8.0   # metres: the most a wall goes above or below a leg with no splays, at least and at most
GAP = 15.0        # metres: a wall triangle this wide, all of it this far from any leg in plan, bridges a gap


def fit_walls(walls, legs):
    """Walls built from plan drawings, put back on the survey. A plan has no
    heights, so Therion guesses them, and where a drawing covers passages at
    different levels some walls end up metres above or below their passage.
    Here each wall point keeps its place in plan but is hung from the leg it
    belongs to (the nearest in plan, or of those nearly as near, the one
    nearest Therion's guess of its height). Where a leg's walls sit more than
    MOVED metres above or below it, they're moved back round it, keeping their
    shape. And where the splays at a leg's stations reach higher or lower than
    its walls, the roof and floor are raised and lowered to meet them (never
    brought in). And no point goes further from its leg than the splays
    reach (SLACK past them), or, with no splays, than twice as far as most of
    the leg's walls go (FLOOR to CAP metres): Therion puts a few points of
    some drawings tens of metres off."""
    import numpy as np
    seg = [(a, b) for a, b, f in legs if not f & 5 and a != b]
    if not seg or not walls:
        return walls
    A, B = np.array([s[0] for s in seg], float), np.array([s[1] for s in seg], float)
    # how high and low the splays reach from each station
    reach, on = {}, {tuple(np.round(p, 2)) for s in seg for p in s}
    for a, b, f in legs:
        if f & 4 and not f & 1:
            if tuple(np.round(a, 2)) not in on:          # (a splay may run either way: from its station or to it)
                a, b = b, a
            k = tuple(np.round(a, 2))
            up, down = reach.get(k, (0.0, 0.0))
            reach[k] = (max(up, b[2] - a[2]), max(down, a[2] - b[2]))
    ends = [[reach.get(tuple(np.round(p, 2))) for p in (a, b)] for a, b in seg]
    pts = np.array([p for ps, ts in walls for p in ps], float)
    AB = B - A
    L2 = np.maximum((AB[:, :2] ** 2).sum(1), 1e-9)
    leg, at, zc = np.zeros(len(pts), int), np.zeros(len(pts)), np.zeros(len(pts))
    for i0 in range(0, len(pts), 2000):
        P = pts[i0:i0 + 2000]
        t = np.clip(((P[:, None, :2] - A[None, :, :2]) * AB[None, :, :2]).sum(2) / L2, 0, 1)
        C = A[None] + t[..., None] * AB[None]
        d = np.hypot(*(P[:, None, :2] - C[..., :2]).transpose(2, 0, 1))
        dz = np.abs(P[:, None, 2] - C[..., 2])
        near = d <= d.min(1, keepdims=True) + 1.5          # (passages at other levels, nearly as near in plan)
        j = np.where(near, dz, np.inf).argmin(1)
        r = np.arange(len(P))
        leg[i0:i0 + 2000], at[i0:i0 + 2000], zc[i0:i0 + 2000] = j, t[r, j], C[r, j, 2]
    off = pts[:, 2] - zc
    z = pts[:, 2].copy()
    for j in np.unique(leg):
        m = leg == j
        mid = np.median(off[m])
        if abs(mid) > MOVED:
            # this leg's walls are off at another level: back round the leg, the same shape
            z[m] -= mid
        e = [x for x in ends[j] if x]
        o = z[m] - zc[m]
        if e:
            # as high and low as the splays at its stations reach, where that's further
            up, down = max(x[0] for x in e), max(x[1] for x in e)
            o = np.where(o > 0, np.maximum(o, np.minimum(o * 4, up)), np.minimum(o, np.maximum(o * 4, -down)))
            top, bottom = up + SLACK, down + SLACK
        else:
            # no splays: no further than most of this leg's walls go, and never far
            above, below = o[o > 0], -o[o < 0]
            top = min(max(2 * np.percentile(above, 75) if above.size else 0, FLOOR), CAP)
            bottom = min(max(2 * np.percentile(below, 75) if below.size else 0, FLOOR), CAP)
        # and no point further: where a drawing covers passages at different levels,
        # Therion puts some of its points tens of metres up or down, out of the hill
        z[m] = zc[m] + np.clip(o, -bottom, top)
    out, k = [], 0
    for ps, ts in walls:
        out.append(([(p[0], p[1], float(z[k + i])) for i, p in enumerate(ps)], ts))
        k += len(ps)
    return out


def bridges(walls, legs):
    """Wall triangles that span a gap between passages rather than wall one:
    over GAP metres across, with their middle or the middle of their longest
    edge more than GAP from any leg in plan. Where a drawing's passages aren't
    surveyed between (an old drawing over a few long legs), Therion joins
    their walls across the gap with long fins."""
    import numpy as np
    seg = [(a, b) for a, b, f in legs if not f & 5 and a != b]
    if not seg:
        return set()
    A = np.array([s[0][:2] for s in seg], float)
    AB = np.array([s[1][:2] for s in seg], float) - A
    L2 = np.maximum((AB ** 2).sum(1), 1e-9)
    tris = [(m, k, np.array([pts[i][:2] for i in t], float)) for m, (pts, ts) in enumerate(walls) for k, t in enumerate(ts)]
    if not tris:
        return set()
    V = np.array([v for _, _, v in tris])
    pairs = ((0, 1), (1, 2), (0, 2))
    E = np.array([np.hypot(*(V[:, a] - V[:, b]).T) for a, b in pairs])
    wide = E.max(0) > GAP
    r, j = np.arange(len(V)), E.argmax(0)
    longest = (V[r, [pairs[k][0] for k in j]] + V[r, [pairs[k][1] for k in j]]) / 2
    far = np.zeros(len(V), bool)
    for q in (V.mean(1), longest):
        for i0 in range(0, len(q), 2000):
            x = q[i0:i0 + 2000, None]
            t = np.clip(((x - A) * AB).sum(2) / L2, 0, 1)
            d = np.hypot(*(x - (A + t[..., None] * AB)).transpose(2, 0, 1)).min(1)
            far[i0:i0 + 2000] |= d > GAP
    return {(m, k) for (m, k, _), w, f in zip(tris, wide, far) if w and f}


def steep(pts, tri, step):
    """A wall triangle that is a curtain rather than a wall: more than step
    metres tall and well over twice as tall as it is wide. Walls Therion
    builds from plan drawings get their heights from the stations near
    them, and where one drawing covers passages at different levels it
    joins them with these, straight down from one level to the other."""
    v = [pts[i] for i in tri]
    dz = max(p[2] for p in v) - min(p[2] for p in v)
    across = max(math.dist(a[:2], b[:2]) for a in v for b in v)
    return dz > step and dz > 2.5 * across


def kml_entrance(path):
    """(lat, lon) of the entrance in a Therion KML export (placed with OSTN15), or None."""
    if not path or not os.path.exists(path):
        return None
    t = open(path, encoding='utf-8').read()
    m = re.search(r'#ThEntranceIcon</styleUrl>.*?<coordinates>\s*([-\d.]+),([-\d.]+)', t, re.S)
    return (float(m.group(2)), float(m.group(1))) if m else None


# -- the scene ------------------------------------------------------------------------

def build(cfg, cave, out_dir, chromium=None):
    """The cave's 3D view in out_dir."""
    SO = tuple(cave['grid']['offset'])            # survey coordinates to the full grid
    crs = cave['grid']['crs']                     # which grid: the National Grid or Irish Transverse Mercator
    grid_to_ll = TO_LL[crs]
    T, R = cave['terrain'], cave['routing']
    legs, stations = cfg.read_centreline(cave)
    xs, ys, zs = zip(*[p for a, b, f in legs if not f & 1 for p in (a, b)])

    # the ground: the cave's extent plus a margin, on a grid of `align` metres
    # (so the model's cells line up with the 1 m LiDAR tiles)
    step, margin, al = T['step'], T['margin'], T['align']
    e0 = int(math.floor((min(xs) + SO[0] - margin) / al) * al)
    e1 = int(math.ceil((max(xs) + SO[0] + margin) / al) * al)
    n0 = int(math.floor((min(ys) + SO[1] - margin) / al) * al)
    n1 = int(math.ceil((max(ys) + SO[1] + margin) / al) * al)
    tw, th, heights, hbase = ground(T['type'], e0, n0, e1, n1, step, cfg.at(T['cache']) if T.get('cache') else None,
                                   level=T.get('level', max(zs) + 10), crs=crs)
    # the scene's origin: the middle of the ground, in survey coordinates
    ox, oy = (e0 + e1) / 2 - SO[0], (n0 + n1) / 2 - SO[1]

    # georeference for the imagery: survey x, y (from the origin) to Web
    # Mercator; with georef.kml, nudged so the entrance lands where Therion
    # (with OSTN15) puts it
    shift = (0.0, 0.0)
    ll, ent0 = kml_entrance(cfg.at(cave['georef'].get('kml'))), next(((n, p) for n, p, f in stations if f & 4), None)
    if ll and ent0:
        mine = grid_to_ll(ent0[1][0] + SO[0], ent0[1][1] + SO[1])
        shift = (ll[0] - mine[0], ll[1] - mine[1])
    pairs = []
    for i in range(5):
        for j in range(5):
            x, y = e0 + (e1 - e0) * i / 4, n0 + (n1 - n0) * j / 4
            lat, lon = grid_to_ll(x, y)
            pairs.append(((x - SO[0] - ox, y - SO[1] - oy), mercator(lat + shift[0], lon + shift[1])))
    merc = fit_affine(pairs)

    def r(v):
        return round(v, 2)

    def rel(p):
        return [r(p[0] - ox), r(p[1] - oy), r(p[2])]

    kinds = {'legs': [], 'duplicates': [], 'splays': [], 'surface': []}
    for a, b, f in legs:
        k = 'surface' if f & 1 else 'splays' if f & 4 else 'duplicates' if f & 2 else 'legs'
        kinds[k] += rel(a) + rel(b)

    # the passage walls, where there are any (a Therion .lox: one in the repo,
    # or the one the survey step built from the drawings)
    wall_pos, wall_idx, lox = [], [], cave['walls'] and cfg.at(cave['walls'].get('lox'))
    if cave['walls'] and cave['walls'].get('type') == 'therion':
        lox = os.path.join(cfg.work_dir(cave), 'walls.lox')
    if lox and cave['features']['walls']:
        if os.path.exists(lox):
            max_step = cave['walls'].get('max_step')     # (off unless asked for: it leaves holes where a passage really does step down)
            cut = 0
            meshes = read_lox_walls(lox)
            leave = [x.lower() for x in cave['walls'].get('leave_out', [])]
            if leave:
                # (walls.leave_out: surveys whose drawings make poor walls, left out)
                from caveviewer.formats import lox_wall_surveys
                inside = lambda sv: any(f'.{x}.' in f'.{sv.lower()}.' for x in leave)
                keep = [not inside(sv) for sv in lox_wall_surveys(lox)]
                meshes = [m for m, k in zip(meshes, keep) if k]
            if cave['walls'].get('heights', 'survey' if cave['walls'].get('type') == 'therion' else 'lox') == 'survey':
                meshes = fit_walls(meshes, legs)
            gaps = bridges(meshes, legs)
            for m, (pts, tris) in enumerate(meshes):
                base = len(wall_pos) // 3
                for p in pts:
                    wall_pos += rel(p)
                for k, t in enumerate(tris):
                    if (m, k) in gaps:
                        continue
                    if max_step and steep(pts, t, max_step):
                        cut += 1
                        continue
                    wall_idx += [base + i for i in t]
            if cut:
                print(f'walls: left out {cut} steep triangles (curtains between levels)', file=sys.stderr)
            if gaps:
                print(f'walls: left out {len(gaps)} triangles bridging gaps between passages', file=sys.stderr)
        else:
            print(f'no walls: {lox} is missing', file=sys.stderr)

    nm = json.load(open(os.path.join(cfg.work_dir(cave), 'names.json'), encoding='utf-8'))
    name = namer(nm, stations, R['codes_first'])
    g = graph(legs, stations, name, rel, set(nm.get('sumps', ())), {k for k in nm.get('avoid', {}) if not k.startswith('_')},
              duplicates=R['duplicates'], join_within=R['join'])
    g['way'] = ways(g, nm, {n: rel(p) for n, p, f in stations if n})
    g['offway'] = nm.get('offway', 1.6)
    names = [{'t': t, 'p': rel((x, y, z))} for t, x, y, z in place_names(stations, name, nm.get('places'))]
    # the sumps: each is a place at its dry end (where it meets the dry cave
    # nearest its middle), and places only beyond a sump aren't places to go
    gpos = lambda i: g['pos'][3 * i:3 * i + 3]
    # the cave's systems: its connected parts (a whole area's data has many, joined only by
    # surface surveys). Each entrance belongs to the one it's nearest, and routes go within it.
    where = {n: p for n, p, f in stations}
    part_of = {}
    for k, part in enumerate(parts(g)):
        for i in part:
            part_of[i] = k
    snapped = {}                    # entrance station -> its nearest node
    for k in nm.get('entrances', {}):
        if k in where:
            p = rel(where[k])
            snapped[k] = min(range(len(g['stn'])), key=lambda i: math.dist(gpos(i), p))
    # places to go: the dry parts an entrance joins (a part beyond a sump isn't one)
    doors = {i for k, i in snapped.items() if math.dist(gpos(i), rel(where[k])) <= R['snap']}
    dry = {i for part in parts(g, dry=True) if doors.intersection(part) for i in part}
    wet = set(g['wet'])
    edges = g['edges']
    ends = {i for k in range(0, len(edges), 2) for i, j in ((edges[k], edges[k + 1]), (edges[k + 1], edges[k]))
            if i in wet and j in dry and j not in wet}
    for n in names:
        i = min(range(len(g['stn'])), key=lambda i: math.dist(gpos(i), n['p']))
        if i in wet and ends:
            sv = g['stn'][i].split('.')[0]
            near = [j for j in ends if g['stn'][j].split('.')[0] == sv] or list(ends)
            n['p'] = gpos(min(near, key=lambda j: math.dist(gpos(j), n['p'])))
        elif i not in dry:
            n['apart'] = True
        if not n.get('apart'):
            n['sys'] = part_of[i]
    # the entrances, in the order in names.json; those that join the
    # surveyed cave (any of its systems) can be routed to, within their system
    ents = []
    for k, t in nm.get('entrances', {}).items():
        if k not in where:
            print(f'no station {k!r} for the entrance {t!r}', file=sys.stderr)
            continue
        p = rel(where[k])
        i = snapped[k]
        e = {'t': t, 'p': p, 'entrance': True}
        if math.dist(gpos(i), p) > R['snap'] or t in nm.get('apart', ()):     # (too far from the cave, or kept out of the routes by name)
            e['apart'] = True
        else:
            e['sys'] = part_of[i]
        ents.append(e)
    names = ents + names
    if not nm.get('entrances'):
        raise ValueError(f'{cave["name"]}: no entrance (flag one in the survey, or give "entrances" in the config)')
    ent = where[next(iter(nm['entrances']))]

    length = sum(math.dist(a, b) for a, b, f in legs if not f & 7)
    hs = [hbase + v / 100 for v in heights if v]
    off = [k for k, v in cave['features'].items() if not v or k == 'drawn' and cave['drawn']['type'] == 'none']
    scene = {
        'title': cave['name'],
        'subtitle': cave['area'],
        'id': cave['id'],
        'built': datetime.date.today().isoformat(),
        'origin': [ox + SO[0], oy + SO[1]],
        'grid_ref': grid_ref(ent[0] + SO[0], ent[1] + SO[1], crs),
        'stats': {'length': round(length), 'depth': round(max(zs) - min(zs)),
                  'top': r(max(zs)), 'bottom': r(min(zs))},
        'terrain': {'file': 'terrain.bin', 'w': tw, 'h': th, 'step': step,
                    'x0': e0 - SO[0] - ox, 'y0': n1 - SO[1] - oy, 'min': min(hs), 'max': max(hs),
                    'base': hbase},
        'merc': merc,
        'walls': {'pos': wall_pos, 'idx': wall_idx},
        'names': names,
        'trips': nm.get('trips', []),
        'graph': g,
        **kinds,
        # (only what's turned off: the page has everything on where it doesn't say)
        **({'features': {k: False for k in off}} if off else {}),
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'scene.json'), 'w') as f:
        json.dump(scene, f, separators=(',', ':'))
    with open(os.path.join(out_dir, 'terrain.bin'), 'wb') as f:
        f.write(heights.tobytes())
    page(cfg, cave, out_dir)
    offline(out_dir, VIEWER, worker=cave['features']['offline'], name=os.path.normpath(cave['path']).replace(os.sep, '-'))
    print(f'3D view written to {out_dir}: {len(legs)} legs, {len(names)} names, '
          f'{length / 1000:.1f} km, ground {tw}x{th} at {step} m', file=sys.stderr)
    if chromium:
        preview(chromium, out_dir)
    return scene


def page(cfg, cave, out_dir):
    """index.html and manifest.webmanifest: the viewer, with the cave's own words in it."""
    sv, data, dr = cave['survey'], cave.get('data', {}), cave['drawn']
    url = data.get('url') or (f"{sv['svn']}/{sv['dir']}/" if sv.get('svn') else '')
    data_html = data.get('html') or (f'Data: <a href="{url}">{data.get("label", "the survey data")}</a>' if url else '')
    ground_credit = cave['terrain'].get('credit', CREDITS[cave['terrain']['type']])
    words = {'NAME': html.escape(cave['name']), 'AREA': html.escape(cave['area']), 'ID': cave['id'],
             'CREDIT': cave['credit'], 'DATA': url, 'DATA_HTML': data_html, 'GROUND_CREDIT': ground_credit,
             'DRAWN_CREDIT': dr.get('page_credit', DRAWN_CREDITS[dr['type']])}
    text = open(os.path.join(VIEWER, 'viewer.html'), encoding='utf-8').read()
    for k, v in words.items():
        text = text.replace('{{' + k + '}}', v)
    with open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(text)
    man = json.load(open(os.path.join(VIEWER, 'static', 'manifest.webmanifest')))
    man.update(name=f"{cave['name']} in 3D",
               short_name=cave.get('short_name') or cave['name'].replace(' Cave', '').replace(' Swallet', ''),
               description=f"{cave['name']} in 3D beneath the ground, with routes through the cave. Works offline.")
    with open(os.path.join(out_dir, 'manifest.webmanifest'), 'w') as f:
        json.dump(man, f, indent=2)
