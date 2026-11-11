"""Entrance names for a survey with many entrances, from its surveys' names.

    python -m unittest discover -s tests
"""
import unittest

from caveviewer.survey import default_entrances, nice


def entrances(*names):
    return default_entrances({'name': 'Tiny Cave'}, [(n, (0, 0, 0), 4) for n in names])


class Nice(unittest.TestCase):
    def test_words(self):
        self.assertEqual(nice('treak_cliff_cavern'), 'Treak Cliff Cavern')
        self.assertEqual(nice('lancasterhole'), 'Lancaster Hole')
        self.assertEqual(nice('greatdoukpot'), 'Great Douk Pot')
        self.assertEqual(nice('rescuepot1'), 'Rescue Pot 1')
        self.assertEqual(nice('upper-skirwith-entrance'), 'Upper Skirwith Entrance')
        self.assertEqual(nice('p8'), 'P8')
        self.assertEqual(nice('5ways'), '5 Ways')
        self.assertEqual(nice('pipikinentrance'), 'Pipikin Entrance')


class Entrances(unittest.TestCase):
    def test_one_entrance_is_the_cave(self):
        self.assertEqual(entrances('tiny.ent'), {'tiny.ent': 'Tiny Entrance'})

    def test_named_after_their_caves(self):
        # an area (easegill: entrances in three of its surveys) is passed down through
        e = entrances('nc3.easegill.lancasterhole.l1.001', 'nc3.easegill.cowpot.entrance',
                      'nc3.easegill.pippikinpot.p.0', 'nc3.kingsdale.keldhead.1')
        self.assertEqual(list(e.values()), ['Lancaster Hole', 'Cow Pot', 'Pippikin Pot', 'Kingsdale'])
        # (an area with fewer than three caves in it is taken for a cave: kingsdale here, and
        # names.json or the config's entrances name it better)

    def test_one_cave_with_several_entrances(self):
        # told apart by their stations' names where those say something, else numbered
        e = entrances('area.skirwithcave.upper-skirwith-entrance', 'area.skirwithcave.lower-skirwith-entrance',
                      'area.gorge.ps', 'area.gorge.smr', 'area.white_scar.entrance')
        self.assertEqual(sorted(e.values()), ['Gorge', 'Gorge 2', 'Skirwith Cave (Lower Skirwith Entrance)',
                                              'Skirwith Cave (Upper Skirwith Entrance)', 'White Scar'])

    def test_numbers_and_file_names_passed_over(self):
        # a station named for its cave; a survey named for its file; codes kept when there's nothing better
        e = entrances('kd.east.bradagarthpot', 'kd.east.surfacemaster.surface2.53', 'kd.east.swinsto.a.1',
                      'kd.east.rowtenpot.b.2', 'kd.east.kingpot.c.1', 'kd.p8.p8.0')
        self.assertEqual(list(e.values()), ['Bradagarth Pot', 'East', 'Swinsto', 'Rowten Pot', 'King Pot', 'P8'])

    def test_surface_surveys_passed_over(self):
        # a surface survey that ties several entrances in names none of them: their stations do
        e = entrances('nc3.leck.yeadon_pipikin_surface_survey.pipikinentrance',
                      'nc3.leck.yeadon_pipikin_surface_survey.smokeyhole',
                      'nc3.leck.yeadon_pipikin_surface_survey.petersonspot',
                      'nc3.leck.lostjohns.entrance', 'nc3.leck.ireby.akahole.entrance')
        self.assertEqual(list(e.values())[:3], ['Pipikin Entrance', 'Smokey Hole', 'Petersons Pot'])

    def test_entrance_surveys(self):
        # a survey in a cave named for its entrance names it, unless it repeats the cave's name
        e = entrances('nc3.wk.kmc.valleyentrance.0', 'nc3.wk.kmc.roof_tunnel.2', 'nc3.wk.swinsto.1',
                      'nc3.wk.hammerpot.hammerentrance.0', 'nc3.wk.rowtenpot.1')
        self.assertEqual(e['nc3.wk.kmc.valleyentrance.0'], 'Valley Entrance')
        self.assertEqual(e['nc3.wk.kmc.roof_tunnel.2'], 'Kmc')
        self.assertEqual(e['nc3.wk.hammerpot.hammerentrance.0'], 'Hammer Pot')

    def test_all_different(self):
        e = entrances('a.x.jinglingcavetop.7', 'a.x.jinglingcavetop.3', 'a.x.jinglingcavetop2.9x', 'a.y.z.1')
        self.assertEqual(len(set(e.values())), 4)


class EntrancesOver(unittest.TestCase):
    def test_renames_and_adds_keeping_the_rest(self):
        """names.entrances renames one found entrance and adds another, keeping the rest."""
        import tempfile
        from caveviewer.survey import names_json

        class Cfg:
            def __init__(self, d): self.d = d
            def at(self, p): return p
            def work_dir(self, cave): return self.d
        with tempfile.TemporaryDirectory() as d:
            cave = {'names': {'entrances': {'a.rr.1': 'Rhino Rift', 'a.uf.ws18': 'Upper Flood Swallet'}}}
            out = names_json(Cfg(d), cave, {}, '', {'a.rr.1': 'R Rift', 'a.gb.0': 'GB'})
        self.assertEqual(out['entrances'], {'a.rr.1': 'Rhino Rift', 'a.gb.0': 'GB', 'a.uf.ws18': 'Upper Flood Swallet'})


if __name__ == '__main__':
    unittest.main()
