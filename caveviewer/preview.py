"""A still of a cave's 3D view (preview.png), by headless Chrome."""
import os
import re
import struct
import subprocess
import sys
import zlib


def preview(chromium, out_dir, port=8765, size=(1200, 750)):
    """A still of the view for the index page, by headless Chrome."""
    import functools
    import http.server
    import threading

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', port), functools.partial(Quiet, directory=out_dir))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    png = os.path.abspath(os.path.join(out_dir, 'preview.png'))
    chrome = [chromium, '--headless=new', '--no-sandbox', '--hide-scrollbars', f'--window-size={size[0]},{size[1]}']
    try:
        # Headless Chrome's screenshot is the whole window, which is taller
        # than the page by a toolbar's height: find out by how much, to crop.
        r = subprocess.run(chrome + ['--dump-dom', 'data:text/html,<script>document.write(innerHeight)</script>'],
                           capture_output=True, text=True, timeout=60)
        m = re.search(r'<body>(\d+)', r.stdout)
        # Now and then Chrome takes the shot before three.js has arrived from
        # the CDN, leaving only the loading screen (a small, plain PNG): retry.
        for _ in range(3):
            subprocess.run(chrome + ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
                                     '--virtual-time-budget=30000', f'--screenshot={png}',
                                     f'http://127.0.0.1:{port}/index.html?still'],
                           check=True, timeout=180, capture_output=True)
            if os.path.getsize(png) > 300_000:
                break
        else:
            print('the preview only shows the loading screen', file=sys.stderr)
        if m:
            crop_png(png, int(m.group(1)))
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        print(f'no preview: {e}', file=sys.stderr)
    finally:
        srv.shutdown()


def crop_png(path, height):
    """Keep the top rows of an 8-bit PNG. Each row's filter refers only to
    the row above, so the rows can be cut without decoding them."""
    d = open(path, 'rb').read()
    i, chunks = 8, []
    while i < len(d):
        n = struct.unpack('>I', d[i:i + 4])[0]
        chunks.append((d[i + 4:i + 8], d[i + 8:i + 8 + n]))
        i += 12 + n
    ihdr = chunks[0][1]
    w, h, depth, colour = struct.unpack('>IIBB', ihdr[:10])
    if height >= h or depth != 8 or ihdr[12] != 0:
        return
    row = 1 + w * {0: 1, 2: 3, 4: 2, 6: 4}[colour]
    pixels = zlib.decompress(b''.join(c for t, c in chunks if t == b'IDAT'))[:row * height]

    def chunk(t, c):
        return struct.pack('>I', len(c)) + t + c + struct.pack('>I', zlib.crc32(t + c))
    out = d[:8] + chunk(b'IHDR', ihdr[:4] + struct.pack('>I', height) + ihdr[8:])
    out += b''.join(chunk(t, c) for t, c in chunks[1:] if t not in (b'IDAT', b'IEND'))
    out += chunk(b'IDAT', zlib.compress(pixels, 9)) + chunk(b'IEND', b'')
    open(path, 'wb').write(out)
