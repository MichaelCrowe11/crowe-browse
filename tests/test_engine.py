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
async def test_engine_elements_align_with_shadow_dom():
    # elements() must enumerate via the same locator that click/type_text
    # resolve against, so open-shadow-root elements are seen and ref indices
    # align. A pure page.content() parse would miss the shadow button, causing
    # click(ref) to hit the wrong element.
    eng = PlaywrightEngine(mode="launch", headless=True)
    await eng.start()
    try:
        await eng.goto(_file_url("shadow.html"))
        names = [e.name for e in await eng.elements()]
        assert "LightButton" in names
        assert "ShadowButton" in names  # pierced the open shadow root
    finally:
        await eng.close()


@pytest.mark.asyncio
async def test_engine_type_and_click():
    eng = PlaywrightEngine(mode="launch", headless=True)
    await eng.start()
    try:
        await eng.goto(_file_url("form.html"))
        await eng.type_text(1, "oyster")  # the input is ref 1
        val = await eng._page.locator("input").input_value()
        assert val == "oyster"
        await eng.click(0)  # the first link; navigation may 404 on file://, no raise
    finally:
        await eng.close()
