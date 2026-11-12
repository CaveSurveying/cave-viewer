"""A cave's landing page (where it has a page): <out>/<page>/index.html, as
the Swildons survey's homepage is. The cave's figures, its 3D view, the
sheets to print (with pictures of them), the caves with pages of their own
below it, its surveys by length (each a link into the 3D view, #at=), and
its files to download, from the files step's files.json. The 3D view's
"About" goes up to it, so a cave's 3D view goes in a folder of its page
(path "<page>/3d").
"""
import html
import json
import os
import time

from caveviewer.terrain import CREDITS

E = html.escape


def human(n):
    for unit in ('B', 'kB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024.0


def inside(page, other):
    """Whether page other is in a folder below page."""
    a, b = os.path.normpath(page), os.path.normpath(other)
    return a != b and (a == '.' or b.startswith(a + os.sep))


def children(cave, caves):
    """The caves with pages directly below this one's (none between)."""
    mine = [c for c in caves if c.get('page') and inside(cave['page'], c['page'])]
    return [c for c in mine if not any(inside(o['page'], c['page']) for o in mine if o is not c)]


def scene(out, cave):
    p = os.path.join(out, cave['path'], 'scene.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def card(href, img, title, sub, nums):
    pic = f'<img src="{img}" alt="" loading="lazy">' if img else '<div class="noimg"></div>'
    return f'''<a class="card" href="{href}">{pic}<div class="txt">
  <h3>{title}</h3>{f'<p class="sub">{sub}</p>' if sub else ''}{f'<p class="nums">{nums}</p>' if nums else ''}
</div></a>'''


def page(cfg, cave, caves, out):
    here = os.path.join(out, cave['page'])
    to = lambda p: os.path.relpath(os.path.join(out, p), here).replace(os.sep, '/')
    three = to(cave['path'])
    s = scene(out, cave) or {}
    st = s.get('stats', {})
    fj = os.path.join(here, 'files', 'files.json')
    fs = json.load(open(fj, encoding='utf-8')) if os.path.exists(fj) else {'files': [], 'survey': None, 'surveys': []}
    top = fs.get('survey') or {}
    nums = [('Surveyed length', f"{st['length'] / 1000:.2f} km" if 'length' in st else None),
            ('Depth', f"{st['depth']} m" if 'depth' in st else None),
            ('Stations', f"{top['stations']:,}" if top.get('stations') else None),
            ('Survey legs', f"{top['shots']:,}" if top.get('shots') else None),
            ('Splay shots', f"{len(s['splays']) // 6:,}" if s.get('splays') else None),
            ('Grid reference', s.get('grid_ref')),
            ('Built', time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime()))]
    sha, repo = os.environ.get('GITHUB_SHA'), os.environ.get('GITHUB_REPOSITORY')
    if sha and repo:
        nums.append(('Commit', f'<a href="https://github.com/{E(repo)}/commit/{E(sha)}"><code>{E(sha[:7])}</code></a>'))
    stats = ''.join(f'<div><span>{k}</span><b>{v}</b></div>' for k, v in nums if v)

    parts = []
    # the 3D view
    pre = f'{three}/preview.png' if os.path.exists(os.path.join(out, cave['path'], 'preview.png')) else None
    links = [f'<a class="btn" href="{three}/">Open the 3D view</a>']
    if cave['drawn']['type'] != 'none' and cave['features']['drawn']:
        links.append(f'<a class="btn" href="{three}/#plan=1">The drawn survey</a>')
    if cave['terrain']['type'] == 'flat':
        ground = 'Every surveyed passage, coloured by altitude, with the ground as a level plane above it.'
    else:
        ground = ('Every surveyed passage, coloured by altitude, set beneath '
                  + ('a LiDAR model' if cave['terrain']['type'] in ('ea', 'wales') else 'a model') + ' of the ground with satellite imagery on it, so you can see what is on the surface above each passage.')
    parts.append(f'''<section><h2>3D view</h2>
<div class="feature">{f'<a href="{three}/"><img src="{pre}" alt="{E(cave["name"])} in 3D"></a>' if pre else ''}
<div><h3>Explore {E(cave.get('short_name') or cave['name'])} in 3D</h3>
<p>{ground}{' Passage walls come from the survey drawings.' if cave['walls'] else ''}{' Pick two places in the cave to see the way between them.' if cave['features']['routes'] else ''}</p>
<p class="note">Drag to turn it, scroll or pinch to zoom. Once opened it works offline. It also works in AR on an iPhone or iPad, and in AR or VR on any device whose browser supports WebXR, such as an Android phone or a headset.</p>
<p>{' '.join(links)}</p></div></div></section>''')
    # the cave's own notes (the config's about: Markdown)
    if cave.get('about'):
        from caveviewer.markdown import to_html
        doc = open(cfg.at(cave['about']), encoding='utf-8').read()
        parts.append(f'<section class="about"><h2>About</h2>{to_html(doc, top=3)}</section>')
    # sheets
    sheets = [f for f in fs['files'] if f['kind'] == 'sheet']
    if sheets:
        cards = [card(f"files/{f['file']}", f"files/{f['preview']}" if f.get('preview') else None, E(f['title']), E(f['blurb']), f"PDF &middot; {human(f['size'])}") for f in sheets]
        parts.append(f'<section><h2>Sheets</h2><div class="grid sheets">{"".join(cards)}</div></section>')
    # caves with their own pages
    kids = sorted(children(cave, caves), key=lambda c: -((scene(out, c) or {}).get('stats', {}).get('length', 0)))
    if kids:
        cards = []
        for c in kids:
            k = scene(out, c) or {}
            ks = k.get('stats', {})
            img = f"{to(c['path'])}/preview.png" if os.path.exists(os.path.join(out, c['path'], 'preview.png')) else None
            cards.append(card(f"{to(c['page'])}/", img, E(c['name']), f"{E(c['area'])}{' &middot; ' + k['grid_ref'] if k.get('grid_ref') else ''}",
                              f"<b>{ks.get('length', 0) / 1000:.1f} km</b> surveyed &middot; <b>{ks.get('depth', 0)} m</b> deep" if ks else ''))
        parts.append(f'<section><h2>Caves</h2><p class="note">Each with its own page: its 3D view, sheets and files.</p><div class="grid">{"".join(cards)}</div></section>')
    # its surveys by length
    if fs.get('surveys'):
        titles = cave.get('titles', {})
        own = {c['survey'].get('dir', '').split('/')[0]: c for c in kids}
        rows = []
        for r in fs['surveys']:
            if not r['length']:
                continue
            name = E(titles.get(r['id'], r['title']))
            pg = own.get(r['id'])
            rows.append(f'''<tr><td>{f'<a href="{to(pg["page"])}/"><b>{name}</b></a>' if pg else name}</td><td class="n">{r['length']:,} m</td><td class="n">{r['depth']} m</td><td><a href="{three}/#at={E(r['id'])}">In 3D</a></td></tr>''')
        parts.append(f'''<section><h2>Surveys</h2><p class="note">By surveyed length (Therion&rsquo;s figures).{' <b>Bold</b>: a page of its own.' if own else ''}</p>
<div class="scroll"><table><thead><tr><th>Survey</th><th class="n">Length</th><th class="n">Depth</th><th></th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>''')
    # files
    data = [f for f in fs['files'] if f['kind'] != 'sheet']
    if data:
        rows = ''.join(f'<tr><td><a href="files/{E(f["file"])}">{E(f["title"])}</a></td><td>{E(f["blurb"])}</td><td class="n">{human(f["size"])}</td></tr>' for f in data)
        parts.append(f'<section><h2>Models and data</h2><div class="scroll"><table><thead><tr><th>File</th><th>What it is</th><th class="n">Size</th></tr></thead><tbody>{rows}</tbody></table></div></section>')

    src = cave.get('data', {})
    source = f' &middot; Data: <a href="{E(src["url"])}">{E(src.get("label", src["url"]))}</a>' if src.get('url') else ''
    up = ''
    parents = [c for c in caves if c.get('page') and inside(c['page'], cave['page'])]
    if parents:
        p = max(parents, key=lambda c: len(os.path.normpath(c['page'])))
        up = f'<a class="up" href="{to(p["page"])}/">&larr; {E(p["name"])}</a>'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(cave['name'])}: cave survey</title>
<meta name="description" content="{E(cave['name'])}, {E(cave['area'])}: the survey in 3D, the sheets to print and the data to download.">
<link rel="stylesheet" href="{three}/vendor/inter/inter.css">
<style>
  :root {{ --bg: #05070c; --card: #0e131d; --text: #e9eef6; --muted: #8d99ab; --line: rgba(255,255,255,.08); --accent: #ffd27a; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 Inter, system-ui, sans-serif; }}
  main {{ max-width: 1120px; margin: 0 auto; padding: 40px 16px 32px; }}
  a {{ color: var(--accent); }}
  .up {{ display: inline-block; margin-bottom: 14px; color: var(--muted); text-decoration: none; font-size: 13px; }}
  h1 {{ margin: 0 0 4px; font-size: 32px; letter-spacing: -.02em; }}
  .lede {{ margin: 0 0 24px; color: var(--muted); max-width: 720px; }}
  .notice {{ margin: -8px 0 24px; padding: 10px 14px; max-width: 720px; border-left: 3px solid #e0a83a; background: rgba(224, 168, 58, .1); border-radius: 4px; }}
  .about {{ max-width: 720px; }}
  .about p, .about li {{ line-height: 1.55; }}
  .about blockquote {{ margin: 0 0 0 4px; padding-left: 14px; border-left: 2px solid var(--line); color: var(--muted); }}
  .stats {{ display: flex; flex-wrap: wrap; gap: 14px 32px; padding: 16px 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }}
  .stats span {{ display: block; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }}
  .stats b {{ font-weight: 600; }}
  section {{ margin-top: 36px; }}
  h2 {{ margin: 0 0 12px; font-size: 12px; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }}
  .note {{ margin: -6px 0 12px; color: var(--muted); font-size: 13px; }}
  .feature {{ display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 20px; align-items: center; background: var(--card); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }}
  .feature img {{ display: block; width: 100%; aspect-ratio: 16 / 10; object-fit: cover; }}
  .feature > div {{ padding: 16px 20px 16px 0; }}
  .feature h3 {{ margin: 0 0 6px; font-size: 20px; }}
  .feature p {{ margin: 0 0 12px; color: var(--muted); }}
  .btn {{ display: inline-block; margin: 0 6px 6px 0; padding: 8px 14px; border-radius: 999px; background: var(--accent); color: #1a1408; font-weight: 600; text-decoration: none; font-size: 14px; }}
  .btn + .btn {{ background: transparent; color: var(--accent); border: 1px solid rgba(255,210,122,.5); }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
  .card {{ display: block; background: var(--card); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; color: inherit; text-decoration: none; transition: border-color .15s, transform .15s; }}
  .card:hover {{ border-color: rgba(255,210,122,.5); transform: translateY(-2px); }}
  .card img, .noimg {{ display: block; width: 100%; aspect-ratio: 16 / 10; object-fit: cover; background: #0a0e16; }}
  .sheets .card img {{ object-fit: contain; background: #e8eaec; }}
  .txt {{ padding: 12px 16px 14px; }}
  h3 {{ margin: 0; font-size: 17px; }}
  .sub {{ margin: 4px 0 6px; color: var(--muted); font-size: 13px; }}
  .nums {{ margin: 0; font-size: 13px; color: var(--muted); }}
  .nums b {{ color: var(--text); font-weight: 600; }}
  .scroll {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
  th {{ font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 500; }}
  td a {{ text-decoration: none; }}
  .n {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }}
  footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--line); color: var(--muted); font-size: 12px; }}
  footer a {{ color: var(--muted); }}
  @media (max-width: 720px) {{ .feature {{ grid-template-columns: 1fr; }} .feature > div {{ padding: 0 16px 16px; }} }}
</style></head><body><main>
{up}
<h1>{E(cave['name'])}</h1>
<p class="lede">{E(cave['area'])}{' &middot; ' + cave['lede'] if cave.get('lede') else ''}</p>
{f'<p class="notice">{cave["notice"]}</p>' if cave.get('notice') else ''}
<div class="stats">{stats}</div>
{chr(10).join(parts)}
<footer>Survey: {cave['credit']}{source} &middot; {CREDITS.get(cave['terrain']['type'], '')} Imagery: Esri &middot; Built by <a href="https://github.com/CaveSurveying/cave-viewer">cave-viewer</a> from the survey data; every push rebuilds it.</footer>
</main></body></html>
'''


# A landing page needs no service worker, but a 3D view built where it now
# is (before it had a page) left one, which would go on showing the old
# view from its cache. This one takes its place and stands down: the
# browser fetches it as the page opens, and it unregisters and reloads.
RETIRE = """// No service worker here: this one retires one an earlier build left (caveviewer pages.py).
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.registration.unregister()
  .then(() => self.clients.matchAll({ type: 'window' }))
  .then(cs => cs.forEach(c => c.navigate(c.url)))));
"""


def build(cfg, caves, out):
    """Each cave's landing page, where it has one."""
    import sys
    for c in caves:
        if c.get('page'):
            os.makedirs(os.path.join(out, c['page']), exist_ok=True)
            with open(os.path.join(out, c['page'], 'index.html'), 'w', encoding='utf-8') as f:
                f.write(page(cfg, c, caves, out))
            with open(os.path.join(out, c['page'], 'sw.js'), 'w', encoding='utf-8') as f:
                f.write(RETIRE)
            print(f'{c["name"]}: landing page {os.path.normpath(os.path.join(out, c["page"]))}/index.html', file=sys.stderr)
