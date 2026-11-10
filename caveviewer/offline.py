"""What a cave's page needs to work with no signal."""
import hashlib
import json
import os
import shutil


def offline(out_dir, here, worker=True):
    """What the page needs to work with no signal: three.js and the font from
    vendor/ (rather than from the internet), the app's manifest and icons, and
    a service worker that keeps all of it, listed and versioned by content."""
    for d in ('vendor',):
        shutil.rmtree(os.path.join(out_dir, d), ignore_errors=True)
        shutil.copytree(os.path.join(here, d), os.path.join(out_dir, d))
    for f in os.listdir(os.path.join(here, 'static')):
        if f not in ('sw.js', 'manifest.webmanifest'):
            shutil.copy(os.path.join(here, 'static', f), os.path.join(out_dir, f))
    if not worker:
        # (no service worker: the page stays online only, and an old one's files go)
        for f in ('sw.js',):
            if os.path.exists(os.path.join(out_dir, f)):
                os.remove(os.path.join(out_dir, f))
        return
    files = ['./']
    for root, dirs, names in os.walk(out_dir):
        # (not another cave's page in a folder of this one's, as when a
        # whole area's page is the site's root and its caves are below it)
        dirs[:] = sorted(d for d in dirs if not os.path.exists(os.path.join(root, d, 'scene.json')))
        for n in sorted(names):
            # (not the drawn survey, where there is one: it's kept apart, as it's seen)
            if n in ('sw.js', 'preview.png', '.DS_Store') or n.endswith(('LICENSE', 'LICENSE.txt')) or os.path.relpath(root, out_dir).split(os.sep)[0] == 'drawn':
                continue
            files.append(os.path.relpath(os.path.join(root, n), out_dir).replace(os.sep, '/'))
    h = hashlib.sha256()
    for f in files[1:]:
        h.update(f.encode())
        h.update(open(os.path.join(out_dir, f), 'rb').read())
    sw = open(os.path.join(here, 'static', 'sw.js')).read()
    sw = sw.replace("'__VERSION__'", repr(h.hexdigest()[:12])).replace('__FILES__', json.dumps(files, indent=2))
    sw = sw.replace('__ID__', os.path.basename(os.path.normpath(out_dir)))    # (each cave's caches its own: the caves share a site)
    with open(os.path.join(out_dir, 'sw.js'), 'w') as f:
        f.write(sw)
