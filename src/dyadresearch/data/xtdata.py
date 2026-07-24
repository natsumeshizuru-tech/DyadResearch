from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from dyadresearch.errors import DyadResearchError


class XtDataBridgeError(DyadResearchError):
    """The local DyadTetrade XtData control plane could not satisfy a request."""


class XtDataBridge:
    def __init__(self, base_url: str | None = None, *, timeout_seconds: int = 330) -> None:
        self.base_url = (
            base_url or os.environ.get("DYADRESEARCH_XTDATA_API") or "http://127.0.0.1:8000/api/v1"
        ).rstrip("/")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
            "127.0.0.1",
            "localhost",
        }:
            raise ValueError("XtData control API must be a loopback HTTP endpoint")
        self.timeout_seconds = timeout_seconds

    def catalog(self) -> dict[str, Any]:
        return self._request("GET", "/market/xtdata/catalog")

    def download(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/market/xtdata/download", payload)

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        encoded = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=encoded, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                value = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("detail")
            except (UnicodeDecodeError, json.JSONDecodeError):
                detail = None
            message = str(detail or f"XtData control API returned {exc.code}")
            raise XtDataBridgeError(message) from exc
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            raise XtDataBridgeError(
                "无法连接 DyadTetrade XtData 控制面; 请确认交易端 API 与 MiniQMT 已启动"
            ) from exc
        if not isinstance(value, dict):
            raise XtDataBridgeError("XtData control API returned an invalid payload")
        return {str(key): item for key, item in value.items()}
