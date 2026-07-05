"""Drive-a-results-page search parsing (pure).

The DuckDuckGo HTML endpoint renders a plain results page a real browser can
load without the JSON API's bot-blocking. This module only parses that HTML;
the tool layer drives the browser to SEARCH_URL and passes the content here.
"""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

SEARCH_URL = "https://html.duckduckgo.com/html/?q={q}"


class _ResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict] = []
        self._mode: str | None = None  # "title" | "snippet"
        self._title = ""
        self._url = ""
        self._snippet = ""

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        d = dict(attrs)
        classes = (d.get("class") or "").split()
        if "result__a" in classes:
            # flush any prior in-progress result
            if self._url:
                self._flush()
            self._url = _clean_url(d.get("href", ""))
            self._mode = "title"
        elif "result__snippet" in classes:
            self._mode = "snippet"

    def handle_data(self, data):
        if self._mode == "title":
            self._title += data
        elif self._mode == "snippet":
            self._snippet += data

    def handle_endtag(self, tag):
        if tag == "a":
            self._mode = None

    def _flush(self):
        self.results.append({
            "title": unescape(self._title).strip(),
            "url": self._url,
            "snippet": unescape(self._snippet).strip(),
        })
        self._title = self._url = self._snippet = ""

    def close(self):
        super().close()
        if self._url:
            self._flush()


def _clean_url(href: str) -> str:
    # DuckDuckGo sometimes wraps targets as /l/?uddg=<encoded>. Unwrap if present.
    if href.startswith("//duckduckgo.com/l/") or "uddg=" in href:
        q = parse_qs(urlparse(href).query)
        if "uddg" in q:
            return q["uddg"][0]
    return href


def parse_results(html: str) -> list[dict]:
    p = _ResultParser()
    p.feed(html)
    p.close()
    return p.results
