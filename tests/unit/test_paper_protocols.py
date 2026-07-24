from __future__ import annotations

from pathlib import Path

from dyadresearch.config import BacktestDefaults, DataConfig, ResearchConfig, ResearchPaths
from dyadresearch.demo import generate_sample_data
from dyadresearch.reproductions.paper_runner import run_paper_protocol


def _config(tmp_path: Path) -> ResearchConfig:
    data_root = tmp_path / "data"
    generate_sample_data(data_root)
    return ResearchConfig(
        name="PaperProtocolTest",
        timezone="Asia/Shanghai",
        data=DataConfig(data_root),
        research=ResearchPaths(database=tmp_path / "research.db"),
        backtest=BacktestDefaults(),
    )


def test_formula_validation_is_repeatable_and_persisted(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = run_paper_protocol(
        config,
        "worldquant101",
        "formula-validation",
        output_root=tmp_path / "reports",
    )
    second = run_paper_protocol(
        config,
        "worldquant101",
        "formula-validation",
        output_root=tmp_path / "reports",
    )
    assert first["result_hash"] == second["result_hash"]
    assert first["experiment_id"] == second["experiment_id"]
    assert first["comparability_level"] == "B"
    assert (tmp_path / "reports/worldquant101/wq101_formula_validation/report.json").is_file()


def test_strict_and_original_market_protocols_are_honestly_not_run(tmp_path: Path) -> None:
    config = _config(tmp_path)
    strict = run_paper_protocol(
        config,
        "gtja-short-cycle",
        "paper-strict",
        output_root=tmp_path / "reports",
    )
    original = run_paper_protocol(
        config,
        "worldquant101",
        "original-market",
        output_root=tmp_path / "reports",
    )
    assert strict["status"] == "not_run"
    assert original["status"] == "not_run"
    assert (tmp_path / "reports/gtja_short_cycle/paper_strict/NOT_RUN.md").is_file()
    assert (tmp_path / "reports/worldquant101/wq101_original_market/NOT_RUN.md").is_file()
