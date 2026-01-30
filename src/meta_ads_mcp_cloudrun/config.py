from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Set


def _csv_set(value: str | None) -> Set[str]:
    if not value:
        return set()
    return {v.strip() for v in value.split(",") if v.strip()}


@dataclass(frozen=True)
class Settings:
    # MCP (client) authentication (Bearer)
    api_bearer_token: str | None

    # Meta auth (server-side). Use a System User token (long-lived).
    meta_access_token: str
    meta_api_version: str

    # Security controls
    allowed_ad_accounts: Set[str]  # e.g. {"act_123", "act_456"} or empty=set() for allow all
    enabled_tools: Set[str]        # if non-empty, only these tools are enabled
    disabled_tools: Set[str]       # always disabled (takes precedence)

    # HTTP behavior
    request_timeout_seconds: float

    @staticmethod
    def from_env() -> "Settings":
        meta_token = os.getenv("META_ACCESS_TOKEN")
        if not meta_token:
            raise RuntimeError("META_ACCESS_TOKEN is required")

        return Settings(
            api_bearer_token=os.getenv("API_BEARER_TOKEN"),
            meta_access_token=meta_token,
            meta_api_version=os.getenv("META_API_VERSION", "v20.0"),
            allowed_ad_accounts=_csv_set(os.getenv("ALLOWED_AD_ACCOUNTS")),
            enabled_tools=_csv_set(os.getenv("ENABLED_TOOLS")),
            disabled_tools=_csv_set(os.getenv("DISABLED_TOOLS")),
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")),
        )

    def is_tool_enabled(self, tool_name: str) -> bool:
        # Allow simple glob-ish prefix disables by supporting entries like "mcp_meta_ads_get_*"
        def matches(rule: str) -> bool:
            if rule.endswith("*"):
                return tool_name.startswith(rule[:-1])
            return tool_name == rule

        if any(matches(r) for r in self.disabled_tools):
            return False
        if self.enabled_tools and not any(matches(r) for r in self.enabled_tools):
            return False
        return True

    def assert_account_allowed(self, account_id: str) -> None:
        # If allowlist is empty -> allow all
        if not self.allowed_ad_accounts:
            return
        if account_id not in self.allowed_ad_accounts:
            raise PermissionError(
                f"Account '{account_id}' is not allowed by ALLOWED_AD_ACCOUNTS"
            )
