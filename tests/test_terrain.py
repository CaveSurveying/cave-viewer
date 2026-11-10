"""The ground's heights: centimetres above a base, in 16 bits, and the cache.

    python -m unittest discover -s tests
"""
import array
import gzip
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

from caveviewer.terrain import cached, encode, ground

NAN = math.nan
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixture', 'data')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def decode(heights, base):
    return [base + v / 100 if v else None for v in heights]


class Encode(unittest.TestCase):
    def test_low_ground_as_before(self):
        # ground that fits in 16 bits keeps base 0: the same terrain.bin and cache as before bases
        heights, base = encode([238.0, 251.37, NAN, 655.33])
        self.assertEqual(base, 0)
        self.assertEqual(list(heights), [23800, 25137, 0, 65533])

    def test_high_ground(self):
        # the Pennines: Crag Hill (682 m) over Easegill, which overflowed before
        heights, base = encode([240.5, 682.25, NAN, 736.0])
        self.assertEqual(base, 239)
        self.assertEqual(decode(heights, base), [240.5, 682.25, None, 736.0])

    def test_below_sea_level(self):
        heights, base = encode([-2.5, 0.0, 12.0])
        self.assertEqual(base, -4)
        self.assertEqual(decode(heights, base), [-2.5, 0.0, 12.0])

    def test_no_ground_is_never_zero(self):
        # 0 means no ground, so a real height at the base itself is kept just above it
        heights, base = encode([0.001, 5.0])
        self.assertEqual(heights[0], 1)

    def test_too_much_relief(self):
        with self.assertRaises(ValueError):
            encode([10.0, 700.0])

    def test_flat_ground_high_up(self):
        w, h, heights, base = ground('flat', 0, 0, 20, 10, 2, None, level=720.0)
        self.assertEqual((w, h), (10, 5))
        self.assertEqual(set(decode(heights, base)), {720.0})


class Cache(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_high_ground_kept_with_its_base(self):
        made = []
        make = lambda: made.append(1) or array.array('d', [700.0, 710.5, NAN])
        first = cached(self.dir, 0, 0, 6, 2, 2, make)
        self.assertEqual(os.listdir(self.dir), ['dtm-0-0-6-2-2m-base699.u16.gz'])
        again = cached(self.dir, 0, 0, 6, 2, 2, make)
        self.assertEqual(len(made), 1, 'read from the cache the second time')
        self.assertEqual((list(again[0]), again[1]), (list(first[0]), first[1]))
        self.assertEqual(decode(*again), [700.0, 710.5, None])

    def test_cache_from_before_bases(self):
        # a cache file with no base in its name (as cave repos have committed) is centimetres above 0
        with gzip.open(os.path.join(self.dir, 'dtm-0-0-4-2-2m.u16.gz'), 'wb') as g:
            g.write(array.array('H', [23800, 0]).tobytes())
        heights, base = cached(self.dir, 0, 0, 4, 2, 2, lambda: self.fail('fetched'))
        self.assertEqual(decode(heights, base), [238.0, None])

    def test_low_ground_keeps_the_old_name(self):
        cached(self.dir, 0, 0, 4, 2, 2, lambda: array.array('d', [238.0, 240.0]))
        self.assertEqual(os.listdir(self.dir), ['dtm-0-0-4-2-2m.u16.gz'])


class Scene(unittest.TestCase):
    """The ground's base reaches scene.json unchanged in a build with passage walls
    (whose own index offsets once shared its name)."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        repo = os.path.join(cls.tmp, 'repo')
        os.makedirs(os.path.join(repo, 'data'))
        shutil.copy(os.path.join(DATA, 'tiny.3d'), os.path.join(repo, 'data'))
        # two boxes along the first legs, as two scraps' walls in a .lox (chunk type 4)
        boxes = [[(50000 + x, 50000 - y, 200 + z) for x in (-1, 1) for y in (0, 5) for z in (-3, 1)],
                 [(50000 + x, 49995 - y, 197 + z) for x in (-1, 1) for y in (0, 8) for z in (-2, 1)]]
        tris = [(0, 1, 2), (1, 2, 3), (4, 5, 6), (5, 6, 7)]
        recs, data = b'', b''
        for pts in boxes:
            ppos = len(data)
            data += struct.pack(f'<{3 * len(pts)}d', *[c for p in pts for c in p])
            tpos = len(data)
            data += struct.pack(f'<{3 * len(tris)}I', *[k for t in tris for k in t])
            recs += struct.pack('<8I', 0, 0, len(pts), ppos, 0, len(tris), tpos, 0)
        with open(os.path.join(repo, 'walls.lox'), 'wb') as f:
            f.write(struct.pack('<4I', 4, len(recs), len(boxes), len(data)) + recs + data)
        cfg = {'caves': [{'id': 'tiny', 'name': 'Tiny Cave', 'area': 'Nowhere', 'credit': 'made up for the tests',
                          'grid': {'offset': [300000, 100000]}, 'survey': {'type': 'survex', 'file': 'data/tiny.3d'},
                          'entrances': {'tiny.ent': 'Tiny Entrance'}, 'terrain': {'type': 'flat', 'cache': None},
                          'walls': {'lox': 'walls.lox'}}]}
        with open(os.path.join(repo, 'caves.json'), 'w') as f:
            json.dump(cfg, f)
        cls.out = os.path.join(cls.tmp, 'site')
        r = subprocess.run([sys.executable, '-m', 'caveviewer', 'build', os.path.join(repo, 'caves.json'), '--out', cls.out],
                           cwd=ROOT, capture_output=True, text=True, env={**os.environ, 'CHROMIUM': ''})
        if r.returncode:
            raise AssertionError(f'the build failed:\n{r.stdout}\n{r.stderr}')
        with open(os.path.join(cls.out, 'tiny', 'scene.json')) as f:
            cls.scene = json.load(f)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_walls_built(self):
        self.assertGreater(len(self.scene['walls']['idx']), 12, 'both scraps')

    def test_ground_where_it_was_put(self):
        # flat ground 10 m over the cave's top: base 0, and min and max both that height
        t, top = self.scene['terrain'], self.scene['stats']['top']
        self.assertEqual(t['base'], 0)
        self.assertAlmostEqual(t['min'], top + 10, places=1)
        self.assertAlmostEqual(t['max'], top + 10, places=1)


if __name__ == '__main__':
    unittest.main()


def float_tiff(values, w, h, x0, y0, px):
    """A single-band float32 GeoTIFF, uncompressed, one strip."""
    data = struct.pack(f'<{w * h}f', *values)
    entries = [(256, 4, 1, w), (257, 4, 1, h), (258, 3, 1, 32), (259, 3, 1, 1), (273, 4, 1, 0),
               (277, 3, 1, 1), (278, 4, 1, h), (279, 4, 1, len(data)), (339, 3, 1, 3),
               (33550, 12, 3, struct.pack('<3d', px, px, 0)), (33922, 12, 6, struct.pack('<6d', 0, 0, 0, x0, y0, 0))]
    ifd_at = 8
    extra_at = ifd_at + 2 + 12 * len(entries) + 4
    extra, body = b'', b''
    for tag, typ, n, v in entries:
        if isinstance(v, bytes):
            body += struct.pack('<HHII', tag, typ, n, extra_at + len(extra))
            extra += v
        elif typ == 3:
            body += struct.pack('<HHIHH', tag, typ, n, v, 0)
        else:
            body += struct.pack('<HHII', tag, typ, n, v)
    strip_at = extra_at + len(extra)
    body = body.replace(struct.pack('<HHII', 273, 4, 1, 0), struct.pack('<HHII', 273, 4, 1, strip_at))
    return b'II*\0' + struct.pack('<I', ifd_at) + struct.pack('<H', len(entries)) + body + b'\0\0\0\0' + extra + data


class EAPieces(unittest.TestCase):
    """A big area from the Environment Agency, a piece at a time (a fake service: no network)."""
    def setUp(self):
        import re
        from caveviewer.terrain import ea
        self.ea, self.asked = ea, []

        def get(url):
            e0, e1 = map(int, re.search(r'subset=E\((\d+),(\d+)\)', url).groups())
            n0, n1 = map(int, re.search(r'subset=N\((\d+),(\d+)\)', url).groups())
            m = re.search(r'scaleFactor=([\d.]+)', url)
            px = round(1 / float(m.group(1))) if m else 1
            w, h = (e1 - e0) // px, (n1 - n0) // px
            self.asked.append((e1 - e0, n1 - n0, px))
            # the height at a pixel's middle: 1 cm a metre east, 1 mm a metre north
            vals = [(e0 + (i + 0.5) * px) * 0.01 + (n1 - (j + 0.5) * px) * 0.001 for j in range(h) for i in range(w)]
            return float_tiff(vals, w, h, e0, n1, px)
        self.real, ea.get = ea.get, get

    def tearDown(self):
        self.ea.get = self.real

    def check(self, e0, n0, e1, n1, step):
        out = self.ea.fetch(e0, n0, e1, n1, step)
        w, h = (e1 - e0) // step, (n1 - n0) // step
        self.assertEqual(len(out), w * h)
        for i, j in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, h // 3)):
            e, n = e0 + (i + 0.5) * step, n1 - (j + 0.5) * step
            self.assertAlmostEqual(out[j * w + i], e * 0.01 + n * 0.001, places=2, msg=(i, j))

    def test_coarse_sampled_by_the_service(self):
        self.check(345000, 151000, 349800, 153400, 8)
        self.assertTrue(all(px == 8 and w <= self.ea.COARSE_PIECE for w, h, px in self.asked))
        self.assertGreater(len(self.asked), 1)

    def test_fine_averaged_here(self):
        self.check(345000, 151000, 346400, 151600, 2)
        self.assertTrue(all(px == 1 and w <= self.ea.PIECE for w, h, px in self.asked))
        self.assertGreater(len(self.asked), 1)

    def test_small_in_one(self):
        self.check(345000, 151000, 345600, 151400, 2)
        self.assertEqual(len(self.asked), 1)


class Patiently(unittest.TestCase):
    """The LiDAR service, asked again after it says it's asked too often."""
    def test_waits_and_tries_again(self):
        import urllib.error
        from caveviewer.terrain import ea
        calls, waits = [], []

        def get(url):
            calls.append(url)
            if len(calls) < 3:
                raise urllib.error.HTTPError(url, 429, 'Too Many Requests', {'Retry-After': '30'}, None)
            return b'ok'
        real, ea.get = ea.get, get
        try:
            self.assertEqual(ea.patiently('u', sleep=waits.append), b'ok')
        finally:
            ea.get = real
        self.assertEqual(waits, [30, 30])          # (as long as it says, longer than the 5 and 10 s it would wait)

    def test_gives_up_in_the_end(self):
        from caveviewer.terrain import ea

        def get(url):
            raise TimeoutError('timed out')
        real, ea.get = ea.get, get
        try:
            with self.assertRaises(TimeoutError):
                ea.patiently('u', sleep=lambda s: None)
        finally:
            ea.get = real
