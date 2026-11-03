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
