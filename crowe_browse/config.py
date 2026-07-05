"""Runtime settings for the browser engine, from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

_TRUE = {"1", "true", "yes", "on"}


@dataclass
class BrowseSettings:
    mode: str = "launch"  # "launch" | "attach"
    headless: bool = True
    profile_dir: str | None = None
    cdp_url: str = "http://localhost:9222"

    @classmethod
    def from_env(cls) -> "BrowseSettings":
        headless_env = os.environ.get("CROWE_BROWSE_HEADLESS", "true").strip().lower()
        return cls(
            mode=os.environ.get("CROWE_BROWSE_MODE", cls.mode),
            headless=headless_env in _TRUE,
            profile_dir=os.environ.get("CROWE_BROWSE_PROFILE") or None,
            cdp_url=os.environ.get("CROWE_BROWSE_CDP_URL", cls.cdp_url),
        )
