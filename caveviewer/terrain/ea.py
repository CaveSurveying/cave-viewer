"""The Environment Agency's 1 m LiDAR composite terrain model (England),
fetched by WCS: as one GeoTIFF, or a piece at a time for an area bigger
than the service will send at once (a whole catchment, say)."""
import array
import math
import sys

from caveviewer.formats import read_tiff
from caveviewer.terrain import get

WCS = ('https://environment.data.gov.uk/spatialdata/lidar-composite-digital-terrain-model-dtm-1m/wcs'
       '?service=WCS&version=2.0.1&request=GetCoverage'
       '&coverageId=13787b9a-26a4-4775-8523-806d13af58fc__Lidar_Composite_Elevation_DTM_1m'
       '&subset=E({e0},{e1})&subset=N({n0},{n1})&format=image/tiff')


PIECE = 1000      # metres: an area wider or taller than this is fetched in pieces this size


def fetch(e0, n0, e1, n1, step):
    if e1 - e0 > PIECE or n1 - n0 > PIECE:
        return pieces(e0, n0, e1, n1, step)
    w, h = (e1 - e0) // step, (n1 - n0) // step
    print(f'fetching LiDAR for {e0},{n0} to {e1},{n1}', file=sys.stderr)
    tw, th, v, (x0, y0), px = read_tiff(get(WCS.format(e0=e0, e1=e1, n0=n0, n1=n1)))
    if (tw, th, round(x0), round(y0), px) != (e1 - e0, n1 - n0, e0, n1, 1.0):
        raise ValueError(f'unexpected LiDAR grid {tw}x{th} at {x0},{y0} ({px} m)')
    out = array.array('d')
    for j in range(h):
        for i in range(w):
            s = [v[(j * step + b) * tw + i * step + a] for b in range(step) for a in range(step)]
            s = [x for x in s if x > -1000]
            out.append(sum(s) / len(s) if s else math.nan)
    return out


COARSE = 4        # metres: a step this coarse or coarser is sampled by the service itself (scaleFactor), not averaged here
COARSE_PIECE = 2000


def pieces(e0, n0, e1, n1, step):
    """The same, a piece at a time (each a whole number of steps). At a
    COARSE step the service samples the LiDAR down itself, a few km at a
    time (fast); finer, each PIECE comes at 1 m and is averaged here, with
    numpy, as there are millions of samples (slow: about a minute a km)."""
    import numpy as np
    w, h = (e1 - e0) // step, (n1 - n0) // step
    coarse = step >= COARSE
    size = (COARSE_PIECE if coarse else PIECE) // step * step
    total, count = np.zeros((h, w)), np.zeros((h, w))
    for pe in range(e0, e1, size):
        for pn in range(n0, n1, size):
            qe, qn = min(pe + size, e1), min(pn + size, n1)
            print(f'fetching LiDAR for {pe},{pn} to {qe},{qn}', file=sys.stderr)
            for attempt in range(3):            # (the service is slow, and now and then gives up)
                try:
                    data = get(WCS.format(e0=pe, e1=qe, n0=pn, n1=qn) + (f'&scaleFactor={1 / step}' if coarse else ''))
                    break
                except OSError as e:
                    if attempt == 2:
                        raise
                    print(f'  retrying ({e})', file=sys.stderr)
            tw, th, v, (x0, y0), px = read_tiff(data)
            k = step if coarse else 1
            if (tw * k, th * k, round(x0), round(y0), round(px, 3)) != (qe - pe, qn - pn, pe, qn, float(k)):
                raise ValueError(f'unexpected LiDAR grid {tw}x{th} at {x0},{y0} ({px} m)')
            a = np.array(v, dtype=float).reshape(th, tw)
            ok = a > -1000
            # this piece's place in the model: columns from pe, rows down from n1
            i0, j0 = (pe - e0) // step, (n1 - qn) // step
            if coarse:
                total[j0:j0 + th, i0:i0 + tw] += np.where(ok, a, 0)
                count[j0:j0 + th, i0:i0 + tw] += ok
                continue
            pw, ph = tw // step, th // step
            a = np.where(ok, a, 0)[:ph * step, :pw * step].reshape(ph, step, pw, step).sum((1, 3))
            c = ok[:ph * step, :pw * step].reshape(ph, step, pw, step).sum((1, 3))
            total[j0:j0 + ph, i0:i0 + pw] += a
            count[j0:j0 + ph, i0:i0 + pw] += c
    mean = np.where(count > 0, total / np.maximum(count, 1), np.nan)      # (metres, NaN where there's none)
    return array.array('d', mean.ravel().tolist())
