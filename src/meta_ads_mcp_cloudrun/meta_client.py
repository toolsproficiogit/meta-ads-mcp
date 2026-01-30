from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class MetaAPIError(RuntimeError):
    pass


@dataclass
class MetaAdsClient:
    access_token: str
    api_version: str = "v20.0"
    timeout_seconds: float = 30.0

    def _base_url(self) -> str:
        return f"https://graph.facebook.com/{self.api_version}"

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = dict(params or {})
        params["access_token"] = self.access_token

        url = f"{self._base_url()}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url, params=params)

        if resp.status_code >= 400:
            # Meta returns JSON with "error"
            try:
                payload = resp.json()
            except Exception:
                payload = {"raw": resp.text}
            raise MetaAPIError(f"Meta API error {resp.status_code}: {payload}")

        return resp.json()
