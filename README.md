# livedemo

**Embed working interfaces inside one self-contained HTML page.**

A walkthrough built from screenshots starts lying the first time the product changes. This embeds
the real interface instead — a complete HTML document rendered inside an isolated frame — so
regenerating the page picks up whatever the product currently does.

```python
from livedemo import Page

page = Page("How the scanner reports a finding",
            kicker="Walkthrough", lede="Command, interface, and what it means.")

page.section("Running a scan", "One command produces the evidence pack.")
page.terminal("scanner --target fleet --report out.html", captured_output)

ui   = page.screen("out.html", label="out.html", height=680, add=False)
note = page.note("read", "Look at the third column",
                 "Every finding carries the control it maps to.", add=False)
page.split(ui, note)

page.note("limit", "What it will not tell you",
          "Whether the finding matters to your business.")
page.write("walkthrough.html")
```

One file, two standard-library imports, no install.

## Why frames and not screenshots

A screenshot is a picture of the past. The embedded document is the artefact itself: scrollable,
sortable, clickable, and correct as of the moment the page was built. When the product changes,
rebuild and it is current — there is no stale image to notice and replace.

## Deliberate scope

**This module knows nothing about any product.** It takes documents and text you hand it and
arranges them. It does not parse, inspect or special-case what it embeds, it carries no branding,
and it imports nothing beyond `html` and `os`.

That is the point. The same file can be used by unrelated projects — including ones with
different licences and different confidentiality — without either acquiring a dependency on the
other or a trace of the other's code. **The separation is enforced by tests, not by remembering:**
`test_livedemo.py` fails if a non-stdlib import appears, if any product name appears in the
source, if it grows past a single file, or if it starts parsing the documents it carries.

## What it will not do

It fetches nothing. A document that pulls in an external stylesheet, font or script renders
without them. That is a feature rather than a gap: the page has to stand on its own on a laptop
with no network, in a room, months from now.

It also refuses a document over 2 MB, with a message saying to embed a representative instance
rather than a whole corpus. A page nobody waits for is a page nobody reads.

## Layout

Designed for 1920, sized so an older laptop panel does not need zooming: 17px base type, and the
extra width spent on a **second column** rather than on longer lines — a 1700px line of prose is
unreadable however large the screen is. `split()` puts the interface beside its explanation, with
the notes sticky as the frame scrolls, and collapses to one column below 1280px.

Light and dark both handled; the page follows the reader's system setting.

## Notes have four kinds, on purpose

`read` says what to look at. `why` says why it matters. `limit` says what the thing will not tell
you. `warn` flags something that needs care. Keeping them visually distinct is what stops a
walkthrough reading as a brochure — **a demo with no `limit` notes is a sales page**, and the
reader can tell.

## Tests

```bash
python3 -m unittest test_livedemo -v    # 16 tests
```

Covering the embedding mechanics that actually bite: a document containing quotes, a document
containing its own `</iframe>`, oversized input, and that the host page fetches nothing.

## License

MIT.
