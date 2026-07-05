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
        val = await eng._page.locator("input").input_value()
        assert val == "oyster"
        await eng.click(0)  # the first link; navigation may 404 on file://, no raise
    finally:
        await eng.close()
