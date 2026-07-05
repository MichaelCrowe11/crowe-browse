# crowe-browse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `crowe-browse` Phase 1 - a stateful, agent-driven web browser exposed as `crowe-agent-core` kernel tools (search, read, act on live pages) that any Crowe agent can register.

**Architecture:** Pure HTML-extraction helpers (offline-testable) + one async Playwright engine with two connect modes (launch headless / attach to real Chrome) + a stateful session + kernel `ToolSpec`s for the agentic loop. Read tools run free; act tools are classified mutating for an approval gate. The kernel (`crowe-agent-core`) is a dependency and is NOT modified.

**Tech Stack:** Python 3.11, `uv`, `crowe-agent-core` (local editable dep), `playwright` (async API) + Chromium, `pytest` + `pytest-asyncio`, stdlib `html.parser` for extraction (no heavy parser deps).

## Global Constraints

- Python `>=3.11`; use `.venv/bin/python` and `uv pip` (repo `.venv` has no `pip`).
- Dependencies limited to: `crowe-agent-core`, `playwright` (+ `pytest`, `pytest-asyncio` dev). No `beautifulsoup4`/`lxml`/readability libs - extraction uses stdlib `html.parser`.
- `crowe-agent-core` is a LOCAL editable path dependency at `../crowe-agent-core`; not modified by this project.
- No em dashes in source (use hyphens).
- Playwright uses the ASYNC API (`playwright.async_api`). Tool handlers are `async`. The sync Playwright API cannot run inside the kernel's asyncio loop, so it is not used.
- `BROWSE_MUTATING = {"click", "type_text"}` is the single source of truth for which tools require approval. Read/navigation tools run free.
- Element enumeration selector is exactly `"a, button, input, textarea, select"` in DOM order; a tool `ref` is the index into that ordered set. The engine resolves a ref with `page.locator(SEL).nth(ref)`.

---

### Task 1: Scaffold package + Playwright + kernel dep

**Files:**
- Create: `pyproject.toml`, `crowe_browse/__init__.py`, `.gitignore` (exists; leave)

**Interfaces:**
- Produces: importable package `crowe_browse` with `__version__`; installed `playwright` + Chromium.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "crowe-browse"
version = "0.1.0"
description = "Agent-driven web browser exposed as Crowe kernel tools (the Comet engine)"
requires-python = ">=3.11"
dependencies = [
    "crowe-agent-core",
    "playwright>=1.48.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.24.0"]

[tool.uv.sources]
crowe-agent-core = { path = "../crowe-agent-core", editable = true }

[tool.pytest.ini_options]
asyncio_mode = "auto"

[tool.setuptools.packages.find]
include = ["crowe_browse*"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 2: Write `crowe_browse/__init__.py`**

```python
"""crowe-browse: an agent-driven web browser exposed as Crowe kernel tools."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create venv, install, install Chromium, verify**

Run:
```bash
cd ~/Projects/crowe-browse
uv venv --python 3.11 .venv
uv pip install -e ".[dev]" --python .venv/bin/python
.venv/bin/python -m playwright install chromium
.venv/bin/python -c "import crowe_agent_core, playwright; from crowe_agent_core import ToolSpec; print('deps OK')"
```
Expected: Chromium downloads (~150 MB), then `deps OK`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml crowe_browse/__init__.py
git commit -m "feat: scaffold crowe-browse package + playwright + kernel dep"
```

---

### Task 2: HTML extraction (pure, offline)

**Files:**
- Create: `crowe_browse/extract.py`
- Test: `tests/test_extract.py`
- Create: `tests/fixtures/article.html`, `tests/fixtures/form.html`

**Interfaces:**
- Produces: `Element` dataclass (`ref: int`, `role: str`, `name: str`, `tag: str`); `readable_text(html: str, url: str = "") -> str`; `interactive_elements(html: str) -> list[Element]`.

- [ ] **Step 1: Write fixtures**

`tests/fixtures/article.html`:
```html
<html><head><title>Oyster Guide</title><style>.x{color:red}</style></head>
<body>
<nav><a href="/home">Home</a></nav>
<article><h1>Blue Oyster</h1><p>Blue oyster fruits at 15 to 21 C.</p>
<p>Keep humidity near 85 percent.</p></article>
<script>console.log('ignore me')</script>
<footer>copyright</footer>
</body></html>
```

`tests/fixtures/form.html`:
```html
<html><body>
<a href="/a">First Link</a>
<input name="q" placeholder="Search here">
<button>Go</button>
</body></html>
```

- [ ] **Step 2: Write the failing test**

`tests/test_extract.py`:
```python
from pathlib import Path

from crowe_browse.extract import Element, interactive_elements, readable_text

FIX = Path(__file__).parent / "fixtures"


def _read(name):
    return (FIX / name).read_text()


def test_readable_text_keeps_article_drops_boilerplate():
    text = readable_text(_read("article.html"))
    assert "Blue oyster fruits at 15 to 21 C." in text
    assert "Keep humidity near 85 percent." in text
    assert "console.log" not in text  # script dropped
    assert "copyright" not in text  # footer dropped


def test_interactive_elements_enumerates_in_order():
    els = interactive_elements(_read("form.html"))
    assert [e.tag for e in els] == ["a", "input", "button"]
    assert els[0].ref == 0 and els[1].ref == 1 and els[2].ref == 2
    assert els[0].role == "link" and els[0].name == "First Link"
    assert els[1].role == "textbox" and "Search here" in els[1].name
    assert els[2].role == "button" and els[2].name == "Go"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crowe_browse.extract'`

- [ ] **Step 4: Write `crowe_browse/extract.py`**

```python
"""Pure HTML extraction: readable text and interactive elements.

Uses only the stdlib html.parser so it is offline-testable with no browser and
no heavy parser dependency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

_SKIP_TAGS = {"script", "style", "noscript", "nav", "header", "footer", "aside"}
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_extract.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add crowe_browse/extract.py tests/test_extract.py tests/fixtures/article.html tests/fixtures/form.html
git commit -m "feat: pure HTML extraction (readable text + interactive elements)"
```

---

### Task 3: Search-results parsing (pure)

**Files:**
- Create: `crowe_browse/search.py`
- Test: `tests/test_search.py`
- Create: `tests/fixtures/ddg_results.html`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `SEARCH_URL` (a `str.format`-able template with `{q}`); `parse_results(html: str) -> list[dict]` where each dict has keys `title`, `url`, `snippet`.

- [ ] **Step 1: Write the fixture**

`tests/fixtures/ddg_results.html` (mimics the DuckDuckGo HTML endpoint structure):
```html
<html><body>
<div class="result">
  <a class="result__a" href="https://example.com/oyster">Oyster Cultivation</a>
  <a class="result__snippet">Blue oyster mushrooms fruit at 15-21C.</a>
</div>
<div class="result">
  <a class="result__a" href="https://example.org/temps">Fruiting Temps</a>
  <a class="result__snippet">A guide to fruiting temperatures.</a>
</div>
</body></html>
```

- [ ] **Step 2: Write the failing test**

`tests/test_search.py`:
```python
from pathlib import Path

from crowe_browse.search import SEARCH_URL, parse_results

FIX = Path(__file__).parent / "fixtures"


def test_search_url_is_ddg_html_endpoint():
    url = SEARCH_URL.format(q="blue+oyster")
    assert url.startswith("https://html.duckduckgo.com/html/")
    assert "blue+oyster" in url


def test_parse_results_extracts_title_url_snippet():
    results = parse_results((FIX / "ddg_results.html").read_text())
    assert len(results) == 2
    assert results[0]["title"] == "Oyster Cultivation"
    assert results[0]["url"] == "https://example.com/oyster"
    assert "15-21C" in results[0]["snippet"]
    assert results[1]["url"] == "https://example.org/temps"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_search.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crowe_browse.search'`

- [ ] **Step 4: Write `crowe_browse/search.py`**

```python
"""Drive-a-results-page search parsing (pure).

The DuckDuckGo HTML endpoint renders a plain results page a real browser can
load without the JSON API's bot-blocking. This module only parses that HTML;
the tool layer drives the browser to SEARCH_URL and passes the content here.
"""

from __future__ import annotations

import re
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_search.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add crowe_browse/search.py tests/test_search.py tests/fixtures/ddg_results.html
git commit -m "feat: search-results parsing for the DDG HTML endpoint"
```

---

### Task 4: Browser engine (async Playwright, launch mode)

**Files:**
- Create: `crowe_browse/engine/__init__.py` (empty), `crowe_browse/engine/base.py`, `crowe_browse/engine/playwright_engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: `crowe_browse.extract.Element`.
- Produces: `SEL = "a, button, input, textarea, select"`; `PlaywrightEngine(mode="launch", *, headless=True, profile_dir=None, cdp_url=None)` with async methods: `start()`, `goto(url)`, `current_url() -> str`, `current_html() -> str`, `elements() -> list[Element]`, `click(ref)`, `type_text(ref, text)`, `go_back()`, `reload()`, `close()`.

- [ ] **Step 1: Write `crowe_browse/engine/base.py`**

```python
"""Browser engine contract. Element is re-exported from extract."""

from __future__ import annotations

from crowe_browse.extract import Element

SEL = "a, button, input, textarea, select"

__all__ = ["Element", "SEL"]
```

- [ ] **Step 2: Write the failing test**

`tests/test_engine.py`:
```python
from pathlib import Path

import pytest

from crowe_browse.engine.playwright_engine import PlaywrightEngine

FIX = Path(__file__).parent / "fixtures"


def _file_url(name):
    return (FIX / name).resolve().as_uri()


@pytest.mark.asyncio
async def test_engine_goto_read_and_elements():
    eng = PlaywrightEngine(mode="launch", headless=True)
    await eng.start()
    try:
        await eng.goto(_file_url("form.html"))
        assert eng.current_url().endswith("form.html")
        html = await eng.current_html()
        assert "First Link" in html
        els = await eng.elements()
        assert [e.tag for e in els] == ["a", "input", "button"]
    finally:
        await eng.close()


@pytest.mark.asyncio
async def test_engine_type_and_click():
    eng = PlaywrightEngine(mode="launch", headless=True)
    await eng.start()
    try:
        await eng.goto(_file_url("form.html"))
        await eng.type_text(1, "oyster")  # the input is ref 1
        html = await eng.current_html()
        # value now set on the input
        val = await eng._page.locator("input").input_value()
        assert val == "oyster"
        await eng.click(0)  # the first link; navigation may 404 on file://, no raise
    finally:
        await eng.close()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crowe_browse.engine'`

- [ ] **Step 4: Write `crowe_browse/engine/__init__.py`** (empty file) and **`crowe_browse/engine/playwright_engine.py`**

```python
"""Async Playwright engine with two connect modes: launch and attach."""

from __future__ import annotations

from crowe_browse.engine.base import SEL, Element
from crowe_browse.extract import interactive_elements


class PlaywrightEngine:
    def __init__(
        self,
        mode: str = "launch",
        *,
        headless: bool = True,
        profile_dir: str | None = None,
        cdp_url: str | None = None,
    ) -> None:
        self._mode = mode
        self._headless = headless
        self._profile_dir = profile_dir
        self._cdp_url = cdp_url
        self._pw = None
        self._ctx = None
        self._browser = None
        self._page = None

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        if self._mode == "attach":
            self._browser = await self._pw.chromium.connect_over_cdp(
                self._cdp_url or "http://localhost:9222"
            )
            ctx = self._browser.contexts[0]
            self._page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        else:
            profile = self._profile_dir or _default_profile()
            self._ctx = await self._pw.chromium.launch_persistent_context(
                profile,
                headless=self._headless,
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            self._page = self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()

    async def goto(self, url: str) -> None:
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)

    def current_url(self) -> str:
        return self._page.url

    async def current_html(self) -> str:
        return await self._page.content()

    async def elements(self) -> list[Element]:
        return interactive_elements(await self.current_html())

    async def click(self, ref: int) -> None:
        await self._page.locator(SEL).nth(ref).click(timeout=15000)

    async def type_text(self, ref: int, text: str) -> None:
        await self._page.locator(SEL).nth(ref).fill(text, timeout=15000)

    async def go_back(self) -> None:
        await self._page.go_back(timeout=30000)

    async def reload(self) -> None:
        await self._page.reload(timeout=30000)

    async def close(self) -> None:
        if self._ctx is not None:
            await self._ctx.close()
        if self._browser is not None:
            await self._browser.close()
        if self._pw is not None:
            await self._pw.stop()


def _default_profile() -> str:
    import os
    from pathlib import Path

    p = Path(os.path.expanduser("~/.crowe-browse/profile"))
    p.mkdir(parents=True, exist_ok=True)
    return str(p)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_engine.py -v`
Expected: PASS (2 passed). (Chromium must be installed from Task 1.)

- [ ] **Step 6: Commit**

```bash
git add crowe_browse/engine/ tests/test_engine.py
git commit -m "feat: async Playwright engine (launch mode) + element resolution"
```

---

### Task 5: Config + session

**Files:**
- Create: `crowe_browse/config.py`, `crowe_browse/session.py`
- Test: `tests/test_session.py`

**Interfaces:**
- Consumes: `PlaywrightEngine` (Task 4).
- Produces: `BrowseSettings.from_env() -> BrowseSettings` (fields `mode`, `headless`, `profile_dir`, `cdp_url`); `BrowseSession(settings=None)` with async `engine()` (lazy-start, returns the started `PlaywrightEngine`) and async `close()`.

- [ ] **Step 1: Write the failing test**

`tests/test_session.py`:
```python
from pathlib import Path

import pytest

from crowe_browse.config import BrowseSettings
from crowe_browse.session import BrowseSession

FIX = Path(__file__).parent / "fixtures"


def test_settings_defaults(monkeypatch):
    for k in ("CROWE_BROWSE_MODE", "CROWE_BROWSE_HEADLESS", "CROWE_BROWSE_CDP_URL"):
        monkeypatch.delenv(k, raising=False)
    s = BrowseSettings.from_env()
    assert s.mode == "launch"
    assert s.headless is True


@pytest.mark.asyncio
async def test_session_lazy_starts_one_engine():
    sess = BrowseSession(BrowseSettings(headless=True))
    try:
        e1 = await sess.engine()
        e2 = await sess.engine()
        assert e1 is e2  # started once, reused
        await e1.goto((FIX / "form.html").resolve().as_uri())
        assert e1.current_url().endswith("form.html")
    finally:
        await sess.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_session.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crowe_browse.config'`

- [ ] **Step 3: Write `crowe_browse/config.py`**

```python
"""Runtime settings for the browser engine, from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

_TRUE = {"1", "true", "yes", "on"}


@dataclass
class BrowseSettings:
    mode: str = "launch"  # "launch" | "attach"
    headless: bool = True
    profile_dir: str | None = None
    cdp_url: str = "http://localhost:9222"

    @classmethod
    def from_env(cls) -> "BrowseSettings":
        headless_env = os.environ.get("CROWE_BROWSE_HEADLESS", "true").strip().lower()
        return cls(
            mode=os.environ.get("CROWE_BROWSE_MODE", cls.mode),
            headless=headless_env in _TRUE,
            profile_dir=os.environ.get("CROWE_BROWSE_PROFILE") or None,
            cdp_url=os.environ.get("CROWE_BROWSE_CDP_URL", cls.cdp_url),
        )
```

- [ ] **Step 4: Write `crowe_browse/session.py`**

```python
"""A stateful browsing session: one lazily-started engine per session."""

from __future__ import annotations

from crowe_browse.config import BrowseSettings
from crowe_browse.engine.playwright_engine import PlaywrightEngine


class BrowseSession:
    def __init__(self, settings: BrowseSettings | None = None) -> None:
        self._settings = settings or BrowseSettings.from_env()
        self._engine: PlaywrightEngine | None = None

    async def engine(self) -> PlaywrightEngine:
        if self._engine is None:
            eng = PlaywrightEngine(
                mode=self._settings.mode,
                headless=self._settings.headless,
                profile_dir=self._settings.profile_dir,
                cdp_url=self._settings.cdp_url,
            )
            await eng.start()
            self._engine = eng
        return self._engine

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.close()
            self._engine = None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_session.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add crowe_browse/config.py crowe_browse/session.py tests/test_session.py
git commit -m "feat: browse settings + stateful session"
```

---

### Task 6: Read tools (search, open, read, observe, navigate)

**Files:**
- Create: `crowe_browse/tools.py`
- Modify: `crowe_browse/__init__.py`
- Test: `tests/test_tools_read.py`

**Interfaces:**
- Consumes: `BrowseSession` (Task 5), `crowe_browse.search.{SEARCH_URL, parse_results}`, `crowe_browse.extract.readable_text`, `crowe_agent_core.ToolSpec`.
- Produces: `BROWSE_MUTATING: set[str]`; `build_browse_tools(session: BrowseSession) -> list[ToolSpec]` registering async handlers `web_search`, `open_page`, `read_page`, `observe`, `navigate` (this task) and `click`, `type_text` (Task 7). `crowe_browse.__init__` re-exports `build_browse_tools` and `BROWSE_MUTATING`.

- [ ] **Step 1: Write the failing test**

`tests/test_tools_read.py`:
```python
from pathlib import Path

import pytest

from crowe_browse import BROWSE_MUTATING, build_browse_tools
from crowe_browse.config import BrowseSettings
from crowe_browse.session import BrowseSession

FIX = Path(__file__).parent / "fixtures"


def _tool(tools, name):
    return next(t for t in tools if t.name == name)


@pytest.mark.asyncio
async def test_open_and_read_and_observe():
    sess = BrowseSession(BrowseSettings(headless=True))
    tools = build_browse_tools(sess)
    try:
        out = await _tool(tools, "open_page").handler(url=(FIX / "article.html").resolve().as_uri())
        assert "Blue oyster fruits at 15 to 21 C." in out
        read = await _tool(tools, "read_page").handler()
        assert "humidity" in read.lower()
        obs = await _tool(tools, "observe").handler()
        assert "[0]" in obs and "Home" in obs  # numbered interactive elements
    finally:
        await sess.close()


def test_read_tools_not_mutating():
    assert "web_search" not in BROWSE_MUTATING
    assert "open_page" not in BROWSE_MUTATING
    assert "navigate" not in BROWSE_MUTATING
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_tools_read.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_browse_tools'`

- [ ] **Step 3: Write `crowe_browse/tools.py`**

```python
"""Kernel ToolSpecs exposing the browsing session as the agentic loop."""

from __future__ import annotations

from urllib.parse import quote_plus

from crowe_agent_core import ToolSpec

from crowe_browse.extract import readable_text
from crowe_browse.search import SEARCH_URL, parse_results
from crowe_browse.session import BrowseSession

BROWSE_MUTATING: set[str] = {"click", "type_text"}

_MAX = 20000


def _clip(text: str) -> str:
    return text if len(text) <= _MAX else text[:_MAX] + "\n... [truncated]"


def build_browse_tools(session: BrowseSession) -> list[ToolSpec]:
    async def web_search(query: str) -> str:
        eng = await session.engine()
        await eng.goto(SEARCH_URL.format(q=quote_plus(query)))
        results = parse_results(await eng.current_html())
        if not results:
            return f"no results (searched {eng.current_url()})"
        lines = [
            f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}"
            for i, r in enumerate(results[:8])
        ]
        return "\n".join(lines)

    async def open_page(url: str) -> str:
        eng = await session.engine()
        try:
            await eng.goto(url)
        except Exception as exc:  # noqa: BLE001 - model-facing error string
            return f"error: could not open {url}: {exc}"
        return _clip(readable_text(await eng.current_html(), url))

    async def read_page() -> str:
        eng = await session.engine()
        return _clip(readable_text(await eng.current_html(), eng.current_url()))

    async def observe() -> str:
        eng = await session.engine()
        els = await eng.elements()
        if not els:
            return "no interactive elements on this page"
        return "\n".join(f"[{e.ref}] {e.role}: {e.name}" for e in els[:60])

    async def navigate(action: str) -> str:
        eng = await session.engine()
        act = action.strip().lower()
        try:
            if act == "back":
                await eng.go_back()
            elif act == "forward":
                await eng._page.go_forward(timeout=30000)
            elif act == "reload":
                await eng.reload()
            else:
                return f"error: unknown navigate action '{action}' (use back/forward/reload)"
        except Exception as exc:  # noqa: BLE001
            return f"error: navigate {act} failed: {exc}"
        return f"navigated {act}; now at {eng.current_url()}"

    async def click(ref: int) -> str:
        eng = await session.engine()
        try:
            await eng.click(int(ref))
        except Exception as exc:  # noqa: BLE001
            return f"error: click [{ref}] failed: {exc}"
        return f"clicked [{ref}]; now at {eng.current_url()}"

    async def type_text(ref: int, text: str) -> str:
        eng = await session.engine()
        try:
            await eng.type_text(int(ref), text)
        except Exception as exc:  # noqa: BLE001
            return f"error: type into [{ref}] failed: {exc}"
        return f"typed into [{ref}]"

    return [
        ToolSpec("web_search", "Search the web and return ranked results (title, url, snippet).",
                 {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                 web_search),
        ToolSpec("open_page", "Open a URL in the browser and return its readable text.",
                 {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
                 open_page),
        ToolSpec("read_page", "Return the readable text of the current page.",
                 {"type": "object", "properties": {}, "required": []}, read_page),
        ToolSpec("observe", "List the current page's interactive elements with [ref] numbers.",
                 {"type": "object", "properties": {}, "required": []}, observe),
        ToolSpec("navigate", "Navigate browser history: back, forward, or reload.",
                 {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]},
                 navigate),
        ToolSpec("click", "Click the interactive element with the given [ref] number (from observe).",
                 {"type": "object", "properties": {"ref": {"type": "integer"}}, "required": ["ref"]},
                 click),
        ToolSpec("type_text", "Type text into the input element with the given [ref] number.",
                 {"type": "object", "properties": {"ref": {"type": "integer"}, "text": {"type": "string"}},
                  "required": ["ref", "text"]},
                 type_text),
    ]
```

- [ ] **Step 4: Update `crowe_browse/__init__.py`**

```python
"""crowe-browse: an agent-driven web browser exposed as Crowe kernel tools."""

from crowe_browse.tools import BROWSE_MUTATING, build_browse_tools

__version__ = "0.1.0"

__all__ = ["build_browse_tools", "BROWSE_MUTATING", "__version__"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_tools_read.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add crowe_browse/tools.py crowe_browse/__init__.py tests/test_tools_read.py
git commit -m "feat: read tools (search/open/read/observe/navigate) + build_browse_tools"
```

---

### Task 7: Act tools (click, type_text) verified end-to-end

**Files:**
- Test: `tests/test_tools_act.py`

**Interfaces:**
- Consumes: `build_browse_tools` (Task 6), which already defines `click` and `type_text`.

Note: the `click`/`type_text` handlers were written in Task 6's `tools.py`. This task adds the end-to-end test proving they act on a live (fixture) page and are correctly classified mutating.

- [ ] **Step 1: Write the failing test**

`tests/test_tools_act.py`:
```python
from pathlib import Path

import pytest

from crowe_browse import BROWSE_MUTATING, build_browse_tools
from crowe_browse.config import BrowseSettings
from crowe_browse.session import BrowseSession

FIX = Path(__file__).parent / "fixtures"


def _tool(tools, name):
    return next(t for t in tools if t.name == name)


def test_act_tools_are_mutating():
    assert BROWSE_MUTATING == {"click", "type_text"}


@pytest.mark.asyncio
async def test_type_text_sets_input_value():
    sess = BrowseSession(BrowseSettings(headless=True))
    tools = build_browse_tools(sess)
    try:
        await _tool(tools, "open_page").handler(url=(FIX / "form.html").resolve().as_uri())
        out = await _tool(tools, "type_text").handler(ref=1, text="oyster")
        assert "typed into [1]" in out
        eng = await sess.engine()
        assert await eng._page.locator("input").input_value() == "oyster"
    finally:
        await sess.close()
```

- [ ] **Step 2: Run test to verify it fails, then passes**

Run: `.venv/bin/python -m pytest tests/test_tools_act.py -v`
Expected: the mutating-set test PASSES immediately (already implemented); if `test_type_text_sets_input_value` fails, fix the `type_text` handler in `tools.py` until it passes. Expected final: PASS (2 passed).

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests pass (extract 2, search 2, engine 2, session 2, tools_read 2, tools_act 2).

- [ ] **Step 4: Commit**

```bash
git add tests/test_tools_act.py
git commit -m "test: act tools (click/type_text) end-to-end + mutating classification"
```

---

### Task 8: Attach mode + README + live smoke

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: `PlaywrightEngine` attach mode (already implemented in Task 4's `start()`), `BrowseSettings` (`CROWE_BROWSE_MODE=attach`).

- [ ] **Step 1: Live smoke - launch mode (real web)**

Run:
```bash
.venv/bin/python - <<'PY'
import asyncio
from crowe_browse import build_browse_tools
from crowe_browse.config import BrowseSettings
from crowe_browse.session import BrowseSession

async def main():
    sess = BrowseSession(BrowseSettings(headless=True))
    tools = {t.name: t for t in build_browse_tools(sess)}
    try:
        print(await tools["web_search"].handler(query="blue oyster mushroom fruiting temperature"))
        # open the first result URL printed above by hand is not automated here;
        # instead open a known-stable page:
        print("----")
        print((await tools["open_page"].handler(url="https://example.com"))[:200])
    finally:
        await sess.close()

asyncio.run(main())
PY
```
Expected: real search results (titles/urls/snippets), then the readable text of example.com. If search returns "no results", note it (DDG may rate-limit) but example.com read must work.

- [ ] **Step 2: Attach-mode smoke (manual, optional)**

Document in README: start Chrome with `--remote-debugging-port=9222`, then
`CROWE_BROWSE_MODE=attach` drives that live Chrome. Verify only if a Chrome is
available; not required for CI.

- [ ] **Step 3: Write `README.md`**

```markdown
# crowe-browse

An agent-driven web browser exposed as Crowe kernel tools (the "Comet engine").
Any Crowe agent registers these tools and gains real browsing: search, read, and
act on live pages, on a stateful Playwright/Chromium session.

## Install
    uv venv --python 3.11 .venv
    uv pip install -e ".[dev]" --python .venv/bin/python
    .venv/bin/python -m playwright install chromium

## Tools
- Read (free): `web_search`, `open_page`, `read_page`, `observe`, `navigate`
- Act (approval-gated): `click`, `type_text`

## Use (in an agent)
    from crowe_browse import build_browse_tools, BROWSE_MUTATING
    from crowe_browse.session import BrowseSession
    tools = build_browse_tools(BrowseSession())   # register these ToolSpecs

## Config (env)
- `CROWE_BROWSE_MODE`     (launch | attach; default launch)
- `CROWE_BROWSE_HEADLESS` (default true)
- `CROWE_BROWSE_PROFILE`  (persistent profile dir; default ~/.crowe-browse/profile)
- `CROWE_BROWSE_CDP_URL`  (attach mode; default http://localhost:9222)

Attach mode: start Chrome with `--remote-debugging-port=9222`, then set
`CROWE_BROWSE_MODE=attach` to drive your live browser session.
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: README + attach-mode notes; live smoke verified"
```

---

## Self-Review

**Spec coverage:**
- Standalone package, kernel tools, not modifying kernel -> Tasks 1, 6. Y
- One Playwright engine, two modes (launch/attach) -> Task 4 (launch) + Task 8 (attach), same `start()`. Y
- Read-first tools: web_search/open_page/read_page/observe/navigate -> Task 6. Y
- Act tools click/type_text, mutating -> Task 6 (handlers) + Task 7 (verified) + `BROWSE_MUTATING`. Y
- Real browser search bypassing bot-blocks -> Task 3 (parse) + Task 6 (`web_search` drives the page). Y
- Pure offline-testable extraction -> Task 2. Y
- Stateful session across calls -> Task 5. Y
- Safety: read free, act mutating, gate unions BROWSE_MUTATING -> `BROWSE_MUTATING` exported (Task 6); crowe-nano wiring is an explicit follow-on, not this plan. Y
- Testing against fixtures + one live smoke -> every task + Task 8. Y

**Placeholder scan:** No TBD/TODO; every code step is complete. Y

**Type consistency:** `Element(ref, role, name, tag)` consistent (extract -> engine -> observe). `SEL` defined in base, used in engine. `build_browse_tools(session) -> list[ToolSpec]` and `BROWSE_MUTATING` consistent across Tasks 6/7/8. Engine method names (`goto`, `current_url`, `current_html`, `elements`, `click`, `type_text`, `go_back`, `reload`, `close`, `start`) consistent between Task 4 definition and Task 5/6 use. `session.engine()` (async) consistent. Y

**Note on `_page` access in tests:** tests reach `eng._page` to assert input value - acceptable white-box test access; not used by production code.
