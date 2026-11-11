"""Build a cave repo's site: each cave's 3D view, and a landing page for several.

    python -m caveviewer build caves.json --out site/            # every step, every cave
    python -m caveviewer build caves.json --out site/ gb         # some caves only, by id
    python -m caveviewer build caves.json --out site/ --steps model,drawn
    python -m caveviewer fit caves.json [cave]                   # fit a scanned drawing (drawn.type "scan")
    python -m caveviewer check caves.json                        # read the config, and say what it builds

The steps, in order:

    survey   each cave's centreline and names, in the work folder (Therion builds it, or a Survex .3d)
    model    each cave's 3D view in <out>/<path>/ (scene.json, terrain.bin, index.html, offline files)
    drawn    each cave's drawn survey, for its 2D plan, in <out>/<path>/drawn/
    files    for a cave with a page, what Therion makes of it to download, in <out>/<page>/files/
    index    each cave's landing page, <out>/<page>/index.html (where it has a page), and the site's,
             <out>/index.html (where site.index is on: by default, for several caves)

Set CHROMIUM to a Chrome or Chromium binary for each cave's preview.png
(and for Therion drawings, where Chrome isn't in the usual place on a Mac).
"""
import argparse
import os
import sys

from caveviewer import __version__
from caveviewer.config import Config, ConfigError

STEPS = ('survey', 'model', 'drawn', 'files', 'index')


def build(cfg, out, only=(), steps=STEPS, fetch=True, chromium=None):
    caves = [c for c in cfg.caves if not only or c['id'] in only]
    if only and len(caves) != len(set(only)):
        raise ConfigError(f'no cave {sorted(set(only) - {c["id"] for c in caves})} in {cfg.path}')
    from caveviewer import drawn, files, index, pages, scene, survey
    failed = []
    if 'survey' in steps:
        failed = [c['id'] for c in caves if not survey.build(cfg, c, fetch)]
    caves = [c for c in caves if c['id'] not in failed]
    if 'model' in steps:
        for c in caves:
            scene.build(cfg, c, os.path.join(out, c['path']), chromium)
    if 'drawn' in steps:
        for c in caves:
            if c['features']['drawn']:
                drawn.build(cfg, c, os.path.join(out, c['path']), chromium)
    if 'files' in steps:
        for c in caves:
            if c['features']['files']:
                files.build(cfg, c, out)
    if 'index' in steps:
        pages.build(cfg, cfg.caves, out)
    if 'index' in steps and cfg.site['index']:
        with open(os.path.join(out, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(index.page(cfg.site, cfg.caves, out))
        print(f'site written to {out}: {len(cfg.caves)} caves', file=sys.stderr)
    if failed:
        raise SystemExit(f'the survey failed to build for {", ".join(failed)}')


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m caveviewer', description=__doc__.split('\n')[0])
    ap.add_argument('--version', action='version', version=f'cave-viewer {__version__}')
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build', help="build the site")
    b.add_argument('config', help='the cave repo\'s config (JSON)')
    b.add_argument('caves', nargs='*', help='which caves (by id): all if none')
    b.add_argument('--out', default='site', help='where the site goes (default site/)')
    b.add_argument('--steps', default=','.join(STEPS), help=f'which steps, comma-separated (default {",".join(STEPS)})')
    b.add_argument('--no-fetch', action='store_true', help="don't bring a Subversion checkout up to date")
    f = sub.add_parser('fit', help='fit a scanned drawn survey to the survey')
    f.add_argument('config')
    f.add_argument('caves', nargs='*')
    c = sub.add_parser('check', help='read the config and say what it builds')
    c.add_argument('config')
    a = ap.parse_args(argv)
    try:
        cfg = Config(a.config)
        if a.cmd == 'build':
            steps = [s.strip() for s in a.steps.split(',') if s.strip()]
            bad = set(steps) - set(STEPS)
            if bad:
                ap.error(f'unknown steps {sorted(bad)}: they are {", ".join(STEPS)}')
            build(cfg, a.out, a.caves, steps, not a.no_fetch, os.environ.get('CHROMIUM'))
        elif a.cmd == 'fit':
            from caveviewer.drawn.scan_fit import fit
            for cave in cfg.caves:
                if (not a.caves or cave['id'] in a.caves) and cave['drawn']['type'] == 'scan':
                    fit(cfg, cave)
        else:
            for cave in cfg.caves:
                off = [k for k, v in cave['features'].items() if not v]
                print(f"{cave['id']}: {cave['name']} -> {cave['path']}/  survey {cave['survey']['type']}, "
                      f"terrain {cave['terrain']['type']}, drawn {cave['drawn']['type']}, walls {(cave['walls'].get('type') or 'lox') if cave['walls'] else 'none'}"
                      + (f"; off: {', '.join(off)}" if off else ''))
            print(f"index: {'yes' if cfg.site['index'] else 'no'}")
    except ConfigError as e:
        raise SystemExit(f'config: {e}')


if __name__ == '__main__':
    main()
