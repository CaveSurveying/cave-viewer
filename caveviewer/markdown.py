"""A little Markdown, to HTML: enough for a cave's notes (the config's
about), without a dependency.

Headings (#, ##, ###; on the page they sit under its own), paragraphs,
lists (- or * or 1.), block quotes (>), links [text](url), **bold**,
*italic*, `code` and a line of --- for a rule. Everything else is text:
HTML in it is shown, not used.
"""
import html
import re

INLINE = [
    (re.compile(r'`([^`]+)`'), r'<code>\1</code>'),
    (re.compile(r'\*\*(.+?)\*\*'), r'<b>\1</b>'),
    (re.compile(r'(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\w)'), r'<i>\1</i>'),
    (re.compile(r'(?<![\w])_(?!\s)(.+?)(?<!\s)_(?![\w])'), r'<i>\1</i>'),
]
LINK = re.compile(r'\[([^\]]+)\]\(([^)\s]+)\)')


def inline(text):
    """A line's text: escaped, then its links, code, bold and italic."""
    out, last = [], 0
    for m in LINK.finditer(text):
        out.append(_marks(html.escape(text[last:m.start()], quote=False)))
        url = m.group(2)
        safe = re.match(r'(https?:|mailto:|#|/|\.{0,2}/|[\w.-]+(/|$))', url) and not url.lower().startswith('javascript:')
        label = _marks(html.escape(m.group(1), quote=False))
        out.append(f'<a href="{html.escape(url)}">{label}</a>' if safe else label)
        last = m.end()
    out.append(_marks(html.escape(text[last:], quote=False)))
    return ''.join(out)


def _marks(t):
    for r, s in INLINE:
        t = r.sub(s, t)
    return t


def to_html(text, top=2):
    """The document as HTML, its # headings as <h{top}> and down."""
    out, para, items, kind, quote = [], [], [], None, []

    def flush():
        nonlocal para, items, kind, quote
        if para:
            out.append(f'<p>{inline(" ".join(para))}</p>')
        if items:
            out.append(f'<{kind}>' + ''.join(f'<li>{inline(i)}</li>' for i in items) + f'</{kind}>')
        if quote:
            out.append(f'<blockquote>{to_html(chr(10).join(quote), top)}</blockquote>')
        para, items, kind, quote = [], [], None, []

    for line in text.splitlines():
        s = line.strip()
        h = re.match(r'(#{1,6})\s+(.*?)\s*#*$', s)
        li = re.match(r'([-*]|\d+[.)])\s+(.*)', s)
        if not s:
            flush()
        elif s.startswith('>'):
            if para or items:
                flush()
            quote.append(s[1:].lstrip())
        elif h:
            flush()
            n = min(6, top + len(h.group(1)) - 1)
            out.append(f'<h{n}>{inline(h.group(2))}</h{n}>')
        elif re.fullmatch(r'(-\s*){3,}|(\*\s*){3,}', s):
            flush()
            out.append('<hr>')
        elif li:
            k = 'ol' if li.group(1)[0].isdigit() else 'ul'
            if para or quote or (items and k != kind):
                flush()
            kind = k
            items.append(li.group(2))
        elif items and line[:1].isspace():
            items[-1] += ' ' + s            # (a list item carried on over the next line)
        else:
            if items or quote:
                flush()
            para.append(s)
    flush()
    return '\n'.join(out)
