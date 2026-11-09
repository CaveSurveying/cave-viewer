"""A Therion project, built for the 3D view: checked out (where the config
gives a Subversion URL) and built with Therion, after cavern for any Survex
files it imports.

survey: {"type": "therion", "svn": URL, "checkout": folder, "dir": the cave's
folder in it, "source": its main .th file, "svx": [Survex files to build
first], "select": [Therion selects], "from": what the drawing's comment
names as its origin}

Writes <work>/<cave>/: cave.3d (the centreline, Survex format), plan.svg
(north up at 1:500, coloured by altitude, the grid's coordinates on it),
esri/ (the same drawing as GIS layers), credits.json and names.json.
"""
import json
import math
import os
import re
import subprocess
import sys

from caveviewer.esri import read_lines, read_points
from caveviewer.formats import read_3d
from caveviewer.survey import default_entrances, names_json

CONFIG = 'thconfig.web'          # written into the cave's folder in the checkout (Therion reads its sources relative to it)


def checkout(cfg, survey, fetch=True):
    """The Subversion checkout, made or (fetch) brought up to date, where the config gives a URL."""
    reg = cfg.at(survey['checkout'])
    if not survey.get('svn'):
        return
    if os.path.isdir(os.path.join(reg, '.svn')):
        if fetch:
            subprocess.run(['svn', 'update', '-q', reg], check=True)
    else:
        subprocess.run(['svn', 'checkout', '-q', survey['svn'], reg], check=True)


def from_drawings(cave):
    """Whether the cave's walls are to come from its Therion drawings (walls.type \"therion\")."""
    return bool(cave['walls']) and cave['walls'].get('type') == 'therion'


def build(cfg, cave, fetch=True):
    sv = cave['survey']
    checkout(cfg, sv, fetch)
    reg = cfg.at(sv['checkout'])
    d = os.path.join(reg, sv['dir'])
    os.makedirs(cfg.work_dir(cave), exist_ok=True)
    out = os.path.relpath(cfg.work_dir(cave), d)
    for svx in sv.get('svx', []):
        # (in the Survex file's own folder, where Therion's import looks for the .3d)
        subprocess.run(['cavern', os.path.basename(svx)], cwd=os.path.join(d, os.path.dirname(svx)), check=True, capture_output=True)
    common = os.path.exists(os.path.join(reg, 'common_layout.th'))
    cfg_lines = [
        'encoding utf-8',
        f'source {sv["source"]}',
        *[f'select {s}' for s in sv.get('select', [])],
        f'export model -fmt survex -o {out}/cave.3d',
        f'export map -proj plan -fmt svg -layout web -o {out}/plan.svg',
        f'export map -proj plan -fmt esri -o {out}/esri',
        # the passage walls, from the drawings only (by default Therion also
        # builds them from every splay, which come out as spikes)
        *([f'export model -fmt loch -wall-source maps -o {out}/walls.lox'] if from_drawings(cave) else []),
        'layout web',
        *(['copy common'] if common else []),
        'scale 1 500', 'colour map-bg transparent', 'colour map-fg altitude', 'debug off',
        # the sheet's own title block, under the drawing: the cave, its length
        # and depth, who surveyed and drew it, its copyright, the altitude key
        'map-header 0 0 nw', 'map-header-bg off', 'colour-legend on', 'legend off',
        'statistics explo off', 'statistics topo all', 'statistics carto all', 'statistics copyright all',
        f'map-comment "{cave["name"]}: {sv.get("from", "the survey data")}/{sv["dir"]}"',
        'grid bottom', 'grid-size 100 100 100 m', 'grid-coords border',
        'endlayout',
        *([f'input {os.path.relpath(os.path.join(reg, "common_layout.th"), d)}'] if common else []),
    ]
    with open(os.path.join(d, CONFIG), 'w') as f:
        f.write('\n'.join(cfg_lines) + '\n')
    r = subprocess.run(['therion', CONFIG], cwd=d, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(os.path.join(cfg.work_dir(cave), 'plan.svg'))
    print(f'{cave["name"]}: {"built" if ok else "FAILED"}', file=sys.stderr)
    if not ok:
        print('\n'.join((r.stdout + r.stderr).splitlines()[-15:]), file=sys.stderr)
        return False
    names(cfg, cave)
    credits(cfg, cave)
    return True


def credits(cfg, cave):
    """build/<cave>/credits.json, for the drawn survey's title block: who
    surveyed it (the teams in its files, most often first) and who holds
    the copyright, as its files say."""
    team, rights = {}, {}
    data = os.path.join(cfg.at(cave['survey']['checkout']), cave['survey']['dir'])
    for root, dirs, files in os.walk(data):
        for f in files:
            if not f.endswith(('.th', '.th2', '.svx')):
                continue
            for line in open(os.path.join(root, f), encoding='utf-8', errors='replace'):
                m = re.match(r'\s*(?:team|explo-team)\s+"([^"]+)"', line, re.I)
                if m:
                    team[m[1].strip()] = team.get(m[1].strip(), 0) + 1
                m = re.match(r'\s*copyright\s+\S+\s+"([^"]+)"', line, re.I)
                if m:
                    rights[m[1].strip()] = rights.get(m[1].strip(), 0) + 1
    licence = re.compile(r'creative|creaative|\bcc\b|gpl|licen', re.I)
    json.dump({'surveyed': [t for t, n in sorted(team.items(), key=lambda x: -x[1]) if len(t) > 2],
               'copyright': [t for t, n in sorted(rights.items(), key=lambda x: -x[1]) if not licence.search(t)]},
              open(os.path.join(cfg.work_dir(cave), 'credits.json'), 'w'), indent=2, ensure_ascii=False)


# the drawings' notes, not names: dates, heights and depths, grid numbers,
# question marks, and words that name a kind of thing rather than a place
NOTE = re.compile(r'\d{1,2}/\d{1,2}/\d{2,4}|[-+]?\d+(\.\d+)?\s*m\b|^[-+\d.,\s]+$|^\(.*\)$|\?|^dived\b|^c\d$|^S[A-Z] \d', re.I)
KINDS = {'aven', 'air bell', 'boulder choke', 'choke', 'clay choke', 'call', 'easy', 'sump', 'pool', 'dig', 'squeeze', 'climb', 'inlet', 'duck'}


def name_like(t):
    return t[0].isupper() and not NOTE.search(t) and t.lower() not in KINDS


def names(cfg, cave):
    """<work>/<cave>/names.json: the entrance (the config's, else the stations
    the survey flags as entrances), and the drawing's labels as places."""
    out = cfg.work_dir(cave)
    legs, stations = read_3d(os.path.join(out, 'cave.3d'))
    named = [(n, p) for n, p, f in stations if n and not f & 1]
    places = {}
    labels = []
    if cave['names'].get('labels', True):     # (names.labels false: the entrances only, as for a whole catchment)
        labels = [(x, y, rec) for x, y, rec in read_points(os.path.join(out, 'esri', 'points2d'))]
        # and the names written along passages (line labels), at the middle of each
        labels += [(*pts[len(pts) // 2], rec) for pts, rec in read_lines(os.path.join(out, 'esri', 'lines2d'))]
    for x, y, rec in labels:
        if rec.get('_TYPE') != 'label':
            continue
        t = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', rec.get('_TEXT', ''))).strip()
        if not t or 'entrance' in t.lower() or t in places or t == cave['name'] or not name_like(t):
            continue
        n = min(named, key=lambda s: math.hypot(s[1][0] - x, s[1][1] - y))
        if math.hypot(n[1][0] - x, n[1][1] - y) < 40:
            places[t] = n[0]
    nm = names_json(cfg, cave, places, f'Made by caveviewer from {cave["survey"]["dir"]} in the checkout: the entrance, and the names on the drawn survey, each at the station nearest its label.',
                    default_entrances(cave, stations), sort=True)
    print(f'  {len(nm["entrances"])} entrance(s), {len(places)} places', file=sys.stderr)


