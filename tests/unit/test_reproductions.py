from __future__ import annotations

from pathlib import Path

import pytest

from dyadresearch.config import BacktestDefaults, DataConfig, ResearchConfig, ResearchPaths
from dyadresearch.demo import generate_sample_data
from dyadresearch.reproductions import run_reproduction


def test_reproduction_is_hashed_repeatable_and_truthfully_classified(
    project_root: Path, tmp_path: Path
) -> None:
    data_root = tmp_path / "data"
    generate_sample_data(data_root)
    config = ResearchConfig(
        name="ReproductionTest",
        timezone="Asia/Shanghai",
        data=DataConfig(data_root),
        research=ResearchPaths(database=tmp_path / "research.db"),
        backtest=BacktestDefaults(),
    )
    spec = project_root / "reproductions" / "specs" / "momentum.yaml"
    output = tmp_path / "reports"

    first = run_reproduction(config, spec, output_root=output)
    second = run_reproduction(config, spec, output_root=output)

    assert first["classification"] == "EXPLORATORY_ONLY"
    assert first["result_hash"] == second["result_hash"]
    report = output / "momentum-synthetic" / "report.html"
    assert "EXPLORATORY_ONLY" in report.read_text(encoding="utf-8")
    json_report = output / "momentum-synthetic" / "report.json"
    assert json_report.is_file()
    assert str(tmp_path) not in json_report.read_text(encoding="utf-8")
    assert (output / "momentum-synthetic" / "metrics.csv").is_file()


def test_synthetic_data_cannot_claim_exact_reproduction(project_root: Path, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    generate_sample_data(data_root)
    config = ResearchConfig(
        name="ReproductionTest",
        timezone="Asia/Shanghai",
        data=DataConfig(data_root),
        research=ResearchPaths(database=tmp_path / "research.db"),
        backtest=BacktestDefaults(),
    )
    original = project_root / "reproductions" / "specs" / "momentum.yaml"
    dishonest = tmp_path / "dishonest.yaml"
    dishonest.write_text(
        original.read_text(encoding="utf-8").replace(
            "classification: EXPLORATORY_ONLY", "classification: EXACT_REPRODUCTION"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="synthetic data cannot support"):
        run_reproduction(config, dishonest, output_root=tmp_path / "reports")
