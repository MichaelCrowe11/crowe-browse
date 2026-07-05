# crowe-browse

An agent-driven web browser exposed as Crowe kernel tools (the "Comet engine").
Any Crowe agent registers these tools and gains real browsing: search, read, and
act on live pages, on a stateful Playwright/Chromium session. Phase 1 = the
headless/driven engine; the browser app (tabs + sidebar) is Phase 2.

## Install
    uv venv --python 3.11 .venv
    uv pip install -e ".[dev]" --python .venv/bin/python
    .venv/bin/python -m playwright install chromium

(Headless Chromium needs disk + a real environment. This package is developed and
tested on the Pro node, where Chromium and the full suite run cleanly.)

## Tools
- Read / navigation (free): `web_search`, `open_page`, `read_page`, `observe`, `navigate`
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

## Status (Phase 1)
Verified on the Pro (real Chromium): the engine, `open_page`, `read_page`,
`observe`, `navigate`, `click`, and `type_text` all work end-to-end, including a
live smoke against `example.com`.

Known follow-up: `web_search` drives the DuckDuckGo HTML endpoint, which
bot-blocks / varies its markup under automation (it returned no parseable
results in the live smoke even though the parser is correct on captured markup).
A more bot-resistant search source (a different results page, or handling the
challenge/consent response) is the first Phase-1.5 refinement. All other tools -
and `open_page` on a known URL - are unaffected.
