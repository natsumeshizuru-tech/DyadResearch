from __future__ import annotations

from typing import Any

import pytest

from dyadresearch import web
from dyadresearch.data.xtdata import XtDataBridge


def test_xtdata_bridge_rejects_non_loopback_control_plane() -> None:
    with pytest.raises(ValueError, match="loopback"):
        XtDataBridge("https://example.com/api/v1")


def test_research_xtdata_routes_preserve_tetrade_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeBridge:
        def catalog(self) -> dict[str, Any]:
            return {"source": "xtdata", "datasets": [], "periods": []}

        def download(self, payload: dict[str, Any]) -> dict[str, Any]:
            return {"status": "completed", "request": payload}

    monkeypatch.setattr(web, "_xtdata_bridge", FakeBridge)
    catalog = web.xtdata_catalog()
    assert catalog["source"] == "xtdata"

    response = web.xtdata_download(
        web.XtDataDownloadRequest.model_validate(
            {
                "dataset": "history",
                "symbols": ["000001.sz"],
                "period": "1d",
                "start_date": "20260723",
                "end_date": "20260724",
                "tables": [],
                "import_to_shared_store": True,
            }
        )
    )
    assert response["request"]["symbols"] == ["000001.SZ"]
