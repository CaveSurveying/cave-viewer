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
import sys

from caveviewer.formats import read_3d

# the names config, each kept in names.json as it is (with its default)
NAME_KEYS = (('ways', list), ('offway', lambda: 1.6), ('codes', dict), ('avoid', dict), ('alone', list), ('trips', list), ('sumps', list))


def default_entrances(cave, stations):
    """The stations the survey flags as entrances, each named after the cave."""
    t = cave['name'].replace(' Cave', '').replace(' Hole', '').replace(' Swallet', '') + ' Entrance'
    return {n: t for n, p, f in stations if f & 4}


def names_json(cfg, cave, places, comment, entrances=None, sort=False):
    """Write <work>/<cave>/names.json: the given places (from the drawing's
    labels) under the config's own, and the rest of the names config."""
    base = json.load(open(cfg.at(cave['names']['file']), encoding='utf-8')) if cave['names'].get('file') else {}
    out = {'_comment': comment, **({k: v for k, v in base.items() if k != '_comment'})}
    out['entrances'] = cave.get('entrances') or base.get('entrances') or entrances or {}
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
    legs, stations = read_3d(cfg.centreline(cave))
    nm = names_json(cfg, cave, {}, f'Made by caveviewer from {cave["survey"]["file"]} and the config.',
                    default_entrances(cave, stations))
    print(f'{cave["name"]}: {len(nm["entrances"])} entrance(s), {len(nm["places"])} places', file=sys.stderr)
    return True
