"""The cave's links out to who looks after it: its access body (access: who
to ask, keys, permits and closures, kept up to date there) and its entry in
the cave registry (registry). cave-viewer doesn't give access arrangements
itself: they change, and the access bodies already keep them.

access, registry: {"url", "label"} (label: the link's text, plain text)
"""
import html

E = html.escape


def link(x, text=None, new_tab=False):
    target = ' target="_blank" rel="noopener"' if new_tab else ''
    return f'<a href="{E(x["url"])}"{target}>{E(text or x.get("label") or x["url"])}</a>'


def page_html(cave):
    """The landing page's access box, or '' when the cave has neither link."""
    acc, reg = cave.get('access'), cave.get('registry')
    if not (acc or reg):
        return ''
    parts = []
    if acc:
        parts.append(f'<b>Access.</b> This page shows the survey, not the access arrangements: they change, '
                     f'and they&rsquo;re kept up to date elsewhere. Before a trip, see {link(acc)}.')
    if reg:
        parts.append(f'{"The" if acc else "<b>Registry.</b> The"} cave&rsquo;s entry in {link(reg)} has its other surveys and references.')
    return f'<p class="access">{" ".join(parts)}</p>'


def viewer_html(cave):
    """The 3D view's line under its title: the same two links, opening in a new tab."""
    acc, reg = cave.get('access'), cave.get('registry')
    parts = []
    if acc:
        parts.append(f'<span title="{E(acc.get("label", ""))}">Before a trip: {link(acc, "access ↗", True)}</span>')
    if reg:
        parts.append(f'<span title="{E(reg.get("label", ""))}">{link(reg, "registry entry ↗", True)}</span>')
    return ' &middot; '.join(parts)
