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
