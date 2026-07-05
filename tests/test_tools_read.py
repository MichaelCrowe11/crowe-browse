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
        out = await _tool(tools, "open_page").handler(
            url=(FIX / "article.html").resolve().as_uri()
        )
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
