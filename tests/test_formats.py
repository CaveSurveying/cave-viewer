"""The file readers, on small files made with the real programs.

    python -m unittest discover -s tests
"""
import os
import unittest

from caveviewer.formats import read_3d

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixture', 'data')


class Read3d(unittest.TestCase):
    def test_passage_dimensions(self):
        # lrud.3d (cavern lrud.svx) has passage cross-sections: two passages,
        # each with its end marked, one of them with a width too big for
        # 16 bits. The reader skips them all and still finds every leg and
        # station, as Survex's dump3d lists them (6 LINE, 7 NODE).
        legs, stations = read_3d(os.path.join(DATA, 'lrud.3d'))
        self.assertEqual(len(legs), 6)
        self.assertEqual(sorted(n for n, _, _ in stations),
                         ['lrud.1', 'lrud.2', 'lrud.3', 'lrud.4', 'lrud.5', 'lrud.6', 'lrud.ent'])
        ent = next(xyz for n, xyz, _ in stations if n == 'lrud.ent')
        self.assertEqual(ent, (50000.0, 50000.0, 200.0))
        self.assertTrue(next(f for n, _, f in stations if n == 'lrud.ent') & 4, 'the entrance flag')


if __name__ == '__main__':
    unittest.main()
