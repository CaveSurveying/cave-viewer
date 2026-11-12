"""A scanned drawing as the drawn survey (drawn.type "scan"): an image
of the drawn survey, fitted to the survey by `python -m caveviewer fit`
(caveviewer.drawn.scan_fit), turned north-up onto the grid and cut into
tiles.

drawn: {"type": "scan", "image": the drawing (PNG or JPEG), "fit": the fit
(JSON), "credit": its credit, in the tiles' meta.json}

A drawing that mustn't be published stays out of git (local/, say): without
the image or its fit this does nothing, so only a build that has them
makes the drawn survey.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

from caveviewer.drawn import LEVEL0, LEVEL1, TILE
from caveviewer.drawn.scan_geo import Geo


def sample(arr, x, y):
    """Bilinear samples of an image array at pixels x, y (white off the edge)."""
    h, w = arr.shape[:2]
    out = np.full(x.shape + (3,), 255, np.float32)
    ok = (x >= 0) & (y >= 0) & (x < w - 1) & (y < h - 1)
    xs, ys = x[ok], y[ok]
    x0, y0 = xs.astype(int), ys.astype(int)
    fx, fy = (xs - x0)[:, None], (ys - y0)[:, None]
    a, b, c, d = arr[y0, x0], arr[y0, x0 + 1], arr[y0 + 1, x0], arr[y0 + 1, x0 + 1]
    out[ok] = (a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy)
    return out


def tile(geo, arr, k, origin, x0, y0, res):
    """One tile: TILE x TILE pixels from the scene's (x0, y0) (its north-west
    corner) at res metres a pixel; None if it's blank paper."""
    i = (np.arange(TILE) + 0.5) * res
    X, Y = np.meshgrid(x0 + i, y0 - i)
    px, py = geo.to_px(X + origin[0], Y + origin[1])
    rgb = sample(arr, px / k, py / k)
    # the ink on the paper in it, not over the whole tile: a small cave's
    # drawing (a sheet of a few tens of metres) is a speck in a 512 m tile
    h, w = arr.shape[:2]
    paper = (px / k >= 0) & (py / k >= 0) & (px / k < w - 1) & (py / k < h - 1)
    if not paper.any():
        return None
    ink = (rgb[paper].min(axis=1) < 225).mean()
    return None if ink < 0.002 else Image.fromarray(rgb.clip(0, 255).astype(np.uint8))


def build(cfg, cave, site_dir):
    DRAWING, FIT = cfg.at(cave['drawn']['image']), cfg.at(cave['drawn']['fit'])
    OUT = os.path.join(site_dir, 'drawn')
    if not (os.path.exists(DRAWING) and os.path.exists(FIT)):
        print(f'{cave["name"]}: no drawn survey ({cave["drawn"]["image"]} and {cave["drawn"]["fit"]}): skipped', file=sys.stderr)
        return
    scene = json.load(open(os.path.join(site_dir, 'scene.json')))
    origin = scene['origin']
    geo = Geo(FIT)
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(DRAWING).convert('RGB')
    W, H = im.size
    full = np.asarray(im)
    quarter = np.asarray(im.resize((W // 4, H // 4), Image.BOX))
    # the drawing's corners on the grid, to the scene's metres, out to whole coarse tiles
    corners = [geo.to_grid(x, y) for x, y in ((0, 0), (W, 0), (W, H), (0, H))]
    xs = [e - origin[0] for e, n in corners]; ys = [n - origin[1] for e, n in corners]
    span0 = TILE * LEVEL0
    x0 = math.floor(min(xs) / span0) * span0; y0 = math.ceil(max(ys) / span0) * span0
    nx0 = math.ceil((max(xs) - x0) / span0); ny0 = math.ceil((y0 - min(ys)) / span0)
    os.makedirs(f'{OUT}/0', exist_ok=True); os.makedirs(f'{OUT}/1', exist_ok=True)
    tiles0, tiles1 = [], []
    per = int(round(LEVEL0 / LEVEL1))            # level 1 tiles across a level 0 tile
    for j in range(ny0):
        for i in range(nx0):
            t = tile(geo, quarter, 4, origin, x0 + i * span0, y0 - j * span0, LEVEL0)
            if t is None:
                continue
            t.save(f'{OUT}/0/{i}_{j}.webp', quality=82); tiles0.append([i, j])
            for jj in range(per):
                for ii in range(per):
                    span1 = TILE * LEVEL1
                    t1 = tile(geo, full, 1, origin, x0 + i * span0 + ii * span1, y0 - j * span0 - jj * span1, LEVEL1)
                    if t1 is not None:
                        t1.save(f'{OUT}/1/{i * per + ii}_{j * per + jj}.webp', quality=80); tiles1.append([i * per + ii, j * per + jj])
        print(f'row {j + 1} of {ny0}: {len(tiles0)} tiles, {len(tiles1)} close up', file=sys.stderr)
    meta = {'x0': x0, 'y0': y0, 'tile': TILE, 'level0': LEVEL0, 'level1': LEVEL1, 'tiles0': tiles0, 'tiles1': tiles1,
            'paper': [[round(float(x), 2), round(float(y), 2)] for x, y in zip(xs, ys)],
            'credit': cave['drawn'].get('credit', '')}
    json.dump(meta, open(f'{OUT}/meta.json', 'w'))
    print(f'{OUT}: {len(tiles0)} tiles, {len(tiles1)} close up', file=sys.stderr)

