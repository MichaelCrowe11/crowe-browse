# crowe-browse — Phase 1 design (the Comet engine)

**Date:** 2026-07-05
**Status:** approved, pre-implementation

## Purpose

A standalone Python package that gives any Crowe agent (crowe-nano, crowe-logic)
a real, stateful, agent-driven web browser exposed as kernel tools: search,
read, and act on live pages. It is the "engine" that a later browser *app*
(Phase 2, its own spec) will wrap.

**Why a browser and not a search API:** search APIs are dead or bot-blocked
(Perplexity retired; DuckDuckGo's JSON API returns bot/anomaly pages under agent
load; Google blocks scraping). A real rendered browser with a realistic profile
reads a live results page the way a human does, sidestepping all of it. This is
the whole point of "build our own Comet."

**Success criteria:**
- A Crowe agent can `web_search`, `open_page`, `read_page`, and `observe` live
  web content, and `click` / `type_text` / `navigate` to act on it, across a
  single stateful browser session.
- Read tools run freely; act tools are gated as mutating by the agent's
  approval gate.
- The engine runs headless anywhere (including the Pro) in launch mode, and can
  attach to the user's real Chrome in attach mode.
- crowe-nano's broken `web_search` is replaced by the real browser-driven one.

## Non-goals (YAGNI / later phases)

- No browser *app* (tabs UI, sidebar, Electron shell) — that is Phase 2.
- No multi-tab management in v1 (single current page). Multi-tab is later.
- No download/file-handling, no video/canvas interaction, no CAPTCHA solving.
- No per-domain policy engine (e.g. "never act on banking") in v1 — the approval
  gate on act tools is the v1 control.
- No visual/screenshot-based acting in v1 (act by element ref, not pixels).

## Architecture

New repo `~/Projects/crowe-browse`. Python 3.11, `uv`-managed venv. The kernel
(`crowe-agent-core`) is a local editable path dependency and is NOT modified.

```
crowe-browse/
  pyproject.toml            # deps: crowe-agent-core, playwright
  crowe_browse/
    __init__.py             # build_browse_tools(session) + BROWSE_MUTATING
    config.py               # BrowseSettings from env (mode, profile dir, cdp url, headless)
    engine/
      base.py               # BrowserEngine interface + Element dataclass
      playwright_engine.py  # Playwright Chromium: launch OR attach (connect_over_cdp)
    extract.py              # rendered DOM -> readable text; DOM -> interactive elements
    search.py               # drive a results page, parse title/url/snippet
    session.py              # BrowseSession: holds engine + current page state
    tools.py                # ToolSpecs (the agentic loop) + MUTATING classification
  tests/
    fixtures/               # static HTML pages (deterministic, no live network)
    test_extract.py
    test_engine.py
    test_search.py
    test_tools.py
  docs/superpowers/specs/2026-07-05-crowe-browse-design.md
```

### Modules

**config.py** — `BrowseSettings` from env with defaults:
- `CROWE_BROWSE_MODE` (`launch` default | `attach`).
- `CROWE_BROWSE_HEADLESS` (default true).
- `CROWE_BROWSE_PROFILE` (default `~/.crowe-browse/profile`) — persistent context
  dir for cookies / logged-in state in launch mode.
- `CROWE_BROWSE_CDP_URL` (default `http://localhost:9222`) — for attach mode.

**engine/base.py** — `BrowserEngine` interface (sync-facing, driven from the
tools) and an `Element` dataclass (`ref: int`, `role: str`, `name: str`,
`tag: str`). Methods: `start()`, `goto(url) -> None`, `current_url() -> str`,
`current_html() -> str`, `elements() -> list[Element]`, `click(ref: int)`,
`type_text(ref: int, text: str)`, `go_back()`, `reload()`, `close()`.

**engine/playwright_engine.py** — the one engine, two connect modes:
- `launch`: `playwright.chromium.launch_persistent_context(profile_dir,
  headless=...)` with a realistic user agent — own Chromium + persistent Crowe
  profile.
- `attach`: `playwright.chromium.connect_over_cdp(cdp_url)` against a Chrome the
  user started with `--remote-debugging-port`. Same Playwright page API after
  connect, so the rest of the engine is identical.
`elements()` delegates to `extract.interactive_elements(current_html())` (one
enumerator, offline-testable), assigning stable `ref` ids; `click(ref)` /
`type_text(ref)` resolve a `ref` to a concrete Playwright locator (the nth
matching link/button/input) to perform the action.

**extract.py** — pure functions over HTML (no browser needed, so unit-testable
against fixtures):
- `readable_text(html, url) -> str`: strip nav/script/style/ads; return main
  article/body text (Reader-mode heuristic: largest text-dense container).
- `interactive_elements(html) -> list[Element]`: enumerate links/buttons/inputs
  with role/name for `observe`.

**search.py** — `parse_results(html) -> list[dict]` (title, url, snippet) for the
chosen results page (DuckDuckGo HTML endpoint `html.duckduckgo.com/html/`, Bing
fallback). Pure parse function, tested against a captured results-page fixture.
The tool drives the engine to the results URL, then calls `parse_results`.

**session.py** — `BrowseSession`: lazily starts one engine (per config), tracks
the current page, and is the object the tools close over. `close()` shuts the
engine. One session = one browsing context for an agent run.

**tools.py** — kernel `ToolSpec`s closing over a `BrowseSession`:
- read / navigation (free): `web_search(query)`, `open_page(url)`,
  `read_page()`, `observe()`, `navigate(action)` where action in
  {back, forward, reload} (navigation is a GET/history move, not remote
  mutation).
- act (mutating): `click(ref)`, `type_text(ref, text)` — interacting with page
  controls, which can submit forms or trigger site actions.
`BROWSE_MUTATING = {"click", "type_text"}` — the single source of truth an
approval gate unions in.

**__init__.py** — `build_browse_tools(session) -> list[ToolSpec]` and the
`BROWSE_MUTATING` export.

## Data flow

```
agent -> web_search("q")  -> session.engine.goto(results_url)
                          -> extract via search.parse_results -> ranked results text
agent -> open_page(url)   -> engine.goto(url) -> extract.readable_text -> text
agent -> observe()        -> engine.elements() -> numbered interactive list
agent -> click(ref=3)     -> [approval gate: mutating -> y/n] -> engine.click(3)
agent -> read_page()      -> extract.readable_text(engine.current_html())
```

The session persists across tool calls, so a multi-step flow (search -> open ->
observe -> click -> read) works as one continuous browsing session.

## Safety

- Read / navigation tools (`web_search`, `open_page`, `read_page`, `observe`,
  `navigate`) do not change remote state -> run freely.
- Act tools (`click`, `type_text`) can submit forms / trigger actions on live
  sites -> classified in `BROWSE_MUTATING`. The consuming
  agent's approval gate (e.g. crowe-nano's `ApprovalGate`) unions `BROWSE_MUTATING`
  into its mutating set and prompts y/n before each act, exactly like a file
  write. `--auto` bypasses, same as file tools.
- The sensitive-path blocklist does not apply to URLs; a per-domain policy is a
  deliberate later addition, not v1.

## Error handling

- Engine start failure (no Chromium / no CDP endpoint) -> one clear tool-facing
  error string ("browser engine unavailable: ..."), never a traceback into the
  agent loop.
- Navigation timeout / bad URL -> the tool returns an "error: ..." string the
  model can react to (kernel wraps tool exceptions anyway).
- Empty/blocked search results -> return "no results" plus the results URL, so
  the agent can fall back to opening a site directly.

## Testing

- `test_extract.py`: `readable_text` and `interactive_elements` over static HTML
  fixtures (article page, form page) — no browser, no network.
- `test_search.py`: `parse_results` over a captured results-page fixture.
- `test_engine.py`: launch a headless Playwright engine against a `file://`
  fixture page; assert `goto`, `elements`, `click`, `type_text`, `read` work
  deterministically offline.
- `test_tools.py`: the ToolSpecs against a `BrowseSession` bound to a fixture
  page; assert read tools return text, act tools are in `BROWSE_MUTATING`, and
  handler param names match schemas.
- One live smoke (manual): `web_search("blue oyster fruiting temperature")` ->
  `open_page(top result)` -> `read_page()` returns real content.

## Install / run

```
cd ~/Projects/crowe-browse
uv venv --python 3.11 .venv
uv pip install -e . --python .venv/bin/python
.venv/bin/python -m playwright install chromium   # ~150 MB (disk: Air ~4.5 GB free, feasible)
```

Integration (follow-on, not this spec): crowe-nano imports `build_browse_tools`,
registers them (replacing its keyless `web_search`), and unions `BROWSE_MUTATING`
into its `ApprovalGate`.

## Rollout (build order)

1. Scaffold + pyproject + kernel dep; `playwright install chromium`.
2. `extract.py` (pure) + tests.
3. `search.py` parse (pure) + test.
4. `engine/base.py` + `playwright_engine.py` (launch mode) + offline fixture test.
5. `session.py` + read tools (`web_search`, `open_page`, `read_page`, `observe`)
   -> first working milestone (research capability).
6. Act tools (`click`, `type_text`, `navigate`) + `BROWSE_MUTATING` + tests.
7. Attach mode (`connect_over_cdp`) on the engine.
8. Live smoke; then (separate) wire into crowe-nano.
