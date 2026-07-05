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
