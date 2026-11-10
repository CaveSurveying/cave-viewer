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


class LoxWallSurveys(unittest.TestCase):
    def test_each_scrap_its_survey(self):
        """Each scrap in a .lox is named by its survey's dotted path."""
        import struct
        import tempfile
        from caveviewer.formats import lox_wall_surveys
        names = b'Top\0Cave\0'
        surveys = struct.pack('<6I', 0, 0, 0, 0, 0, 0) + struct.pack('<6I', 1, 0, 3, 0, 0, 0) + struct.pack('<6I', 2, 4, 4, 1, 0, 0)
        scraps = struct.pack('<8I', 0, 2, 0, 0, 0, 0, 0, 0) + struct.pack('<8I', 1, 1, 0, 0, 0, 0, 0, 0)
        d = struct.pack('<4I', 1, len(surveys), 3, len(names)) + surveys + names
        d += struct.pack('<4I', 4, len(scraps), 2, 0) + scraps
        with tempfile.NamedTemporaryFile(suffix='.lox', delete=False) as f:
            f.write(d)
        self.assertEqual(lox_wall_surveys(f.name), ['Top.Cave', 'Top'])


if __name__ == '__main__':
    unittest.main()
