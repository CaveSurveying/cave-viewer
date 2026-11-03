"""The drawn survey, for the 3D view's 2D plan: map tiles of the cave's own
drawing, north up, in the scene's metres.

    therion-svg  the plan Therion draws from the survey (caveviewer.drawn.therion_svg)
    scan         a scanned or exported drawing, fitted to the survey
                 (caveviewer.drawn.scan; fitted by `python -m caveviewer fit`)
    none         no drawn survey

What this makes goes only into the built site:

drawn/meta.json  where the tiles and the paper's corners are, in the scene's metres
drawn/0/I_J.webp the drawing at LEVEL0 m a pixel, in tiles of TILE pixels; always loaded
drawn/1/I_J.webp the same at LEVEL1 m a pixel, for close up
"""
import numpy as np

TILE = 1024
LEVEL0, LEVEL1 = 0.5, 0.125     # metres a pixel


def blank(t):
    """No ink at all (a tile with only a few words on it, a grid label or
    a corner of the title block, is kept)."""
    return int((np.asarray(t).min(axis=2) < 200).sum()) < 12


def build(cfg, cave, site_dir, chromium=None):
    kind = cave['drawn']['type']
    if kind == 'therion-svg':
        from caveviewer.drawn import therion_svg
        therion_svg.build(cfg, cave, site_dir, chromium)
    elif kind == 'scan':
        from caveviewer.drawn import scan
        scan.build(cfg, cave, site_dir)
