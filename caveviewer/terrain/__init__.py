"""The ground over the cave: heights on a regular grid of the National Grid.

Each source has fetch(e0, n0, e1, n1, step) -> heights in metres, an
array('d') row by row from the north-west corner, every step metres, NaN
where there's none. ground() gives them as centimetres above a base height,
an array('H') with 0 where there's none: the base is 0 (the heights as
they are) wherever the ground fits in 16 bits, up to 655.34 m, and
otherwise a whole metre under its lowest point, so higher ground (the
Pennines, Snowdonia) fits as long as it rises less than that within the
model. What's fetched is kept, averaged and so encoded, in the cache folder
(cache=None keeps nothing).

    ea      the Environment Agency's 1 m LiDAR composite DTM (England), by WCS
    wales   the Welsh Government's 1 m LiDAR DTM 2020-22, by its WFS tile catalogue
    flat    no LiDAR: a level ground just above the cave (for tests, or anywhere else)
"""
import array
import glob
import gzip
import math
import os
import re
import sys
import urllib.request

UA = 'cave-viewer 3D view'

# the ground's credit on the page, by source
CREDITS = {
    'ea': 'Ground: Environment Agency LiDAR Composite DTM, &copy; Environment Agency, '
          '<a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/">OGL&nbsp;v3</a> &middot;',
    'wales': 'Ground: Welsh Government LiDAR 2020&ndash;22 DTM, &copy; Welsh Government, '
             '<a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/">OGL&nbsp;v3</a> &middot;',
    'flat': '',
}


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    return urllib.request.urlopen(req, timeout=180).read()


def encode(metres):
    """(centimetres above the base as an array('H'), 0 where there's none; the base in metres)."""
    have = [m for m in metres if m == m]
    lo, hi = (min(have), max(have)) if have else (1, 1)
    base = 0 if lo > 0 and hi < 655.34 else math.floor(lo) - 1
    if hi - base >= 655.34:
        raise ValueError(f'the ground rises {hi - lo:.0f} m, from {lo:.0f} to {hi:.0f} m: '
                         'more than the 655 m it can rise within one model (a smaller margin, or the cave in parts)')
    return array.array('H', (max(1, round((m - base) * 100)) if m == m else 0 for m in metres)), base


def cached(cache, e0, n0, e1, n1, step, make):
    """(heights, base) from the cache, made (make() -> metres) and kept the first time. A cache
    file's name gives its base, after -base; one without (all from before bases) has base 0."""
    stem = cache and os.path.join(cache, f'dtm-{e0}-{n0}-{e1}-{n1}-{step}m')
    found = stem and ([stem + '.u16.gz'] if os.path.exists(stem + '.u16.gz') else glob.glob(glob.escape(stem) + '-base*.u16.gz'))
    if found:
        raw = array.array('H', gzip.open(found[0]).read())
        if sys.byteorder != 'little':
            raw.byteswap()
        m = re.search(r'-base(-?\d+)\.u16\.gz$', found[0])
        return raw, int(m.group(1)) if m else 0
    out, base = encode(make())
    if stem:
        keep = array.array('H', out)
        if sys.byteorder != 'little':
            keep.byteswap()
        os.makedirs(cache, exist_ok=True)
        with gzip.open(stem + (f'-base{base}' if base else '') + '.u16.gz', 'wb') as g:
            g.write(keep.tobytes())
    return out, base


def ground(kind, e0, n0, e1, n1, step, cache, level=None):
    """(columns, rows, heights, base) from the named source: heights in centimetres above base (metres)."""
    w, h = (e1 - e0) // step, (n1 - n0) // step
    if kind == 'flat':
        return (w, h, *encode([level] * (w * h)))
    from importlib import import_module
    make = import_module(f'caveviewer.terrain.{kind}').fetch
    return (w, h, *cached(cache, e0, n0, e1, n1, step, lambda: make(e0, n0, e1, n1, step)))
