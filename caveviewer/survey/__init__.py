"""The survey step: each cave's centreline and names, in its work folder.

    therion   a Therion project (checked out with Subversion, if the config
              says where from): built to cave.3d, plan.svg (for the drawn
              survey), esri/ (GIS layers, whose labels become place names)
              and credits.json
    survex    a Survex .3d file already in the repo

Either way it writes <work>/<cave>/names.json, what the 3D view's names and
routes are made from: the entrances, the places (by station), and the
config's usual ways, trips, codes, avoid, alone and sumps.
"""
import json
import os
import re
import sys

from caveviewer.formats import read_3d

# the names config, each kept in names.json as it is (with its default)
NAME_KEYS = (('ways', list), ('offway', lambda: 1.6), ('codes', dict), ('avoid', dict), ('alone', list), ('trips', list), ('sumps', list),
             ('apart', list))


def default_entrances(cave, stations):
    """The stations the survey flags as entrances, with names. One entrance is
    named after the cave. Where there are several (a whole area's data, as the
    cave registry's Northern England or the Peak Survex Project give it), each
    is named after the survey it's in: lancasterhole.l1.001 in easegill is
    Lancaster Hole. Areas (a survey with entrances in three or more of its
    own surveys, as easegill has) are passed down through, as are surveys
    named only by a number or a file's own words. Two entrances to one cave
    are told apart by their stations' names where those say something, else
    numbered."""
    ents = [n for n, p, f in stations if f & 4]
    if len(ents) < 2:
        t = cave['name'].replace(' Cave', '').replace(' Hole', '').replace(' Swallet', '') + ' Entrance'
        return {n: t for n in ents}
    paths = [n.split('.') for n in ents]
    top = 0                                             # (the levels every entrance shares: the file's own survey)
    while all(len(p) > top + 1 and p[top] == paths[0][top] for p in paths):
        top += 1

    def cave_of(p):
        for d in range(top, len(p) - 1):
            kids = {q[d + 1] for q in paths if q[:d + 1] == p[:d + 1] and len(q) > d + 2}
            if len(kids) < 3 and not GENERIC.match(p[d]):
                # (a survey in it named for the entrance names it better: kmc.valleyentrance.0,
                # unless it only repeats the cave's name: hammerpot.hammerentrance)
                door = [c for k, c in enumerate(p[:-1]) if k > d and ENTRANCE.match(c) and says(c)
                        and not any(a.lower().startswith(re.sub(r'[_-]?entrance$', '', c.lower())) for a in p[d:k])]
                return door[-1] if door else p[d]
        if says(p[-1]):                                 # (a station named for its cave: bradagarthpot)
            return p[-1]
        named = [c for c in p[top:-1] if not GENERIC.match(c)] or [c for c in p[:-1] if not c.isdigit()]
        return named[-1] if named else cave['name']

    named = [(n, nice(cave_of(p)), p[-1]) for n, p in zip(ents, paths)]
    count = {}
    for _, t, _ in named:
        count[t] = count.get(t, 0) + 1
    out, used = {}, set()
    for n, t, stn in sorted(named, key=lambda e: e[0]):
        if count[t] > 1 and says(stn) and nice(stn) != t:
            t = f'{t} ({nice(stn)})'
        k, name = 1, t
        while name in used:
            k += 1
            name = f'{t} {k}'
        used.add(name)
        out[n] = name
    return {n: out[n] for n in ents}


def says(station):
    """Whether a station's name says something (upper-skirwith-entrance), not just numbers it (12a, ps, e)."""
    return len(station) > 3 and not GENERIC.match(station)


# survey and station names that say nothing of where they are: numbers, "entrance",
# the survey files' own words (master, area, surface, nosplays)
GENERIC = re.compile(r'^(\d+\w{0,2}|[a-z]?\d+[a-z]?|ents?\d*|entrance\d*|main|master|surface\w*|fixed_points|'
                     r'.*[_-](master|area|nosurface|nosplays)\w*|.*[_-]surface([_-]survey)?)$', re.I)   # (yeadon_pipikin_surface_survey)
# a survey named for an entrance (valleyentrance, upper_entrance): not just "entrance"
ENTRANCE = re.compile(r'^.+[a-z_-]entrance$', re.I)
# words cave names run together ("lancasterhole", "greatdoukpot"), split where they end or begin one
_ENDS = ('swallet', 'cavern', 'caves', 'cave', 'pot', 'hole', 'holes', 'mine', 'sinks', 'sink', 'shaft', 'rift',
         'chamber', 'passage', 'inlet', 'dig', 'series', 'head', 'rising', 'level', 'sough', 'adit', 'entrance')
_STARTS = ('great', 'little', 'high', 'low', 'upper', 'lower', 'top', 'old', 'new', 'big')


def nice(s):
    """A survey name as words: treak_cliff_cavern -> Treak Cliff Cavern, rescuepot1 -> Rescue Pot 1,
    upper-skirwith-entrance -> Upper Skirwith Entrance."""
    words = []
    for w in re.split(r'[_\-\s]+', s):
        if not w:
            continue
        w = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', w)                   # camelCase
        w = re.sub(r'(?<=[A-Za-z]{3})(?=\d)|(?<=\d)(?=[A-Za-z]{3})', ' ', w)  # rescuepot1, 5ways (not codes: p8, 2b)
        for part in w.split():
            low = part.lower()
            if low.isalpha() and part == low:
                for end in _ENDS:
                    if low.endswith(end) and len(low) > len(end) + 2:
                        part, low = f'{low[:-len(end)]} {end}', f'{low[:-len(end)]} {end}'
                        break
                first = low.split()[0]
                for start in _STARTS:
                    if first.startswith(start) and len(first) > len(start) + 2:
                        low = f'{start} {low[len(start):]}'
                        break
                part = low
            words += part.split()
    return ' '.join(w[:1].upper() + w[1:] for w in words)


def names_json(cfg, cave, places, comment, entrances=None, sort=False):
    """Write <work>/<cave>/names.json: the given places (from the drawing's
    labels) under the config's own, and the rest of the names config."""
    base = json.load(open(cfg.at(cave['names']['file']), encoding='utf-8')) if cave['names'].get('file') else {}
    out = {'_comment': comment, **({k: v for k, v in base.items() if k != '_comment'})}
    out['entrances'] = cave.get('entrances') or base.get('entrances') or entrances or {}
    # (names.entrances: over those, renaming one or adding one the survey doesn't flag)
    out['entrances'] = {**out['entrances'], **cave['names'].get('entrances', {})}
    out['places'] = {**base.get('places', {}), **places, **cave.get('places', {})}
    if sort:
        out['places'] = dict(sorted(out['places'].items()))
    for k, d in NAME_KEYS:
        out[k] = cave[k] if k in cave else base.get(k, d())
    if cave.get('surveys') or 'surveys' in base:
        out['surveys'] = {**base.get('surveys', {}), **cave.get('surveys', {})}
    d = cfg.work_dir(cave)
    os.makedirs(d, exist_ok=True)
    json.dump(out, open(os.path.join(d, 'names.json'), 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    return out


def build(cfg, cave, fetch=True):
    if cave['survey']['type'] == 'therion':
        from caveviewer.survey import therion
        return therion.build(cfg, cave, fetch)
    # a Survex .3d: its names from the names file (if any) and the config
    legs, stations = cfg.read_centreline(cave)
    nm = names_json(cfg, cave, {}, f'Made by caveviewer from {cave["survey"]["file"]} and the config.',
                    default_entrances(cave, stations))
    print(f'{cave["name"]}: {len(nm["entrances"])} entrance(s), {len(nm["places"])} places', file=sys.stderr)
    return True
