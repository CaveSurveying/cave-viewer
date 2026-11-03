"""A Therion drawing as the drawn survey (drawn.type "therion-svg"): the
plan the survey step exported (<work>/<cave>/plan.svg, at 1:500, the
National Grid's coordinates written on its grid), which headless Chrome
(CHROMIUM, or the usual place on a Mac) turns into pixels, a piece at a
time; the grid's labels place it. A title block goes under it: the cave,
its length and depth, who surveyed it (credits.json), the cave's note and
licence. Then it's cut into tiles on the scene's own grid.
"""
import math
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import json
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image

from caveviewer.drawn import LEVEL0, LEVEL1, TILE, blank

CHROME = os.environ.get('CHROMIUM') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
CHUNK = 4096                    # pixels: Chrome draws the plan this much at a time
SCALE = 72 / 0.0254             # points a metre on paper
MARGIN = 6                      # metres of paper added round Therion's frame
LABEL = (2.0, 2.0)              # where Therion writes a grid label, from its grid point (points, up and to the right)


def matrix(t):
    """An SVG transform attribute as (a, b, c, d, e, f)."""
    m = (1, 0, 0, 1, 0, 0)
    for kind, args in re.findall(r'(\w+)\s*\(([^)]*)\)', t or ''):
        v = [float(x) for x in re.split(r'[\s,]+', args.strip()) if x]
        n = {'matrix': tuple(v), 'translate': (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0),
             'scale': (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)}.get(kind)
        if n:
            m = mul(m, n)
    return m


def mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D, a * E + c * F + e, b * E + d * F + f)


def georef(path):
    """The plan's viewBox, and where the grid is on it: (k, a, b) with
    x = a + k * E and y = b - k * N (SVG units, survey coordinates)."""
    root = ET.parse(path).getroot()
    vb = [float(v) for v in root.get('viewBox').split()]
    marks = []

    def walk(el, m):
        m = mul(m, matrix(el.get('transform')))
        tag = el.tag.split('}')[-1]
        txt = ''.join(el.itertext()).strip()
        g = re.fullmatch(r'\((-?[\d.]+),\s*(-?[\d.]+)\)', txt) if tag == 'text' else None
        if g and el.get('text-anchor') in (None, 'start'):
            # the label's own origin is the grid point plus LABEL, in the drawing's up-is-up units
            x, y = m[4] - m[0] * LABEL[0] - m[2] * LABEL[1], m[5] - m[1] * LABEL[0] - m[3] * LABEL[1]
            marks.append((float(g[1]), float(g[2]), x, y))
            return
        for c in el:
            walk(c, m)
    walk(root, (1, 0, 0, 1, 0, 0))
    if len(marks) < 3:
        raise ValueError(f'{path}: too few grid labels ({len(marks)}) to place the drawing')
    E, N, X, Y = (np.array(v) for v in zip(*marks))
    k = SCALE / 500                         # (the layout's 1:500)
    a, b = np.median(X - k * E), np.median(Y + k * N)
    # (the labels along the top sit below their points, inside the frame: the median leaves them out)
    agree = int(((np.abs(X - k * E - a) < 0.05 * k) & (np.abs(Y + k * N - b) < 0.05 * k)).sum())
    return vb, (k, a, b), len(marks), agree


def title_block(cave, scene, credits, x, y, width):
    """The sheet's title block (Therion draws one only in its PDFs): the
    cave, its length and depth, who surveyed it, its copyright and licence,
    and where the data is from, as SVG text from (x, y) down, wrapped to
    width. Returns (svg, height), in the plan's units (points)."""
    st = scene['stats']
    team = credits.get('surveyed', [])
    who = ', '.join(team[:18]) + (' and others' if len(team) > 18 else '')
    rights = ', '.join(credits.get('copyright', []))
    lines = [(22, 700, cave['name']),
             (10, 400, f"{st['length'] / 1000:.1f} km surveyed \u00b7 {st['depth']} m deep \u00b7 entrance {scene['grid_ref']} \u00b7 plan at 1:500, coloured by altitude")]
    text = [f'Surveyed by {who}.' if who else '', cave.get('note', ''),
            f'Copyright {rights}.' if rights else '', cave.get('licence', ''),
            f"Drawn by Therion from the {cave['survey'].get('from', 'survey data')}/{cave['survey']['dir']}. Grid: the National Grid, 100 m squares."]
    wrap = max(40, int(width / (9 * 0.52)))
    for t in text:
        lines += [(9, 400, w) for w in textwrap.wrap(t, wrap)]
    out, h = [], 0
    for size, weight, t in lines:
        h += size * 1.45
        out.append(f'<text x="{x:.1f}" y="{y + h:.1f}" font-family="Helvetica, Arial, sans-serif" font-size="{size}" '
                   f'font-weight="{weight}" fill="#222">{escape(t)}</text>')
    return '\n'.join(out), h + 6


def render(path, vb, R, extra='', chrome=None):
    """The whole plan as an image, R pixels a unit, on white paper, over
    the given viewBox (which may be bigger than the plan's own)."""
    W, H = math.ceil(vb[2] * R), math.ceil(vb[3] * R)
    out = Image.new('RGB', (W, H), 'white')
    with tempfile.TemporaryDirectory() as tmp:
        svg = open(path, encoding='utf-8').read()
        head = re.search(r'<svg [^>]*>', svg).group(0)
        new = re.sub(r'viewBox="[^"]*"', 'viewBox="{} {} {} {}"'.format(*vb), head)
        new = re.sub(r'width="[^"]*"', f'width="{W}px"', new, count=1)
        new = re.sub(r'height="[^"]*"', f'height="{H}px"', new, count=1)
        path = os.path.join(tmp, 'plan.svg')
        svg = svg.replace(head, new, 1).replace(' clip-path="url(#clip_viewBox)"', '')     # (and Therion's clip to its own frame, off)
        svg = svg[:svg.rindex('</svg>')] + extra + '</svg>'
        open(path, 'w', encoding='utf-8').write(svg)
        for y in range(0, H, CHUNK):
            for x in range(0, W, CHUNK):
                w, h = min(CHUNK, W - x), min(CHUNK, H - y)
                page = os.path.join(tmp, 'p.html')
                open(page, 'w').write(
                    f'<html><body style="margin:0;background:#fff;overflow:hidden">'
                    f'<img src="file://{os.path.abspath(path)}" style="position:absolute;left:{-x}px;top:{-y}px;width:{W}px;height:{H}px"></body></html>')
                shot = os.path.join(tmp, 's.png')
                subprocess.run([chrome or CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--allow-file-access-from-files',
                                f'--window-size={w},{h}', f'--screenshot={shot}', 'file://' + page],
                               check=True, capture_output=True, timeout=300)
                out.paste(Image.open(shot).convert('RGB').crop((0, 0, w, h)), (x, y))
    return out


def build(cfg, cave, site_dir, chromium=None):
    SO = cave['grid']['offset']
    src = os.path.join(cfg.work_dir(cave), 'plan.svg')
    out = os.path.join(site_dir, 'drawn')
    scene = json.load(open(os.path.join(site_dir, 'scene.json')))
    ox, oy = scene['origin'][0] - SO[0], scene['origin'][1] - SO[1]       # the scene's origin, in survey coordinates
    vb, (k, a, b), n, agree = georef(src)
    # Therion's frame is a little tight (the grid's labels at the edge are
    # cut): a margin all round
    m = MARGIN * k
    credits = json.load(open(os.path.join(cfg.work_dir(cave), 'credits.json')))
    block, bh = title_block(cave, scene, credits, vb[0], vb[1] + vb[3] + m, vb[2])
    vb = [vb[0] - m, vb[1] - m, vb[2] + 2 * m, vb[3] + 2 * m + bh]
    R = 1 / (LEVEL1 * k)                                                   # pixels a unit at LEVEL1
    print(f'{cave["name"]}: placed by its grid labels ({agree} of {n} agree to 5 cm); drawing it', file=sys.stderr)
    im = render(src, vb, R, block, chromium)
    # scene metres <-> pixels of im: E = sx + ox; x = a + k E; px = (x - vb[0]) R
    px = lambda sx: (a + k * (sx + ox) - vb[0]) * R
    py = lambda sy: (b - k * (sy + oy) - vb[1]) * R
    sx = lambda X: (X / R + vb[0] - a) / k - ox
    sy = lambda Y: (b - (Y / R + vb[1])) / k - oy
    W, H = im.size
    paper = [[round(sx(X), 2), round(sy(Y), 2)] for X, Y in ((0, 0), (W, 0), (W, H), (0, H))]
    span0, span1 = TILE * LEVEL0, TILE * LEVEL1
    xs, ys = [p[0] for p in paper], [p[1] for p in paper]
    x0, y0 = math.floor(min(xs) / span0) * span0, math.ceil(max(ys) / span0) * span0
    nx0, ny0 = math.ceil((max(xs) - x0) / span0), math.ceil((y0 - min(ys)) / span0)
    per = round(LEVEL0 / LEVEL1)
    for d in ('0', '1'):
        os.makedirs(os.path.join(out, d), exist_ok=True)
        for f in os.listdir(os.path.join(out, d)):
            os.remove(os.path.join(out, d, f))
    tiles0, tiles1 = [], []
    for j in range(ny0):
        for i in range(nx0):
            # the big tile at full detail, then its parts and itself made smaller
            L, T = px(x0 + i * span0), py(y0 - j * span0)
            big = im.crop((round(L), round(T), round(L) + TILE * per, round(T) + TILE * per))   # (white beyond the drawing)
            if blank(big):
                continue
            big.resize((TILE, TILE), Image.BOX).save(os.path.join(out, '0', f'{i}_{j}.webp'), quality=82)
            tiles0.append([i, j])
            for jj in range(per):
                for ii in range(per):
                    t = big.crop((ii * TILE, jj * TILE, (ii + 1) * TILE, (jj + 1) * TILE))
                    if not blank(t):
                        I, J = i * per + ii, j * per + jj
                        t.save(os.path.join(out, '1', f'{I}_{J}.webp'), quality=80)
                        tiles1.append([I, J])
    json.dump({'x0': x0, 'y0': y0, 'tile': TILE, 'level0': LEVEL0, 'level1': LEVEL1, 'tiles0': tiles0, 'tiles1': tiles1,
               'paper': paper, 'credit': cave['drawn'].get('credit', cave['credit'])}, open(os.path.join(out, 'meta.json'), 'w'))
    print(f'  {out}: {len(tiles0)} tiles, {len(tiles1)} close up', file=sys.stderr)
