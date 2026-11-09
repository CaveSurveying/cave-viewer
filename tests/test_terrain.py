"""The ground's heights: centimetres above a base, in 16 bits, and the cache.

    python -m unittest discover -s tests
"""
import array
import gzip
import math
import os
import shutil
import tempfile
import unittest

from caveviewer.terrain import cached, encode, ground

NAN = math.nan


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


if __name__ == '__main__':
    unittest.main()
