"""Survey grids to lat/long, and grid references.

    python -m unittest discover -s tests
"""
import unittest

from caveviewer.geo import grid_ref, itm_to_ll


class ITM(unittest.TestCase):
    def test_origin(self):
        # ITM's false origin is 53.5 N, 8 W
        lat, lon = itm_to_ll(600000, 750000)
        self.assertAlmostEqual(lat, 53.5, places=7)
        self.assertAlmostEqual(lon, -8.0, places=7)

    def test_burren(self):
        # Fergus River Cave's ground, as PROJ (EPSG:2157 to EPSG:4326) gives it
        lat, lon = itm_to_ll(525350, 692800)
        self.assertAlmostEqual(lat, 52.98074, places=5)
        self.assertAlmostEqual(lon, -9.11163, places=5)


class GridRef(unittest.TestCase):
    def test_national_grid(self):
        self.assertEqual(grid_ref(358026, 213918), 'SO 58026 13918')

    def test_itm(self):
        self.assertEqual(grid_ref(525174.4, 692314.2, 'itm'), 'ITM 525174 692314')


if __name__ == '__main__':
    unittest.main()
