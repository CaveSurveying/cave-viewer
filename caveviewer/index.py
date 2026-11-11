"""The landing page for a repo of several caves (site.index): a card for
each, with its picture (preview.png, where there is one), its length and
depth, and the caves' credits.

site: {"title", "description" (its meta description), "lede" (HTML, under
the title), "footer" (HTML: {credits} is each cave's credit in turn)}
"""
import html
import json
import os


def page(site, caves, out):
    cards = []
    for c in caves:
        s = json.load(open(os.path.join(out, c['path'], 'scene.json')))
        st = s['stats']
        img = f'<img src="{c["path"]}/preview.png" alt="" loading="lazy">' if os.path.exists(os.path.join(out, c['path'], 'preview.png')) else '<div class="noimg"></div>'
        cards.append(f'''<a class="card" href="{c.get('page') or c['path']}/">{img}<div class="txt">
  <h2>{html.escape(c['name'])}</h2>
  <p class="area">{html.escape(c['area'])} &middot; {s['grid_ref']}</p>
  <p class="nums"><b>{st['length'] / 1000:.1f} km</b> surveyed &middot; <b>{st['depth']} m</b> deep</p>
</div></a>''')
    credits = ' &middot; '.join(f"{html.escape(c['name'])}: {c['credit']}" for c in caves)
    footer = site['footer'].replace('{credits}', credits)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(site['title'])}</title>
<meta name="description" content="{html.escape(site['description'])}">
<link rel="stylesheet" href="{caves[0]['path']}/vendor/inter/inter.css">
<style>
  :root {{ --bg: #05070c; --card: #0e131d; --text: #e9eef6; --muted: #8d99ab; --line: rgba(255,255,255,.08); --accent: #ffd27a; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 Inter, system-ui, sans-serif; }}
  main {{ max-width: 1120px; margin: 0 auto; padding: 48px 16px 32px; }}
  h1 {{ margin: 0 0 6px; font-size: 32px; letter-spacing: -.02em; }}
  .lede {{ margin: 0 0 32px; color: var(--muted); max-width: 640px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }}
  .card {{ display: block; background: var(--card); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; color: inherit; text-decoration: none; transition: border-color .15s, transform .15s; }}
  .card:hover {{ border-color: rgba(255,210,122,.5); transform: translateY(-2px); }}
  .card img, .noimg {{ display: block; width: 100%; aspect-ratio: 16 / 10; object-fit: cover; background: #0a0e16; }}
  .txt {{ padding: 14px 16px 16px; }}
  h2 {{ margin: 0; font-size: 19px; }}
  .area {{ margin: 2px 0 8px; color: var(--muted); font-size: 13px; }}
  .nums {{ margin: 0; font-size: 13px; color: var(--muted); }}
  .nums b {{ color: var(--text); font-weight: 600; }}
  footer {{ margin-top: 36px; padding-top: 16px; border-top: 1px solid var(--line); color: var(--muted); font-size: 12px; }}
  footer a {{ color: var(--muted); }}
</style></head><body><main>
<h1>{html.escape(site['title'])}</h1>
<p class="lede">{site['lede']}</p>
<div class="grid">
{chr(10).join(cards)}
</div>
<footer>{footer}</footer>
</main></body></html>
'''
