"""Therion's GIS export (export map -fmt esri): the points layer, read
without a GIS library. Shapefile points and their dBASE records."""
import struct


def read_dbf(path):
    d = open(path, 'rb').read()
    n, head, size = struct.unpack('<IHH', d[4:12])
    fields, i = [], 32
    while d[i] != 0x0d:
        fields.append((d[i:i + 11].split(b'\0')[0].decode(), d[i + 16]))
        i += 32
    out = []
    for r in range(n):
        o, rec = head + r * size + 1, {}
        for name, length in fields:
            rec[name] = d[o:o + length].decode('utf-8', 'replace').strip()
            o += length
        out.append(rec)
    return out


def read_points(stem):
    """(x, y, record) for each point in stem.shp / stem.dbf."""
    d = open(stem + '.shp', 'rb').read()
    pts, i = [], 100
    while i < len(d):
        n = struct.unpack('>I', d[i + 4:i + 8])[0] * 2
        kind = struct.unpack('<i', d[i + 8:i + 12])[0]
        pts.append(struct.unpack('<2d', d[i + 12:i + 28]) if kind in (1, 11, 21) else None)
        i += 8 + n
    return [(p[0], p[1], r) for p, r in zip(pts, read_dbf(stem + '.dbf')) if p]


def read_lines(stem):
    """(points, record) for each line in stem.shp / stem.dbf: its first part's points."""
    d = open(stem + '.shp', 'rb').read()
    out, i = [], 100
    while i < len(d):
        n = struct.unpack('>I', d[i + 4:i + 8])[0] * 2
        kind = struct.unpack('<i', d[i + 8:i + 12])[0]
        pts = None
        if kind in (3, 13, 23):
            parts, count = struct.unpack('<2i', d[i + 44:i + 52])
            first = struct.unpack('<i', d[i + 52:i + 56])[0]
            end = struct.unpack('<i', d[i + 56:i + 60])[0] if parts > 1 else count
            o = i + 52 + 4 * parts
            pts = [struct.unpack('<2d', d[o + 16 * k:o + 16 * k + 16]) for k in range(first, end)]
        out.append(pts)
        i += 8 + n
    return [(p, r) for p, r in zip(out, read_dbf(stem + '.dbf')) if p]
