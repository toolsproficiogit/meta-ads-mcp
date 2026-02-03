from __future__ import annotations

from typing import Any, Dict, Optional

from ..config import Settings
from ..meta_client import MetaAdsClient


def _paginate_params(limit: int, after: Optional[str]) -> Dict[str, Any]:
    params: Dict[str, Any] = {"limit": limit}
    if after:
        params["after"] = after
    return params


def register_read_tools(mcp, settings: Settings) -> None:
    client = MetaAdsClient(
        access_token=settings.meta_access_token,
        api_version=settings.meta_api_version,
        timeout_seconds=settings.request_timeout_seconds,
    )

    def guard(tool_name: str, account_id: Optional[str] = None) -> None:
        if not settings.is_tool_enabled(tool_name):
            raise PermissionError(f"Tool '{tool_name}' is disabled by server configuration")
        if account_id:
            settings.assert_account_allowed(account_id)

    @mcp.tool(
        name="mcp_meta_ads_list_accounts",
        description="List ad accounts accessible by the System User token (server-side).",
    )
    async def list_accounts(limit: int = 25, after: Optional[str] = None) -> Dict[str, Any]:
        tool = "mcp_meta_ads_list_accounts"
        guard(tool)
        # /me/adaccounts returns ad account nodes. Request a small, safe field set.
        params = _paginate_params(limit, after)
        params["fields"] = "id,account_id,name,account_status,currency,timezone_name,business,owner"
        resp = await client.get("/me/adaccounts", params=params)

        # Server-level allowlist: if ALLOWED_AD_ACCOUNTS is set, filter the listing too.
        # (Otherwise callers could discover accounts via list and then get blocked later.)
        if settings.allowed_ad_accounts and isinstance(resp, dict) and isinstance(resp.get("data"), list):
            allowed = settings.allowed_ad_accounts
            resp["data"] = [
                node
                for node in resp["data"]
                if isinstance(node, dict)
                and (
                    (node.get("id") in allowed)
                    or (node.get("account_id") in allowed)
                    or (f"act_{node.get('account_id')}" in allowed if node.get("account_id") else False)
                )
            ]
        return resp

    @mcp.tool(
        name="mcp_meta_ads_get_account",
        description="Get details about a specific Meta ad account (act_XXXXXXXXX).",
    )
    async def get_account(account_id: str) -> Dict[str, Any]:
        tool = "mcp_meta_ads_get_account"
        guard(tool, account_id=account_id)
        fields = ",".join(
            [
                "id",
                "account_id",
                "name",
                "account_status",
                "currency",
                "timezone_name",
                "timezone_offset_hours_utc",
                "business",
                "owner",
                "amount_spent",
                "spend_cap",
            ]
        )
        return await client.get(f"/{account_id}", params={"fields": fields})

    @mcp.tool(
        name="mcp_meta_ads_get_campaigns",
        description="Get campaigns for an ad account, optionally filtered by effective status.",
    )
    async def get_campaigns(
        account_id: str,
        limit: int = 25,
        after: Optional[str] = None,
        effective_status: Optional[str] = None,  # e.g. ACTIVE, PAUSED
    ) -> Dict[str, Any]:
        tool = "mcp_meta_ads_get_campaigns"
        guard(tool, account_id=account_id)

        params = _paginate_params(limit, after)
        params["fields"] = "id,name,status,effective_status,objective,created_time,updated_time"
        if effective_status:
            # Meta expects an array-like string for filtering; keep simple for common cases.
            params["effective_status"] = f'["{effective_status}"]'
        return await client.get(f"/{account_id}/campaigns", params=params)

    @mcp.tool(
        name="mcp_meta_ads_get_campaign_details",
        description="Get detailed information about a campaign by campaign_id.",
    )
    async def get_campaign_details(campaign_id: str) -> Dict[str, Any]:
        tool = "mcp_meta_ads_get_campaign_details"
        guard(tool)
        fields = ",".join(
            [
                "id",
                "name",
                "status",
                "effective_status",
                "objective",
                "special_ad_categories",
                "buying_type",
                "created_time",
                "updated_time",
                "start_time",
                "stop_time",
                "daily_budget",
                "lifetime_budget",
            ]
        )
        return await client.get(f"/{campaign_id}", params={"fields": fields})

    @mcp.tool(
        name="mcp_meta_ads_get_adsets",
        description="Get ad sets for an ad account, optionally filtered by campaign_id.",
    )
    async def get_adsets(
        account_id: str,
        limit: int = 25,
        after: Optional[str] = None,
        campaign_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        tool = "mcp_meta_ads_get_adsets"
        guard(tool, account_id=account_id)

        params = _paginate_params(limit, after)
        params["fields"] = "id,name,status,effective_status,campaign_id,daily_budget,lifetime_budget,optimization_goal,billing_event,start_time,end_time"
        if campaign_id:
            params["filtering"] = f'[{{"field":"campaign.id","operator":"EQUAL","value":"{campaign_id}"}}]'
        return await client.get(f"/{account_id}/adsets", params=params)

    @mcp.tool(
        name="mcp_meta_ads_get_ads",
        description="Get ads for an ad account, optionally filtered by campaign_id and/or adset_id.",
    )
    async def get_ads(
        account_id: str,
        limit: int = 25,
        after: Optional[str] = None,
        campaign_id: Optional[str] = None,
        adset_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        tool = "mcp_meta_ads_get_ads"
        guard(tool, account_id=account_id)

        params = _paginate_params(limit, after)
        params["fields"] = "id,name,status,effective_status,adset_id,campaign_id,created_time,updated_time,creative"
        filters = []
        if campaign_id:
            filters.append(f'{{"field":"campaign.id","operator":"EQUAL","value":"{campaign_id}"}}')
        if adset_id:
            filters.append(f'{{"field":"adset.id","operator":"EQUAL","value":"{adset_id}"}}')
        if filters:
            params["filtering"] = "[" + ",".join(filters) + "]"
        return await client.get(f"/{account_id}/ads", params=params)

    @mcp.tool(
        name="mcp_meta_ads_get_ad_details",
        description="Get detailed information about a specific ad by ad_id.",
    )
    async def get_ad_details(ad_id: str) -> Dict[str, Any]:
        tool = "mcp_meta_ads_get_ad_details"
        guard(tool)
        fields = ",".join(
            [
                "id",
                "name",
                "status",
                "effective_status",
                "campaign_id",
                "adset_id",
                "created_time",
                "updated_time",
                "tracking_specs",
                "creative{object_story_spec,asset_feed_spec,link_url,page_id,instagram_actor_id,call_to_action_type}",
            ]
        )
        return await client.get(f"/{ad_id}", params={"fields": fields})

    @mcp.tool(
        name="mcp_meta_ads_get_insights",
        description="Get performance insights for an ad account/campaign/adset/ad. Supports date_preset or explicit time_range.",
    )
    async def get_insights(
        object_id: str,
        level: str = "campaign",  # account, campaign, adset, ad
        date_preset: Optional[str] = "last_30d",
        time_range_json: Optional[str] = None,  # e.g. {"since":"2025-01-01","until":"2025-01-31"}
        fields: str = "impressions,clicks,spend,ctr,cpc,cpm,actions,action_values,purchase_roas",
        limit: int = 100,
        after: Optional[str] = None,
    ) -> Dict[str, Any]:
        tool = "mcp_meta_ads_get_insights"
        # object_id might be act_... or a campaign/adset/ad id. Only enforce allowlist if it's an act_*
        if object_id.startswith("act_"):
            guard(tool, account_id=object_id)
        else:
            guard(tool)

        params = _paginate_params(limit, after)
        params["level"] = level
        params["fields"] = fields

        if time_range_json:
            params["time_range"] = time_range_json
            params.pop("date_preset", None)
        elif date_preset:
            params["date_preset"] = date_preset

        return await client.get(f"/{object_id}/insights", params=params)
