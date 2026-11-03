"""Line a scanned drawn survey up with the survey data.

    python -m caveviewer fit <config> [cave]     # writes the cave's drawn.fit

The drawing (drawn.image) and its fit (drawn.fit) are the cave repo's own:
a private drawing and all made from it stay out of git, as the repo says.

1. The entrances: the red triangles on the drawing, matched to the
   survey's entrance stations (a pair at a time, keeping the fit most
   entrances agree with, then least squares over those).
2. The whole cave: moved, turned and scaled so the most survey stations
   sit on the drawn passages (their colours, blurred, so they pull from
   a distance).
3. Each square of CELL metres the same way, with its neighbours'
   stations, for where the drawing is a little off.
"""
import itertools
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

from caveviewer.formats import read_3d

K = 4            # the drawing is fitted at a quarter of its size
CELL = 250.0     # metres: the squares fitted on their own


def blobs(mask, least=30):
    """Connected patches of a mask: (size, width, height, x, y) each."""
    seen = np.zeros_like(mask)
    out = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        stack, pts = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop(); pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < mask.shape[0] and 0 <= xx < mask.shape[1] and mask[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True; stack.append((yy, xx))
        if len(pts) >= least:
            a = np.array(pts)
            out.append((len(pts), np.ptp(a[:, 1]) + 1, np.ptp(a[:, 0]) + 1, a[:, 1].mean(), a[:, 0].mean()))
    return out


def nelder_mead(f, x0, steps, it=300):
    n = len(x0)
    pts = [np.array(x0, float)] + [np.array(x0, float) + np.eye(n)[i] * steps[i] for i in range(n)]
    vals = [f(p) for p in pts]
    for _ in range(it):
        o = np.argsort(vals); pts = [pts[i] for i in o]; vals = [vals[i] for i in o]
        c = np.mean(pts[:-1], axis=0); xr = c + (c - pts[-1]); fr = f(xr)
        if fr < vals[0]:
            xe = c + 2 * (c - pts[-1]); fe = f(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            xc = c + 0.5 * (pts[-1] - c); fc = f(xc)
            if fc < vals[-1]:
                pts[-1], vals[-1] = xc, fc
            else:
                pts = [pts[0]] + [pts[0] + 0.5 * (p - pts[0]) for p in pts[1:]]
                vals = [vals[0]] + [f(p) for p in pts[1:]]
    return pts[int(np.argmin(vals))]


def fit(cfg, cave):
    path, OUT = cfg.at(cave['drawn']['image']), cfg.at(cave['drawn']['fit'])
    SO = cave['grid']['offset']             # (the fit is on the full National Grid)
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(path).convert('RGB')
    W, H = im.size
    sm = np.asarray(im.resize((W // K, H // K), Image.BOX)).astype(int)
    print(f'drawing {W}x{H}', file=sys.stderr)
    legs, stations = read_3d(cfg.centreline(cave))
    stations = [(n, (p[0] + SO[0], p[1] + SO[1], p[2]), f) for n, p, f in stations]

    # 1. the entrances
    r, g, b = sm[..., 0], sm[..., 1], sm[..., 2]
    tri = [(x * K, y * K) for n, w, h, x, y in blobs((r > 225) & (g > 60) & (g < 115) & (b < 100))
           if 4 <= w <= 30 and 4 <= h <= 30 and n / (w * h) > 0.3]
    ents = [p[:2] for n, p, f in stations if f & 4]
    ap = lambda A, B, p: (lambda u: (u.real, -u.imag))(A * complex(p[0], p[1]) + B)
    best = None
    for i, j in itertools.permutations(range(len(tri)), 2):
        for a, c in itertools.combinations(range(len(ents)), 2):
            w1, w2 = complex(*ents[a]), complex(*ents[c])
            if w1 == w2:
                continue
            u1, u2 = complex(tri[i][0], -tri[i][1]), complex(tri[j][0], -tri[j][1])
            A = (u1 - u2) / (w1 - w2)
            if not 3 < abs(A) < 30:
                continue
            B = u1 - A * w1
            inl = sum(1 for e in ents if min(math.dist(ap(A, B, e), t) for t in tri) < 25)
            if best is None or inl > best[0]:
                best = (inl, A, B)
    _, A, B = best
    pairs = [(e, min(tri, key=lambda t: math.dist(ap(A, B, e), t))) for e in ents]
    pairs = [(e, t) for e, t in pairs if math.dist(ap(A, B, e), t) < 25]
    M = np.array([[complex(*e), 1] for e, t in pairs]); u = np.array([complex(t[0], -t[1]) for e, t in pairs])
    (A, B), *_ = np.linalg.lstsq(M, u, rcond=None)
    print(f'{len(tri)} entrance triangles, {len(pairs)} matched; {abs(A):.3f} px/m, turned {math.degrees(math.atan2(A.imag, A.real)):.2f} degrees',
          file=sys.stderr)

    # 2 and 3: the passages (the drawing's colours, not its grey text and lines)
    luma = 0.3 * r + 0.59 * g + 0.11 * b
    mask = (((sm.max(axis=2) - sm.min(axis=2)) > 12) & (luma < 250)).astype(np.uint8) * 255
    fields = {rad: np.asarray(Image.fromarray(mask).filter(ImageFilter.GaussianBlur(rad))).astype(float) / 255
              for rad in (24, 8, 3)}
    pts = np.array([p[:2] for n, p, f in stations if not f & 1])
    Wc = pts[:, 0] + 1j * pts[:, 1]

    def score(q, F, sel=None):
        u = complex(q[0], q[1]) * (Wc if sel is None else Wc[sel]) + complex(q[2], q[3])
        x, y = u.real / K, -u.imag / K
        ok = (x >= 0) & (y >= 0) & (x < F.shape[1] - 1) & (y < F.shape[0] - 1)
        return F[y[ok].astype(int), x[ok].astype(int)].sum() / max(1, len(x))
    q = [A.real, A.imag, B.real, B.imag]
    for rad in (24, 8, 3):
        q = nelder_mead(lambda v: -score(v, fields[rad]), q, [abs(A) * 0.004, abs(A) * 0.004, 60, 60])
    print(f'whole cave: {score(q, fields[3]):.0%} of the stations on the drawn passages', file=sys.stderr)
    cx, cy = np.floor(pts[:, 0] / CELL).astype(int), np.floor(pts[:, 1] / CELL).astype(int)
    local = {}
    for key in sorted(set(zip(cx.tolist(), cy.tolist()))):
        sel = (abs(cx - key[0]) <= 1) & (abs(cy - key[1]) <= 1)
        if sel.sum() < 40:
            continue
        v = nelder_mead(lambda w: -score(w, fields[3], sel), q, [abs(A) * 0.003, abs(A) * 0.003, 25, 25], 200)
        local[f'{key[0]},{key[1]}'] = [float(x) for x in v]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({'drawing': [W, H], 'cell': CELL, 'global': [float(x) for x in q], 'local': local}, open(OUT, 'w'))
    print(f'{OUT}: the whole cave and {len(local)} squares', file=sys.stderr)

