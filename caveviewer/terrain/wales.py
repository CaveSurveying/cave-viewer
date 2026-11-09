"""The Welsh Government's 1 m LiDAR terrain model (2020-22), fetched 1 km
tile by tile: its WFS catalogue gives each tile's GeoTIFF."""
import array
import json
import math
import sys
import urllib.parse

from caveviewer.formats import read_tiff
from caveviewer.terrain import get

WFS = ('https://datamap.gov.wales/geoserver/ows?service=WFS&version=2.0.0&request=GetFeature'
       '&typeNames=geonode:welsh_government_lidar_tile_catalogue_2020_2023&outputFormat=application/json'
       '&bbox={e0},{n0},{e1},{n1},EPSG:27700')


def fetch(e0, n0, e1, n1, step):
    w, h = (e1 - e0) // step, (n1 - n0) // step
    total, count = array.array('d', bytes(8 * w * h)), array.array('H', bytes(2 * w * h))
    tiles = json.loads(get(WFS.format(e0=e0, n0=n0, e1=e1, n1=n1)))['features']
    for k, t in enumerate(tiles):
        link = t['properties']['dtm_link']
        url = link if link.startswith('http') else 'https://' + urllib.parse.quote(link)
        print(f'fetching LiDAR tile {t["properties"]["british_gr"]} ({k + 1} of {len(tiles)})', file=sys.stderr)
        tw, th, v, (x0, y0), px = read_tiff(get(url))
        if px != 1.0:
            raise ValueError(f'unexpected LiDAR pixel size {px} m in {url}')
        x0, y0 = round(x0), round(y0)
        for r in range(th):
            j = (n1 - (y0 - r)) // step        # the model row this LiDAR row falls in
            if not 0 <= j < h:
                continue
            row = r * tw
            for c in range(tw):
                i = (x0 + c - e0) // step
                z = v[row + c]
                if 0 <= i < w and z > -1000:
                    total[j * w + i] += z
                    count[j * w + i] += 1
    return array.array('d', (t / n if n else math.nan for t, n in zip(total, count)))
