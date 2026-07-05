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
                return (
                    f"error: unknown navigate action '{action}' "
                    "(use back/forward/reload)"
                )
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
        ToolSpec(
            "web_search",
            "Search the web and return ranked results (title, url, snippet).",
            {"type": "object", "properties": {"query": {"type": "string"}},
             "required": ["query"]},
            web_search,
        ),
        ToolSpec(
            "open_page",
            "Open a URL in the browser and return its readable text.",
            {"type": "object", "properties": {"url": {"type": "string"}},
             "required": ["url"]},
            open_page,
        ),
        ToolSpec(
            "read_page",
            "Return the readable text of the current page.",
            {"type": "object", "properties": {}, "required": []},
            read_page,
        ),
        ToolSpec(
            "observe",
            "List the current page's interactive elements with [ref] numbers.",
            {"type": "object", "properties": {}, "required": []},
            observe,
        ),
        ToolSpec(
            "navigate",
            "Navigate browser history: back, forward, or reload.",
            {"type": "object", "properties": {"action": {"type": "string"}},
             "required": ["action"]},
            navigate,
        ),
        ToolSpec(
            "click",
            "Click the interactive element with the given [ref] number (from observe).",
            {"type": "object", "properties": {"ref": {"type": "integer"}},
             "required": ["ref"]},
            click,
        ),
        ToolSpec(
            "type_text",
            "Type text into the input element with the given [ref] number.",
            {"type": "object", "properties": {"ref": {"type": "integer"},
             "text": {"type": "string"}}, "required": ["ref", "text"]},
            type_text,
        ),
    ]
