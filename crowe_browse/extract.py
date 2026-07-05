"""Pure HTML extraction: readable text and interactive elements.

Uses only the stdlib html.parser so it is offline-testable with no browser and
no heavy parser dependency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

_SKIP_TAGS = {"script", "style", "noscript", "nav", "header", "footer", "aside", "title"}
_BLOCK_TAGS = {
    "p", "div", "section", "article", "br", "li", "h1", "h2", "h3", "h4", "tr",
}
_INTERACTIVE = {"a", "button", "input", "textarea", "select"}
_VOID = {"input"}
_ROLE = {
    "a": "link", "button": "button", "input": "textbox",
    "textarea": "textbox", "select": "combobox",
}


@dataclass
class Element:
    ref: int
    role: str
    name: str
    tag: str


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _BLOCK_TAGS and self._skip == 0:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            t = data.strip()
            if t:
                self.parts.append(t + " ")


def readable_text(html: str, url: str = "") -> str:
    p = _TextExtractor()
    p.feed(html)
    text = "".join(p.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n+", "\n\n", text)
    return text.strip()


class _ElementCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[tuple[str, str]] = []  # (tag, name)
        self._cur_tag: str | None = None
        self._cur_attrs: dict = {}
        self._cur_text: list[str] = []

    def _attr_label(self, tag, attrs):
        return (
            attrs.get("aria-label")
            or attrs.get("placeholder")
            or attrs.get("value")
            or attrs.get("name")
            or (attrs.get("href", "") if tag == "a" else "")
        )

    def _finish(self):
        tag = self._cur_tag
        attrs = self._cur_attrs
        label = " ".join(self._cur_text).strip() or self._attr_label(tag, attrs)
        self.items.append((tag, (label or "")[:80]))
        self._cur_tag = None
        self._cur_attrs = {}
        self._cur_text = []

    def handle_starttag(self, tag, attrs):
        if self._cur_tag is not None:
            self._finish()  # nested/unclosed: finalize the previous one
        if tag in _INTERACTIVE:
            d = dict(attrs)
            if tag in _VOID:
                self.items.append((tag, (self._attr_label(tag, d) or "")[:80]))
            else:
                self._cur_tag = tag
                self._cur_attrs = d
                self._cur_text = []

    def handle_data(self, data):
        if self._cur_tag is not None:
            t = data.strip()
            if t:
                self._cur_text.append(t)

    def handle_endtag(self, tag):
        if self._cur_tag is not None and tag == self._cur_tag:
            self._finish()


def interactive_elements(html: str) -> list[Element]:
    c = _ElementCollector()
    c.feed(html)
    if c._cur_tag is not None:
        c._finish()
    return [
        Element(ref=i, role=_ROLE.get(tag, tag), name=name, tag=tag)
        for i, (tag, name) in enumerate(c.items)
    ]
