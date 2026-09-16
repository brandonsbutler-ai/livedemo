"""livedemo -- embed working interfaces inside one self-contained HTML page.

A walkthrough that shows SCREENSHOTS starts lying the first time the product
changes. This embeds the real interface instead: a complete HTML document
rendered inside an isolated frame, so regenerating the page picks up whatever
the product currently does.

    from livedemo import Page

    page = Page("How the scanner reports a finding")
    page.section("Running a scan", "One command produces the evidence pack.")
    page.terminal("scanner --target fleet --report out.html", captured_output)
    page.screen("out.html", label="out.html", height=680)
    page.note("read", "Look at the third column", "...")
    page.write("walkthrough.html")

SCOPE, DELIBERATELY NARROW. This module knows nothing about any product. It
takes documents and text you give it and arranges them. It has no imports
beyond the standard library, no branding, and no knowledge of what it is
embedding -- which is what lets the same file be used by unrelated projects
without either one acquiring a dependency on the other.

WHAT IT DOES NOT DO. It will not fetch anything, so a document that pulls in an
external stylesheet or script will render without it. That is a feature: the
page has to stand alone on a laptop with no network, in a boardroom, months
from now.
"""

import html
import os

__version__ = "0.1.0"
__all__ = ["Page", "__version__"]

_MAX_FRAME_BYTES = 2_000_000       # past this a page stops opening quickly

# Sized for 1920 while staying readable on an older laptop panel: the width is
# spent on a second column rather than on longer lines, because a 1700px line of
# prose is unreadable however large the screen is.
_CSS = """
:root{--ground:#F6F7F5;--panel:#FFF;--sunk:#ECEFEE;--ink:#12161C;--rule:#D9DEE0;
--accent:#17566B;--accent-soft:#E2EDF0;--warn:#A6641A;--warn-soft:#F7EEE1;
--stop:#8E3B3B;--stop-soft:#F6E7E7;--go:#2C6E54;--go-soft:#E3EFE9;--mut:#5B6670;
--shadow:0 1px 2px rgba(18,22,28,.06),0 16px 40px rgba(18,22,28,.07);
--display:"Archivo","Helvetica Neue",Arial,sans-serif;
--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){
--ground:#14171A;--panel:#1C2024;--sunk:#23282D;--ink:#E9ECEE;--rule:#333A40;
--accent:#6FB2C7;--accent-soft:#1E3A44;--warn:#D9A05B;--warn-soft:#332818;
--stop:#D08A8A;--stop-soft:#33201F;--go:#7FC8A4;--go-soft:#1D3229;--mut:#98A2AA;
--shadow:0 1px 2px rgba(0,0,0,.3),0 16px 40px rgba(0,0,0,.35)}}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
font:17px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}
.wrap{max-width:1720px;margin:0 auto;padding:34px 30px 80px}
h1{font:700 42px/1.1 var(--display);margin:0 0 8px;letter-spacing:-.02em}
h2{font:700 30px/1.18 var(--display);margin:0 0 8px;letter-spacing:-.014em}
.kicker{font:600 13px var(--display);letter-spacing:.16em;text-transform:uppercase;
color:var(--accent);margin-bottom:10px}
.lede{color:var(--mut);max-width:74ch;margin:0 0 18px;font-size:18px}
p{max-width:74ch}
.section{background:var(--panel);border:1px solid var(--rule);border-radius:16px;
box-shadow:var(--shadow);padding:38px 42px;margin-bottom:28px}
.split{display:grid;grid-template-columns:minmax(0,1.85fr) minmax(360px,1fr);
gap:26px;align-items:start;margin:14px 0}
.split .side{position:sticky;top:20px}
@media(max-width:1280px){.split{grid-template-columns:1fr}.split .side{position:static}}
.term{background:#11161A;border-radius:12px;overflow:hidden;margin:12px 0 14px}
.term .cmd{background:#0B0F12;color:#8FD3A8;font:14px var(--mono);padding:11px 18px;
border-bottom:1px solid #222A30}
.term pre{margin:0;padding:15px 18px;color:#D7DDE2;font:13.5px/1.6 var(--mono);
overflow-x:auto;white-space:pre}
.screen{border:1px solid var(--rule);border-radius:12px;overflow:hidden;
margin:12px 0 14px;background:var(--panel);box-shadow:var(--shadow)}
.chrome{display:flex;align-items:center;gap:7px;padding:9px 14px;background:var(--sunk);
border-bottom:1px solid var(--rule)}
.dot{width:11px;height:11px;border-radius:50%;background:var(--rule);display:inline-block}
.addr{margin-left:10px;font:13px var(--mono);color:var(--mut)}
iframe{width:100%;border:0;display:block;background:#fff}
@media(prefers-color-scheme:dark){iframe{background:#1C2024}}
.note{border-radius:11px;padding:14px 17px;margin:12px 0;font-size:16px}
.note strong{display:block;font:700 13.5px var(--display);margin-bottom:4px;
text-transform:uppercase;letter-spacing:.05em}
.note.read{background:var(--accent-soft)} .note.read strong{color:var(--accent)}
.note.why{background:var(--go-soft)} .note.why strong{color:var(--go)}
.note.limit{background:var(--stop-soft)} .note.limit strong{color:var(--stop)}
.note.warn{background:var(--warn-soft)} .note.warn strong{color:var(--warn)}
.stats{display:flex;flex-wrap:wrap;gap:14px;margin:20px 0}
.stat{background:var(--sunk);border-radius:12px;padding:15px 20px;min-width:132px}
.stat b{display:block;font:700 30px/1.1 var(--display)}
.stat span{color:var(--mut);font-size:13.5px}
.foot{color:var(--mut);font-size:14px;text-align:center;padding:12px 0 0}
"""


class FrameTooLarge(Exception):
    """An embedded document is big enough to make the page slow to open."""


def _e(text):
    return html.escape("" if text is None else str(text))


class Page:
    """A walkthrough page. Call the builders in the order you want them read."""

    def __init__(self, title, kicker="", lede=""):
        self.title = title
        self._parts = []
        self._open = False
        if kicker or lede:
            self.section(title, lede, kicker=kicker, heading_level=1)

    # -- structure --------------------------------------------------------
    def section(self, heading, lede="", kicker="", heading_level=2, anchor=None):
        """Start a new panel. Everything added next lands inside it."""
        self._close()
        tag = f"h{heading_level}"
        anchor_html = f'<div id="{_e(anchor)}"></div>' if anchor else ""
        self._parts.append(
            f'<section class="section">{anchor_html}'
            + (f'<div class="kicker">{_e(kicker)}</div>' if kicker else "")
            + f"<{tag}>{_e(heading)}</{tag}>"
            + (f'<p class="lede">{_e(lede)}</p>' if lede else ""))
        self._open = True
        return self

    def split(self, main, side):
        """Interface on the left, its explanation on the right.

        This is what the width of a wide screen is actually for. Below 1280px
        it collapses to one column, because side-by-side on a laptop gives both
        halves too little room.
        """
        self._parts.append(f'<div class="split"><div>{main}</div>'
                           f'<div class="side">{side}</div></div>')
        return self

    # -- blocks -----------------------------------------------------------
    def html(self, markup):
        """Raw markup, for anything this class does not cover."""
        self._parts.append(markup)
        return self

    def text(self, body):
        self._parts.append(f"<p>{body}</p>")
        return self

    def terminal(self, command, output, max_lines=None):
        """A captured command and its real output."""
        lines = str(output).rstrip().splitlines()
        if max_lines and len(lines) > max_lines:
            hidden = len(lines) - max_lines
            lines = lines[:max_lines] + [f"    ... {hidden} more lines"]
        block = (f'<div class="term"><div class="cmd">$ {_e(command)}</div>'
                 f'<pre>{_e(chr(10).join(lines))}</pre></div>')
        self._parts.append(block)
        return block

    def screen(self, document, label="", height=620, add=True):
        """Embed a complete HTML document, live, in an isolated frame.

        `document` is a path or the markup itself. The frame is sandboxed and
        same-origin only, so the embedded page cannot navigate the host.
        """
        markup = document
        if isinstance(document, str) and os.path.isfile(document):
            with open(document, encoding="utf-8") as fh:
                markup = fh.read()
            label = label or os.path.basename(document)
        size = len(markup.encode("utf-8"))
        if size > _MAX_FRAME_BYTES:
            raise FrameTooLarge(
                f"{label or 'document'} is {size // 1024} KB. Embed a "
                f"representative instance rather than a whole corpus -- a page "
                f"nobody waits for is a page nobody reads.")
        block = (f'<div class="screen"><div class="chrome">'
                 f'<span class="dot"></span><span class="dot"></span>'
                 f'<span class="dot"></span>'
                 f'<span class="addr">{_e(label)}</span></div>'
                 f'<iframe loading="lazy" style="height:{int(height)}px" '
                 f'sandbox="allow-same-origin" '
                 f'srcdoc="{html.escape(markup, quote=True)}"></iframe></div>')
        if add:
            self._parts.append(block)
        return block

    def note(self, kind, title, body, add=True):
        """An aside. `kind` is read, why, limit or warn.

        The four exist to keep different claims visually apart: what to look
        at, why it matters, and what the thing will not tell you. A walkthrough
        with no limit notes reads as a brochure.
        """
        if kind not in ("read", "why", "limit", "warn"):
            raise ValueError(f"note kind must be read/why/limit/warn, got {kind!r}")
        block = (f'<div class="note {kind}"><strong>{_e(title)}</strong> {body}</div>')
        if add:
            self._parts.append(block)
        return block

    def stats(self, pairs):
        cells = "".join(f'<div class="stat"><b>{_e(v)}</b><span>{_e(k)}</span></div>'
                        for k, v in pairs)
        self._parts.append(f'<div class="stats">{cells}</div>')
        return self

    # -- output -----------------------------------------------------------
    def _close(self):
        if self._open:
            self._parts.append("</section>")
            self._open = False

    def render(self, footer=""):
        self._close()
        body = "".join(self._parts)
        foot = f'<p class="foot">{footer}</p>' if footer else ""
        return (f"<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">\n"
                f'<meta name="viewport" content="width=device-width,'
                f'initial-scale=1,viewport-fit=cover">\n'
                f"<title>{_e(self.title)}</title><style>{_CSS}</style></head>\n"
                f'<body><div class="wrap">{body}{foot}</div></body></html>')

    def write(self, path, footer=""):
        doc = self.render(footer)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(doc)
        return path
