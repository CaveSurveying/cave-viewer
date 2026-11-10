import json
import os
import re
import tempfile
import unittest

from caveviewer.offline import offline

HERE = os.path.join(os.path.dirname(__file__), '..', 'caveviewer', 'viewer')


def listed(out):
    sw = open(os.path.join(out, 'sw.js')).read()
    return json.loads(re.search(r'const FILES = (\[.*?\]);', sw, re.S).group(1))


class Offline(unittest.TestCase):
    def test_leaves_out_caves_below_it(self):
        """A whole area's page at the site's root keeps its own files, not its caves' pages in folders below it."""
        with tempfile.TemporaryDirectory() as out:
            for f in ('index.html', 'scene.json', 'terrain.bin'):
                open(os.path.join(out, f), 'w').write('x')
            os.makedirs(os.path.join(out, 'goughs'))
            for f in ('index.html', 'scene.json'):
                open(os.path.join(out, 'goughs', f), 'w').write('x')
            offline(out, HERE)
            files = listed(out)
            self.assertIn('scene.json', files)
            self.assertIn('terrain.bin', files)
            self.assertFalse([f for f in files if f.startswith('goughs/')])
            self.assertTrue([f for f in files if f.startswith('vendor/')])


if __name__ == '__main__':
    unittest.main()
