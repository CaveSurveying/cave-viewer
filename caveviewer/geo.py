"""The National Grid: to lat/long and Web Mercator (for the imagery), and
its grid references."""
import math


def grid_to_ll(e, n):
    """OSGB36 National Grid to WGS84 lat/long (degrees), by the Ordnance
    Survey's formulae and a Helmert shift: good to a few metres, and the
    caller corrects what is left with the entrance's OSTN15 position."""
    a, b, f0 = 6377563.396, 6356256.909, 0.9996012717
    lat0, lon0, e0, n0 = math.radians(49), math.radians(-2), 400000, -100000
    e2 = 1 - b * b / (a * a)
    nn = (a - b) / (a + b)
    lat, m = lat0, 0
    while abs(n - n0 - m) >= 1e-5:
        lat += (n - n0 - m) / (a * f0)
        m = b * f0 * ((1 + nn + 1.25 * nn ** 2 + 1.25 * nn ** 3) * (lat - lat0)
                      - (3 * nn + 3 * nn ** 2 + 21 / 8 * nn ** 3) * math.sin(lat - lat0) * math.cos(lat + lat0)
                      + (15 / 8 * nn ** 2 + 15 / 8 * nn ** 3) * math.sin(2 * (lat - lat0)) * math.cos(2 * (lat + lat0))
                      - 35 / 24 * nn ** 3 * math.sin(3 * (lat - lat0)) * math.cos(3 * (lat + lat0)))
    s, c, t = math.sin(lat), math.cos(lat), math.tan(lat)
    nu = a * f0 / math.sqrt(1 - e2 * s * s)
    rho = a * f0 * (1 - e2) / (1 - e2 * s * s) ** 1.5
    eta2 = nu / rho - 1
    de = e - e0
    lat = (lat - t / (2 * rho * nu) * de ** 2
           + t / (24 * rho * nu ** 3) * (5 + 3 * t * t + eta2 - 9 * t * t * eta2) * de ** 4
           - t / (720 * rho * nu ** 5) * (61 + 90 * t * t + 45 * t ** 4) * de ** 6)
    lon = (lon0 + de / (c * nu)
           - de ** 3 / (6 * c * nu ** 3) * (nu / rho + 2 * t * t)
           + de ** 5 / (120 * c * nu ** 5) * (5 + 28 * t * t + 24 * t ** 4)
           - de ** 7 / (5040 * c * nu ** 7) * (61 + 662 * t * t + 1320 * t ** 4 + 720 * t ** 6))
    # Airy 1830 to GRS80 through Cartesian coordinates
    s, c = math.sin(lat), math.cos(lat)
    nu = a / math.sqrt(1 - e2 * s * s)
    x, y, z = nu * c * math.cos(lon), nu * c * math.sin(lon), nu * (1 - e2) * s
    tx, ty, tz, sc = 446.448, -125.157, 542.060, -20.4894e-6
    rx, ry, rz = (math.radians(v / 3600) for v in (0.1502, 0.2470, 0.8421))
    x, y, z = (tx + (1 + sc) * x - rz * y + ry * z,
               ty + rz * x + (1 + sc) * y - rx * z,
               tz - ry * x + rx * y + (1 + sc) * z)
    a2, b2 = 6378137.0, 6356752.3141
    e2 = 1 - b2 * b2 / (a2 * a2)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - e2))
    for _ in range(10):
        lat = math.atan2(z + e2 * a2 / math.sqrt(1 - e2 * math.sin(lat) ** 2) * math.sin(lat), p)
    return math.degrees(lat), math.degrees(math.atan2(y, x))


def mercator(lat, lon):
    """Web Mercator, as a fraction of the world (0..1 across and down)."""
    s = math.sin(math.radians(lat))
    return (lon + 180) / 360, 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)


def fit_affine(pairs):
    """Least-squares (u, v) = A (1, x, y) over (x, y) -> (u, v) pairs."""
    m = [[0.0] * 3 for _ in range(3)]
    ru, rv = [0.0] * 3, [0.0] * 3
    for (x, y), (u, v) in pairs:
        r = (1.0, x, y)
        for i in range(3):
            ru[i] += r[i] * u
            rv[i] += r[i] * v
            for j in range(3):
                m[i][j] += r[i] * r[j]

    def solve(rhs):
        a = [row[:] + [rhs[i]] for i, row in enumerate(m)]
        for i in range(3):
            p = max(range(i, 3), key=lambda k: abs(a[k][i]))
            a[i], a[p] = a[p], a[i]
            for k in range(3):
                if k != i:
                    f = a[k][i] / a[i][i]
                    a[k] = [x - f * y for x, y in zip(a[k], a[i])]
        return [a[i][3] / a[i][i] for i in range(3)]
    return solve(ru) + solve(rv)


def grid_ref(e, n):
    """A National Grid reference with its letters, to the metre: SN 86357 15878."""
    e1, n1 = int(e // 100000), int(n // 100000)
    l1 = (19 - n1) - (19 - n1) % 5 + (e1 + 10) // 5
    l2 = (19 - n1) * 5 % 25 + e1 % 5
    letter = lambda i: chr(ord('A') + i + (i > 7))      # no I
    e, n = round(e), round(n)
    return f'{letter(l1)}{letter(l2)} {e % 100000:05d} {n % 100000:05d}'
