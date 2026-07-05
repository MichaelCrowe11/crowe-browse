"""Async Playwright engine with two connect modes: launch and attach."""

from __future__ import annotations

from crowe_browse.engine.base import SEL, Element
from crowe_browse.extract import _ROLE


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
            self._page = (
                self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()
            )

    async def goto(self, url: str) -> None:
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)

    def current_url(self) -> str:
        return self._page.url

    async def current_html(self) -> str:
        return await self._page.content()

    async def elements(self) -> list[Element]:
        # Enumerate via the SAME locator that click/type_text resolve against
        # (page.locator(SEL).nth(ref)), so a ref index maps to exactly the
        # element an action will hit. A pure-HTML parse of page.content()
        # diverges from Playwright's DOM on shadow-root / <template> pages,
        # which would make click(ref) hit the wrong element.
        handles = await self._page.locator(SEL).element_handles()
        out: list[Element] = []
        for i, h in enumerate(handles):
            tag = (await h.evaluate("e => e.tagName")).lower()
            name = await h.evaluate(
                "e => (e.innerText || e.getAttribute('aria-label') || "
                "e.getAttribute('placeholder') || e.value || "
                "e.getAttribute('name') || e.getAttribute('href') || "
                "'').trim().slice(0, 80)"
            )
            out.append(Element(ref=i, role=_ROLE.get(tag, tag), name=name, tag=tag))
        return out

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
