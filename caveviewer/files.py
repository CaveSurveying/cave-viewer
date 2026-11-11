"""The files step: for a cave with a landing page (page), what Therion makes
of its survey for people to download, in <out>/<page>/files/: the plan to
print (PDF, where it has drawings, with a picture of it), the centreline
and the model (Survex .3d, Therion's .lox), KML for Google Earth, and
Therion's lists of its surveys, caves and continuations. And files.json,
which the landing page (pages.py) is made from: what each file is, and the
survey's figures and its surveys, from Therion's survey list.

Each export is tried apart from the rest, so one Therion can't make (a
plan of a whole catchment, say) leaves the others.
"""
import json
import os
import re
import shutil
import subprocess
import sys

CONFIG = 'thconfig.files'

# (suffix, export, title, blurb, kind), in the order the page shows them;
# 'drawn' ones only for a cave with drawings (drawn.type therion-svg)
EXPORTS = [
    ('-plan.pdf', 'export map -proj plan -layout sheet -o {f}', 'Plan', 'The drawn survey to print, coloured by altitude, with its title block, grid and key. Scale 1:500.', 'sheet', True),
    ('.3d', 'export model -fmt survex -o {f}', 'Survex 3D model', 'The centreline. Opens in Aven.', 'data', False),
    ('.lox', 'export model -fmt loch -o {f}', 'Loch 3D model', "Therion's own viewer format, with the passage walls.", 'data', False),
    ('-plan.svg', None, 'Plan, SVG', 'The drawing as vectors: edit in Inkscape or Illustrator.', 'data', True),
    ('-plan.kml', 'export map -proj plan -fmt kml -o {f}', 'Plan, KML', 'The drawn passage outlines, for Google Earth.', 'data', True),
    ('-centreline.kml', 'export model -fmt kml -o {f}', 'Centreline, KML', 'The centreline, for Google Earth.', 'data', False),
    ('-surveys.html', 'export survey-list -o {f}', 'Survey list', 'Every survey in it, with its length and depth.', 'data', False),
    ('-caves.html', 'export cave-list -o {f}', 'Cave list', 'Each cave, with its length and depth.', 'data', False),
    ('-continuations.html', 'export continuation-list -o {f}', 'Continuations', 'Leads still to push, where the survey marks them.', 'data', False),
]

SHEET = [
    'layout sheet',
    'copy common', 'scale 1 500', 'colour map-fg altitude', 'debug off',
    'map-header 0 0 nw', 'colour-legend on', 'legend on',
    'statistics explo all', 'statistics topo all', 'statistics carto all', 'statistics copyright all',
    'grid bottom', 'grid-size 100 100 100 m', 'grid-coords border',
    'endlayout',
]


def therion(d, lines):
    with open(os.path.join(d, CONFIG), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    try:
        return subprocess.run(['therion', CONFIG], cwd=d, capture_output=True, text=True, timeout=1800).returncode == 0
    finally:
        os.remove(os.path.join(d, CONFIG))


def preview(pdf, png, dpi=40):
    """The first page of a PDF as a PNG, by Ghostscript or pdftoppm, where either is here."""
    gs, ppm = shutil.which('gs'), shutil.which('pdftoppm')
    if gs:
        cmd = [gs, '-q', '-dNOPAUSE', '-dBATCH', '-dSAFER', '-sDEVICE=png16m', f'-r{dpi}', '-dFirstPage=1', '-dLastPage=1',
               '-dTextAlphaBits=4', '-dGraphicsAlphaBits=4', f'-sOutputFile={png}', pdf]
    elif ppm:
        cmd = [ppm, '-png', '-r', str(dpi), '-f', '1', '-l', '1', '-singlefile', pdf, png[:-4]]
    else:
        return False
    return subprocess.run(cmd, capture_output=True).returncode == 0 and os.path.exists(png)


def survey_list(path):
    """From Therion's survey list (HTML): the whole survey's figures, and its
    own surveys' (the level below), longest first."""
    s = open(path, encoding='utf-8', errors='replace').read()
    rows = []
    for m in re.finditer(r'<tr id="([^"]+)">(.*?)</tr>', s, re.S):
        tds = re.findall(r'<td[^>]*>(.*?)</td>', m[2], re.S)
        title = re.sub(r'<[^>]+>', '', re.sub(r'<br>.*', '', tds[0], flags=re.S)).strip()
        n = [round(float(x)) if re.fullmatch(r'[\d.]+', x.strip()) else 0 for x in tds[1:]]
        rows.append({'id': m[1], 'title': title, 'length': n[0], 'depth': n[1], 'shots': n[6] if len(n) > 6 else 0,
                     'stations': n[7] if len(n) > 7 else 0})
    if not rows:
        return None, []
    top = rows[0]
    kids = [dict(r, id=r['id'].split('.')[-1]) for r in rows[1:] if r['id'].count('.') == top['id'].count('.') + 1]
    return top, sorted(kids, key=lambda r: -r['length'])


def build(cfg, cave, out):
    if not cave.get('page') or cave['survey']['type'] != 'therion':
        return
    sv = cave['survey']
    reg = cfg.at(sv['checkout'])
    d = os.path.join(reg, sv['dir'])
    dest = os.path.join(out, cave['page'], 'files')
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    rel = os.path.relpath(dest, d)
    base = cave['id']
    drawn = cave['drawn']['type'] == 'therion-svg'
    common = os.path.exists(os.path.join(reg, 'common_layout.th'))
    head = ['encoding utf-8', f'source {sv["source"]}', *[f'select {s}' for s in sv.get('select', [])]]
    tail = [*SHEET, *([f'input {os.path.relpath(os.path.join(reg, "common_layout.th"), d)}'] if common else [])]
    todo = [e for e in EXPORTS if drawn or not e[5]]
    # the models and lists in one run; each map in its own (where Therion can fail on a drawing)
    therion(d, head + [e[1].format(f=f'{rel}/{base}{e[0]}') for e in todo if e[1] and 'export map' not in e[1]] + tail)
    for e in todo:
        if e[1] and 'export map' in e[1]:
            therion(d, head + [e[1].format(f=f'{rel}/{base}{e[0]}')] + tail)
    if drawn:
        # (the plan Therion drew for the 3D view's drawn survey)
        src = cfg.at(cave['drawn']['svg']) if cave['drawn'].get('svg') else os.path.join(cfg.work_dir(cave), 'plan.svg')
        if os.path.exists(src):
            shutil.copy(src, os.path.join(dest, base + '-plan.svg'))
    made = []
    for suffix, export, title, blurb, kind, needs_drawing in todo:
        name = base + suffix
        if os.path.exists(os.path.join(dest, name)) and os.path.getsize(os.path.join(dest, name)):
            item = {'file': name, 'title': title, 'blurb': blurb, 'kind': kind, 'size': os.path.getsize(os.path.join(dest, name))}
            if name.endswith('.pdf') and preview(os.path.join(dest, name), os.path.join(dest, name[:-4] + '.png')):
                item['preview'] = name[:-4] + '.png'
            made.append(item)
        else:
            print(f'  {cave["name"]}: no {title} (Therion made none)', file=sys.stderr)
    top, kids = survey_list(os.path.join(dest, base + '-surveys.html')) if os.path.exists(os.path.join(dest, base + '-surveys.html')) else (None, [])
    json.dump({'_comment': 'Made by caveviewer (files step), for the landing page.', 'files': made, 'survey': top, 'surveys': kids},
              open(os.path.join(dest, 'files.json'), 'w'), indent=1, ensure_ascii=False)
    print(f'{cave["name"]}: {len(made)} files in {os.path.relpath(dest, out)}/', file=sys.stderr)
