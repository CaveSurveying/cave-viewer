"""The Copernicus 30 m DEM (GLO-30), for ground where there's no LiDAR: Ireland,
say. It covers the world in 1 degree tiles on lat/long, from the public copy on
AWS (Copernicus_DSM_COG_10_N52_00_W010_00_DEM.tif): each sample of the model's
grid is put into lat/long and read off the tiles between their points.

A surface model, not a terrain model: its heights include trees and buildings
(little of either on the Burren), on the EGM2008 geoid, which is close to the
Irish and British height datums. The tiles are 32-bit floats, deflated with the
floating-point predictor, in 1024 x 1024 tiles, and point-registered: the tie
point is the centre of the first pixel. North of 50 degrees a pixel is 1.5 by 1
arcseconds.
"""
import math
import struct
import sys
import zlib

import numpy as np

from caveviewer.geo import TO_LL
from caveviewer.terrain import get

URL = ('https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{lat}_00_{lon}_00_DEM/'
       'Copernicus_DSM_COG_10_{lat}_00_{lon}_00_DEM.tif')


def tile_name(lat, lon):
    """The tile with this south-west corner (whole degrees): (N52, W010)."""
    return (f'N{lat:02d}' if lat >= 0 else f'S{-lat:02d}'), (f'E{lon:03d}' if lon >= 0 else f'W{-lon:03d}')


def read(data):
    """A GLO-30 tile: (heights as a 2D float32 array, from the north-west, the first
    pixel's centre (lon, lat), and a pixel's size (lon, lat) in degrees)."""
    end = '<' if data[:2] == b'II' else '>'
    off = struct.unpack_from(end + 'I', data, 4)[0]
    sizes = {3: 2, 4: 4, 12: 8, 16: 8}
    fmts = {3: 'H', 4: 'I', 12: 'd', 16: 'Q'}
    tags = {}
    for k in range(struct.unpack_from(end + 'H', data, off)[0]):
        tag, typ, cnt, val = struct.unpack_from(end + 'HHI4s', data, off + 2 + 12 * k)
        if typ in fmts:
            n = sizes[typ] * cnt
            src = val if n <= 4 else data[struct.unpack(end + 'I', val)[0]:][:n]
            tags[tag] = struct.unpack_from(end + fmts[typ] * cnt, src)
    w, h, tw, th = tags[256][0], tags[257][0], tags[322][0], tags[323][0]
    if tags.get(259, (1,))[0] != 8 or tags.get(339, (3,))[0] != 3 or tags.get(258, (32,))[0] != 32:
        raise ValueError('expected a deflated float32 GeoTIFF')
    predictor = tags.get(317, (1,))[0]
    out = np.zeros((h, w), np.float32)
    across = (w + tw - 1) // tw
    for t, (o, c) in enumerate(zip(tags[324], tags[325])):
        raw = np.frombuffer(zlib.decompress(data[o:o + c]), np.uint8)
        if predictor == 3:
            # the floating-point predictor: each row's bytes, most significant of
            # every sample first, then the next byte of every sample, and so on,
            # each byte stored as its difference from the one before
            rows = np.cumsum(raw.reshape(th, 4 * tw), axis=1, dtype=np.uint8)
            vals = rows.reshape(th, 4, tw).transpose(0, 2, 1).copy().view('>f4').reshape(th, tw)
        elif predictor == 1:
            vals = raw.view(end + 'f4').reshape(th, tw)
        else:
            raise ValueError(f'unexpected TIFF predictor {predictor}')
        y, x = (t // across) * th, (t % across) * tw
        out[y:y + th, x:x + tw][:min(th, h - y), :min(tw, w - x)] = vals[:min(th, h - y), :min(tw, w - x)]
    sx, sy = tags[33550][0], tags[33550][1]
    return out, (tags[33922][3], tags[33922][4]), (sx, sy)


def fetch(e0, n0, e1, n1, step, crs='osgb'):
    to_ll = TO_LL[crs]
    w, h = (e1 - e0) // step, (n1 - n0) // step
    # each sample's lat/long (at its cell's middle, as the LiDAR sources average theirs)
    lat = np.empty(w * h); lon = np.empty(w * h)
    for j in range(h):
        y = n1 - (j + 0.5) * step
        for i in range(w):
            lat[j * w + i], lon[j * w + i] = to_ll(e0 + (i + 0.5) * step, y)
    out = np.full(w * h, np.nan)
    for la, lo in sorted({(math.floor(a), math.floor(b)) for a, b in zip(lat, lon)}):
        ns, ew = tile_name(la, lo)
        print(f'fetching the Copernicus 30 m DEM tile {ns}{ew}', file=sys.stderr)
        try:
            z, (x0, y0), (sx, sy) = read(get(URL.format(lat=ns, lon=ew)))
        except Exception as err:          # (a tile of sea isn't there)
            print(f'  none: {err}', file=sys.stderr)
            continue
        inside = (np.floor(lat) == la) & (np.floor(lon) == lo)
        c = (lon[inside] - x0) / sx
        r = (y0 - lat[inside]) / sy
        c0 = np.clip(np.floor(c).astype(int), 0, z.shape[1] - 2); r0 = np.clip(np.floor(r).astype(int), 0, z.shape[0] - 2)
        fc, fr = c - c0, r - r0
        v = (z[r0, c0] * (1 - fc) * (1 - fr) + z[r0, c0 + 1] * fc * (1 - fr)
             + z[r0 + 1, c0] * (1 - fc) * fr + z[r0 + 1, c0 + 1] * fc * fr)
        out[inside] = np.where(v > -1000, v, np.nan)
    import array
    return array.array('d', out.tolist())
