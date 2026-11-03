"""The ground over the cave: heights on a regular grid of the National Grid.

Each source has fetch(e0, n0, e1, n1, step, cache) -> (columns, rows,
heights): heights in centimetres as an array('H'), row by row from the
north-west corner, every step metres, 0 where there's none. What's fetched
is kept, averaged, in the cache folder (cache=None keeps nothing).

    ea      the Environment Agency's 1 m LiDAR composite DTM (England), by WCS
    wales   the Welsh Government's 1 m LiDAR DTM 2020-22, by its WFS tile catalogue
    flat    no LiDAR: a level ground just above the cave (for tests, or anywhere else)
"""
import array
import gzip
import os
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


def cached(cache, e0, n0, e1, n1, step, make):
    """The heights from the cache, made (make() -> array('H')) and kept the first time."""
    f = cache and os.path.join(cache, f'dtm-{e0}-{n0}-{e1}-{n1}-{step}m.u16.gz')
    if f and os.path.exists(f):
        raw = array.array('H', gzip.open(f).read())
        if sys.byteorder != 'little':
            raw.byteswap()
        return raw
    out = make()
    if f:
        keep = array.array('H', out)
        if sys.byteorder != 'little':
            keep.byteswap()
        os.makedirs(cache, exist_ok=True)
        with gzip.open(f, 'wb') as g:
            g.write(keep.tobytes())
    return out


def ground(kind, e0, n0, e1, n1, step, cache, level=None):
    """(columns, rows, heights) from the named source."""
    w, h = (e1 - e0) // step, (n1 - n0) // step
    if kind == 'flat':
        return w, h, array.array('H', [max(1, round(level * 100))] * (w * h))
    from importlib import import_module
    make = import_module(f'caveviewer.terrain.{kind}').fetch
    return w, h, cached(cache, e0, n0, e1, n1, step, lambda: make(e0, n0, e1, n1, step))
