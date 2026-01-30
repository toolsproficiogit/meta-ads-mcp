from meta_ads_mcp_cloudrun.config import Settings


def test_tool_enabled_logic():
    s = Settings(
        api_bearer_token="x",
        meta_access_token="y",
        meta_api_version="v20.0",
        allowed_ad_accounts=set(),
        enabled_tools=set(),
        disabled_tools={"mcp_meta_ads_get_*"},
        request_timeout_seconds=30.0,
    )
    assert not s.is_tool_enabled("mcp_meta_ads_get_campaigns")
    assert s.is_tool_enabled("mcp_meta_ads_list_accounts")
