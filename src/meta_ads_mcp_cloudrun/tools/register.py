from __future__ import annotations

from meta_ads_mcp_cloudrun.config import Settings
from meta_ads_mcp_cloudrun.tools.read_tools import register_read_tools


def register_all_tools(mcp, settings: Settings) -> None:
    # Currently only read tools exist. This wrapper keeps future structure stable.
    register_read_tools(mcp, settings)


__all__ = ["register_all_tools", "register_read_tools"]
