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
        await _tool(tools, "open_page").handler(
            url=(FIX / "form.html").resolve().as_uri()
        )
        out = await _tool(tools, "type_text").handler(ref=1, text="oyster")
        assert "typed into [1]" in out
        eng = await sess.engine()
        assert await eng._page.locator("input").input_value() == "oyster"
    finally:
        await sess.close()
