from __future__ import annotations

from pathlib import Path

import pytest

from dyadresearch.config import DataConfig
from dyadresearch.data.capabilities import capability_matrix
from dyadresearch.data.catalog import CatalogReader
from dyadresearch.data.financial import FinancialReader
from dyadresearch.data.query import MarketDataReader
from dyadresearch.demo import generate_sample_data
from dyadresearch.web import data_coverage, health, reference_index_weights, reference_sectors


def test_synthetic_demo_is_deterministic_and_queryable(tmp_path: Path) -> None:
    first = generate_sample_data(tmp_path)
    second = generate_sample_data(tmp_path)

    assert first["classification"] == "SYNTHETIC DATA"
    assert first["orders_sent"] == 0
    assert second["generated"] is False
    config = DataConfig(tmp_path)
    bars = MarketDataReader(config).query_bars(
        ["000001.SZ", "510300.SH"],
        period="1d",
        start=20240102,
        end=20240325,
    )
    assert len(bars.bars) == 120
    assert all(bar.source == "SYNTHETIC" for bar in bars.bars)
    capabilities = capability_matrix(tmp_path)
    assert capabilities[0]["available_to"] == 20240325
    assert "SYNTHETIC" in str(capabilities[0]["reason"])
    assert CatalogReader(config).corporate_actions(["510300.SH"], 20240101, 20240331)
    financials = FinancialReader(config).as_of(
        ["000001.SZ"], table_names=["Income"], as_of_date=20240229
    )
    assert financials[0].values["classification"] == "SYNTHETIC"


def test_demo_refuses_to_overwrite_unmarked_databases(tmp_path: Path) -> None:
    (tmp_path / "catalog.db").write_bytes(b"private")

    with pytest.raises(ValueError, match="refusing to overwrite"):
        generate_sample_data(tmp_path, overwrite=True)


def test_demo_schema_supports_public_data_endpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "sample"
    generate_sample_data(data_root)
    config = tmp_path / "research.yaml"
    config.write_text(
        "\n".join(
            (
                "project:",
                "  name: SyntheticTest",
                "  timezone: Asia/Shanghai",
                "data:",
                f"  root: {data_root.as_posix()}",
                "  readonly: true",
                "research:",
                f"  database: {(tmp_path / 'research.db').as_posix()}",
                f"  reports_root: {(tmp_path / 'reports').as_posix()}",
                "backtest:",
                "  policy: strict_research",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DYADRESEARCH_CONFIG", str(config))

    health_payload = health()
    coverage = data_coverage()

    assert health_payload["ok"] is True
    assert health_payload["data_through"] == 20240325
    assert sum(int(item["rows"]) for item in coverage["market_data"]) == 300
    assert coverage["references"]["sectors"]["snapshot_rows"] == 2
    assert reference_sectors(limit=100)["snapshot_date"] == 20240325
    assert reference_index_weights(limit=100)["snapshot_date"] == 20240325
