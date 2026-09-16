"""Tests for livedemo, including the separation rule.

The separation tests are the important ones. This module is intended for use by
unrelated projects -- one public and MIT, one proprietary -- and the whole value
of that arrangement is that neither acquires a dependency on the other, or any
trace of the other's code or branding. That has to be enforced by a check,
because "remember not to" is not a control.
"""

import ast
import html
import os
import sys
import tempfile
import unittest
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import livedemo
from livedemo import FrameTooLarge, Page

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = open(os.path.join(HERE, "livedemo.py"), encoding="utf-8").read()


class TestSeparation(unittest.TestCase):
    """No cross-pollination, proven rather than promised."""

    def test_imports_nothing_outside_the_standard_library(self):
        tree = ast.parse(SOURCE)
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
        outside = found - set(sys.stdlib_module_names)
        self.assertEqual(outside, set(), f"non-stdlib imports: {outside}")

    def test_names_no_product_on_either_side(self):
        """A shared helper carrying one project's vocabulary is not shared."""
        lowered = SOURCE.lower()
        for word in ("vanilla", "cobbler", "fortefide", "fortestrike",
                     "densesense", "denseaiarmour", "densedefense", "forte"):
            self.assertNotIn(word, lowered, f"product name {word!r} present")

    def test_is_a_single_file_with_no_package_of_its_own(self):
        """Droppable into any tree without bringing a directory with it."""
        modules = [f for f in os.listdir(HERE)
                   if f.endswith(".py") and not f.startswith("test_")]
        self.assertEqual(modules, ["livedemo.py"])

    def test_knows_nothing_about_what_it_embeds(self):
        """It must not inspect or special-case the documents it is given."""
        tree = ast.parse(SOURCE)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in (
                    "findall", "search", "match"):
                self.fail("parses the embedded document; it should only carry it")


class TestEmbedding(unittest.TestCase):
    def _frames(self, doc):
        class P(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.frames = []

            def handle_starttag(self, tag, attrs):
                if tag == "iframe":
                    d = dict(attrs)
                    if "srcdoc" in d:
                        self.frames.append(d["srcdoc"])
        p = P()
        p.feed(doc)
        p.close()
        return p.frames

    def test_an_embedded_document_survives_whole(self):
        inner = ('<!doctype html><html><head><style>p{color:red}</style></head>'
                 '<body><p>Inside</p><script>var x=1;</script></body></html>')
        page = Page("t")
        page.section("s")
        page.screen(inner, label="inner.html")
        frames = self._frames(page.render())
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].strip(), inner)

    def test_quotes_in_the_document_cannot_break_the_attribute(self):
        inner = ('<!doctype html><html><body>'
                 '<p class="x" data-y=\'z\'>He said "hello"</p></body></html>')
        page = Page("t")
        page.section("s")
        page.screen(inner)
        frames = self._frames(page.render())
        self.assertIn('He said "hello"', frames[0])

    def test_a_document_containing_a_closing_iframe_tag_is_contained(self):
        """The embedded page must not be able to end its own frame early."""
        inner = "<!doctype html><html><body>x</iframe><h1>escaped</h1></body></html>"
        page = Page("t")
        page.section("s")
        page.screen(inner)
        doc = page.render()
        self.assertEqual(len(self._frames(doc)), 1)
        self.assertNotIn("</iframe><h1>escaped", doc)

    def test_reads_a_document_from_a_path(self):
        page = Page("t")
        page.section("s")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "report.html")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("<!doctype html><html><body>from disk</body></html>")
            page.screen(path)
        doc = page.render()
        self.assertIn("from disk", self._frames(doc)[0])
        self.assertIn("report.html", doc)      # the label defaults to the name

    def test_an_oversized_document_is_refused_with_a_reason(self):
        page = Page("t")
        page.section("s")
        with self.assertRaises(FrameTooLarge) as caught:
            page.screen("<html>" + "x" * 3_000_000 + "</html>", label="huge.html")
        self.assertIn("representative instance", str(caught.exception))

    def test_the_page_itself_fetches_nothing(self):
        page = Page("t", kicker="k", lede="l")
        page.section("s", "lede")
        page.terminal("run --thing", "output here")
        page.screen("<!doctype html><html><body>x</body></html>")
        page.note("limit", "A limit", "what it will not do")
        doc = page.render(footer="f")
        for needle in ('src="http', 'href="http', "cdn.", "fonts.googleapis"):
            self.assertNotIn(needle, doc)


class TestBuilders(unittest.TestCase):
    def test_terminal_truncates_and_says_so(self):
        page = Page("t")
        page.section("s")
        page.terminal("cmd", "\n".join(f"line {i}" for i in range(50)), max_lines=5)
        doc = page.render()
        self.assertIn("45 more lines", doc)

    def test_note_kinds_are_constrained(self):
        page = Page("t")
        page.section("s")
        with self.assertRaises(ValueError):
            page.note("interesting", "t", "b")

    def test_terminal_output_is_escaped(self):
        page = Page("t")
        page.section("s")
        page.terminal("cmd", "<script>alert(1)</script>")
        doc = page.render()
        self.assertNotIn("<script>alert(1)", doc)

    def test_split_puts_the_interface_beside_its_explanation(self):
        page = Page("t")
        page.section("s")
        main = page.screen("<html><body>ui</body></html>", add=False)
        side = page.note("read", "Look here", "at this", add=False)
        page.split(main, side)
        doc = page.render()
        self.assertIn('class="split"', doc)
        self.assertIn('class="side"', doc)
        self.assertEqual(doc.count("<iframe"), 1)   # not added twice

    def test_sections_close_themselves(self):
        page = Page("t")
        page.section("one")
        page.text("a")
        page.section("two")
        page.text("b")
        doc = page.render()
        self.assertEqual(doc.count("<section"), doc.count("</section>"))

    def test_renders_at_1920_without_requiring_zoom(self):
        doc = Page("t").render()
        self.assertIn("max-width:1720px", doc)
        self.assertIn("font:17px", doc.replace(" ", ""))
        self.assertIn("max-width:1280px", doc)      # collapses for laptops



class SandboxTests(unittest.TestCase):
    """The sandbox has to withhold the right things, not the easy things."""

    def _frame(self):
        page = Page("t")
        return page.screen("<!doctype html><p onclick=\"x()\">hi</p>", add=False)

    def test_scripts_run_inside_the_frame(self):
        """An embedded interface whose scripts are blocked is a screenshot.

        Withholding allow-scripts silently kills every control -- sorting,
        editing, the hover map -- while the prose still says to click them.
        """
        self.assertIn("allow-scripts", self._frame())

    def test_frame_cannot_reach_the_host(self):
        """allow-scripts WITH allow-same-origin removes the sandbox entirely.

        Together those two tokens let the framed page script the host document
        and its storage. Scripts yes; same-origin no.
        """
        self.assertNotIn("allow-same-origin", self._frame())

    def test_downloads_are_allowed(self):
        """Several embedded tools export a file via createObjectURL.

        A sandboxed frame silently drops the download without this token, so the
        export button appears to do nothing at all.
        """
        self.assertIn("allow-downloads", self._frame())

    def test_no_broader_tokens(self):
        """Nothing here needs to navigate, popup, or run top-level scripts."""
        frame = self._frame()
        for token in ("allow-top-navigation", "allow-popups", "allow-forms",
                      "allow-modals", "allow-pointer-lock", "allow-presentation"):
            self.assertNotIn(token, frame)

if __name__ == "__main__":
    unittest.main(verbosity=2)
