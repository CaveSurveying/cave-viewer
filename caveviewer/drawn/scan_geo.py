"""Where a point on the National Grid is on the drawn survey, and back.

The fit (drawn.fit in the config, made by `python -m caveviewer fit`) is a scaled,
turned and shifted copy of the grid for the whole cave, and one for each
square of CELL metres where the drawing's passages pull it a little off:
a hand-drawn survey isn't quite a perfect copy of the data. Between the
squares' middles the fits are blended, so nothing jumps at their edges.

A fit is two complex numbers (A, B): pixel x - i*y = A * (E + i*N) + B.
"""
import json
import math

import numpy as np


class Geo:
    def __init__(self, path):
        t = json.load(open(path))
        self.cell = t['cell']
        mk = lambda q: (complex(q[0], q[1]), complex(q[2], q[3]))
        self.g = mk(t['global'])
        self.local = {tuple(map(int, k.split(','))): mk(v) for k, v in t['local'].items()}

    def _fit(self, i, j):
        return self.local.get((i, j), self.g)

    def params(self, e, n):
        """The blended fit (A, B) at points (arrays of E and N)."""
        e, n = np.asarray(e, float), np.asarray(n, float)
        fx, fy = e / self.cell - 0.5, n / self.cell - 0.5
        i0, j0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
        tx, ty = fx - i0, fy - j0
        A = np.zeros(e.shape, complex); B = np.zeros(e.shape, complex)
        for di, dj, w in ((0, 0, (1 - tx) * (1 - ty)), (1, 0, tx * (1 - ty)), (0, 1, (1 - tx) * ty), (1, 1, tx * ty)):
            ii, jj = i0 + di, j0 + dj
            keys = np.unique(np.stack([ii.ravel(), jj.ravel()], 1), axis=0)
            a = np.zeros(e.shape, complex); b = np.zeros(e.shape, complex)
            for ki, kj in keys:
                m = (ii == ki) & (jj == kj)
                fa, fb = self._fit(ki, kj)
                a[m] = fa; b[m] = fb
            A += w * a; B += w * b
        return A, B

    def to_px(self, e, n):
        """Grid E, N (arrays) -> drawing pixels x, y."""
        A, B = self.params(e, n)
        u = A * (np.asarray(e, float) + 1j * np.asarray(n, float)) + B
        return u.real, -u.imag

    def to_grid(self, x, y):
        """Drawing pixels -> grid E, N (by the whole fit, then refined by the blended)."""
        u = complex(x, -y)
        A, B = self.g
        w = (u - B) / A
        for _ in range(3):
            A, B = self.params(np.array([w.real]), np.array([w.imag]))
            w = (u - B[0]) / A[0]
        return w.real, w.imag
