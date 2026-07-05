"""crowe-browse: an agent-driven web browser exposed as Crowe kernel tools."""

from crowe_browse.tools import BROWSE_MUTATING, build_browse_tools

__version__ = "0.1.0"

__all__ = ["build_browse_tools", "BROWSE_MUTATING", "__version__"]
