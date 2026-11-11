"""A smoke test: the fixture cave (tests/fixture) builds, and its pages say
what the config says.

    python -m unittest discover -s tests
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, 'fixture')
ROOT = os.path.dirname(HERE)


class Build(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # the fixture, copied (its work folder goes inside it)
        cls.tmp = tempfile.mkdtemp()
        cls.repo = os.path.join(cls.tmp, 'repo')
        shutil.copytree(FIXTURE, cls.repo, ignore=shutil.ignore_patterns('build', 'site'))
        cls.out = os.path.join(cls.tmp, 'site')
        r = subprocess.run([sys.executable, '-m', 'caveviewer', 'build', os.path.join(cls.repo, 'caves.json'), '--out', cls.out],
                           cwd=ROOT, capture_output=True, text=True, env={**os.environ, 'CHROMIUM': ''})
        cls.log = r.stderr
        if r.returncode:
            raise AssertionError(f'the build failed:\n{r.stdout}\n{r.stderr}')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def scene(self, path):
        return json.load(open(os.path.join(self.out, path, 'scene.json')))

    def test_files(self):
        for f in ('index.html', 'scene.json', 'terrain.bin', 'manifest.webmanifest', 'sw.js', 'icon-192.png',
                  'vendor/three/build/three.module.js', 'vendor/inter/inter.css'):
            self.assertTrue(os.path.exists(os.path.join(self.out, 'tiny', f)), f)
        self.assertTrue(os.path.exists(os.path.join(self.out, 'index.html')), 'the landing page')
        self.assertTrue(os.path.exists(os.path.join(self.repo, 'build', 'tiny', 'names.json')), 'the work folder')
        self.assertNotIn('no place', self.log)

    def test_scene(self):
        s = self.scene('tiny')
        self.assertEqual(s['title'], 'Tiny Cave')
        self.assertEqual(s['grid_ref'], 'ST 50000 50000')
        self.assertEqual(s['stats']['length'], 93)              # (96.5 m of tape, after cavern closes the loop)
        names = {n['t'] for n in s['names']}
        self.assertEqual(names, {'Tiny Entrance', 'The Fork', 'The Loop', 'The Pitch', 'The End'})
        self.assertTrue(s['names'][0].get('entrance'))
        g = s['graph']
        self.assertEqual(len(g['pos']) // 3, 10)               # (ten stations, one node each)
        self.assertEqual(len(g['edges']) // 2, 10)
        self.assertTrue(g['way'], 'the usual way')
        self.assertEqual(s['trips'][0]['name'], 'Round the loop')
        terrain = os.path.getsize(os.path.join(self.out, 'tiny', 'terrain.bin'))
        self.assertEqual(terrain, s['terrain']['w'] * s['terrain']['h'] * 2)
        self.assertEqual(s['features'], {'drawn': False})       # (everything else on; no drawn survey, so the page doesn't ask for one)

    def test_page(self):
        page = open(os.path.join(self.out, 'tiny', 'index.html'), encoding='utf-8').read()
        self.assertEqual(re.findall(r'\{\{\w+\}\}', page), [], 'every placeholder filled')
        self.assertIn('<title>Tiny Cave in 3D</title>', page)
        self.assertIn('Survey: made up for the tests', page)
        self.assertIn('<a href="data/tiny.svx">the test survey</a>', page)
        sw = open(os.path.join(self.out, 'tiny', 'sw.js')).read()
        self.assertIn("'tiny-tiles'", sw)                         # (its own caches)
        for k in ('__VERSION__', '__FILES__', '__ID__'):
            self.assertNotIn(k, sw)
        man = json.load(open(os.path.join(self.out, 'plain', 'manifest.webmanifest')))
        self.assertEqual(man['short_name'], 'Tiny plain')

    def test_features_off(self):
        s = self.scene('plain')
        self.assertEqual(s['features'], {'routes': False, 'drawn': False, 'ar': False, 'offline': False})
        self.assertFalse(os.path.exists(os.path.join(self.out, 'plain', 'sw.js')), 'no service worker when offline is off')

    def test_landing(self):
        page = open(os.path.join(self.out, 'index.html'), encoding='utf-8').read()
        self.assertIn('<title>Test caves in 3D</title>', page)
        self.assertIn('href="tiny/"', page)
        self.assertIn('href="plain/"', page)
        self.assertIn('Tiny Cave: made up for the tests', page)


class Config(unittest.TestCase):
    def write(self, cfg):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        p = os.path.join(d, 'caves.json')
        json.dump(cfg, open(p, 'w'))
        return p

    def test_defaults_merge(self):
        sys.path.insert(0, ROOT)
        from caveviewer.config import Config as C
        c = C(self.write({'defaults': {'terrain': {'type': 'ea', 'step': 4}, 'survey': {'type': 'survex', 'file': 'x.3d'}},
                          'caves': [{'id': 'a', 'name': 'A', 'terrain': {'step': 2}}, {'id': 'b', 'name': 'B'}]}))
        self.assertEqual([x['terrain']['type'] for x in c.caves], ['ea', 'ea'])
        self.assertEqual([x['terrain']['step'] for x in c.caves], [2, 4])
        self.assertEqual(c.caves[0]['terrain']['margin'], 250)
        self.assertEqual(c.caves[0]['path'], 'a')
        self.assertTrue(c.site['index'])

    def test_errors(self):
        from caveviewer.config import Config as C, ConfigError
        for bad in ({'caves': []},
                    {'caves': [{'id': 'a'}]},
                    {'caves': [{'id': 'a', 'name': 'A', 'terrain': {'type': 'mars'}}]},
                    {'caves': [{'id': 'a', 'name': 'A', 'survey': {'type': 'survex', 'file': 'x.3d'}, 'features': {'sound': True}}]},
                    {'caves': [{'id': 'a', 'name': 'A', 'survey': {'type': 'survex', 'file': 'x.3d'}, 'drawn': {'type': 'therion-svg'}}]},
                    {'caves': [{'id': 'a', 'name': 'A', 'survey': {'type': 'survex', 'file': 'x.3d'}, 'drawn': {'type': 'scan'}}]}):
            with self.assertRaises(ConfigError, msg=bad):
                C(self.write(bad))


if __name__ == '__main__':
    unittest.main()


class Walls(unittest.TestCase):
    """Walls from plan drawings, put back on the survey (scene.fit_walls)."""
    def leg_and_walls(self, lift, splay_up=None):
        legs = [((0, 0, 0), (10, 0, 0), 0)]
        if splay_up:
            legs.append(((0, 0, 0), (0, 0, splay_up), 4))
        # a box round the leg, 2 m wide and 2 m high, lifted by `lift`
        pts = [(x, y, z + lift) for x in (0, 10) for y in (-1, 1) for z in (-1, 1)]
        return legs, [(pts, [(0, 1, 2), (1, 2, 3)])]

    def test_moved_back_onto_the_leg(self):
        sys.path.insert(0, ROOT)
        from caveviewer.scene import fit_walls
        legs, walls = self.leg_and_walls(12)
        z = [p[2] for p in fit_walls(walls, legs)[0][0]]
        self.assertAlmostEqual(min(z), -1, places=3)
        self.assertAlmostEqual(max(z), 1, places=3)

    def test_left_alone_when_on_the_leg(self):
        from caveviewer.scene import fit_walls
        legs, walls = self.leg_and_walls(0.5)
        self.assertEqual([p[2] for p in fit_walls(walls, legs)[0][0]], [p[2] for p in walls[0][0]])

    def test_roof_raised_to_the_splays(self):
        from caveviewer.scene import fit_walls
        legs, walls = self.leg_and_walls(0, splay_up=3)
        z = [p[2] for p in fit_walls(walls, legs)[0][0]]
        self.assertAlmostEqual(max(z), 3, places=3)        # (up to where the splay reached)
        self.assertAlmostEqual(min(z), -1, places=3)       # (no splay down: the floor stays)


class WallsOwnSurvey(unittest.TestCase):
    """A steep passage's walls stay on its own legs, not on another survey's
    passage beneath it that's nearer in plan (scene.own_legs, scene.fit_walls)."""
    def setUp(self):
        # a rift dropping 20 m north (its own survey, A), over a passage of
        # another survey (B) 30 m below that runs straight under its walls
        self.stations = [('S.A.1', (0, 0, 0), 2), ('S.A.2', (0, 4, -20), 2),
                         ('S.B.1', (-10, 6, -30), 2), ('S.B.2', (10, 6, -30), 2)]
        at = dict((n, p) for n, p, f in self.stations)
        self.legs = [(at['S.A.1'], at['S.A.2'], 0), (at['S.B.1'], at['S.B.2'], 0)]
        # the rift's drawing reaches a couple of metres past its end, over B
        pts = [(x, y, -20 + z) for x in (-1, 1) for y in (4, 6) for z in (-1, 1)]
        self.walls = [(pts, [(0, 1, 2), (1, 2, 3)])]

    def test_kept_on_its_own_legs(self):
        from caveviewer.scene import fit_walls, own_legs
        own = own_legs(['S.A'], self.legs, self.stations)
        self.assertEqual(own[0].tolist(), [True, False])
        z = [p[2] for p in fit_walls(self.walls, self.legs, own)[0][0]]
        self.assertGreater(min(z), -23)

    def test_without_it_hung_on_the_passage_beneath(self):
        from caveviewer.scene import fit_walls
        z = [p[2] for p in fit_walls(self.walls, self.legs)[0][0]]
        self.assertLess(min(z), -28)        # (what it did: the slab)

    def test_another_survey_at_its_height(self):
        from caveviewer.scene import fit_walls, own_legs
        # B at the rift's foot: the drawing's end over it may hang from it
        stations = self.stations[:2] + [('S.B.1', (-10, 6, -20), 2), ('S.B.2', (10, 6, -20), 2)]
        at = dict((n, p) for n, p, f in stations)
        legs = [self.legs[0], (at['S.B.1'], at['S.B.2'], 0)]
        own = own_legs(['S.A'], legs, stations)
        pts = [(x, 6, -20 + z) for x in (-1, 1) for z in (-1, 1)]
        z = [p[2] for p in fit_walls([(pts, [(0, 1, 2)])], legs, own)[0][0]]
        self.assertAlmostEqual(min(z), -21, places=3)
        self.assertAlmostEqual(max(z), -19, places=3)


class WallBridges(unittest.TestCase):
    """A wall triangle spanning the gap between two unconnected passages is left out (scene.bridges)."""
    def test_fin_across_a_gap(self):
        from caveviewer.scene import bridges
        legs = [((0, 0, 0), (10, 0, 0), 0), ((60, 0, 0), (70, 0, 0), 0)]
        pts = [(0, 1, 0), (10, 1, 0), (5, 2, 1), (60, 1, 0), (70, 1, 0), (65, 2, 1)]
        walls = [(pts, [(0, 1, 2), (3, 4, 5), (1, 2, 3)])]
        # the first two are each passage's own walls; the third joins them
        self.assertEqual(bridges(walls, legs), {(0, 2)})


class WallOutliers(unittest.TestCase):
    """A wall point Therion put far off its passage is brought back (scene.fit_walls)."""
    def walls(self, stray):
        pts = [(x, y, z) for x in (0, 10) for y in (-1, 1) for z in (-1, 1)] + [(5, 1, stray)]
        return [(pts, [(0, 1, 2), (1, 2, 3), (2, 3, 8)])]

    def test_kept_to_the_splays(self):
        from caveviewer.scene import fit_walls
        legs = [((0, 0, 0), (10, 0, 0), 0), ((0, 0, 0), (0, 0, 3), 4)]
        z = [p[2] for p in fit_walls(self.walls(50), legs)[0][0]]
        self.assertAlmostEqual(max(z), 4, places=3)          # (3 m of splay and 1 m of slack, not 50)

    def test_kept_near_the_rest_without_splays(self):
        from caveviewer.scene import fit_walls, CAP
        legs = [((0, 0, 0), (10, 0, 0), 0)]
        z = [p[2] for p in fit_walls(self.walls(-60), legs)[0][0]]
        self.assertGreaterEqual(min(z), -CAP)
        self.assertLessEqual(max(z), 1)
