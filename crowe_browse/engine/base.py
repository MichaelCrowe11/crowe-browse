"""Browser engine contract. Element is re-exported from extract."""

from __future__ import annotations

from crowe_browse.extract import Element

SEL = "a, button, input, textarea, select"

__all__ = ["Element", "SEL"]
