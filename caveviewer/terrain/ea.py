"""The Environment Agency's 1 m LiDAR composite terrain model (England),
fetched as one GeoTIFF by WCS."""
import array
import math
import sys

from caveviewer.formats import read_tiff
from caveviewer.terrain import get

WCS = ('https://environment.data.gov.uk/spatialdata/lidar-composite-digital-terrain-model-dtm-1m/wcs'
       '?service=WCS&version=2.0.1&request=GetCoverage'
       '&coverageId=13787b9a-26a4-4775-8523-806d13af58fc__Lidar_Composite_Elevation_DTM_1m'
       '&subset=E({e0},{e1})&subset=N({n0},{n1})&format=image/tiff')


def fetch(e0, n0, e1, n1, step):
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
