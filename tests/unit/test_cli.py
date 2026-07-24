from pathlib import Path

from dyadresearch.cli import main


def test_cli_lists_factors_and_backtests(project_root: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(project_root)
    assert main(["factor", "list"]) == 0
    assert "momentum_20" in capsys.readouterr().out
    assert main(["backtest", "list"]) == 0
    assert "strict_research" in capsys.readouterr().out


def test_cli_data_query_and_expected_error(project_root: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(project_root)
    code = main(
        [
            "data",
            "query",
            "--symbols",
            "000001.SZ",
            "--period",
            "1d",
            "--start",
            "20240102",
            "--end",
            "20240105",
            "--limit",
            "1",
        ]
    )
    assert code == 0
    assert '"rows"' in capsys.readouterr().out
    code = main(
        [
            "data",
            "query",
            "--symbols",
            "000001.SZ",
            "--period",
            "1m",
            "--start",
            "20240102",
            "--end",
            "20240105",
        ]
    )
    assert code == 2
    assert "truthful local coverage" in capsys.readouterr().err


def test_cli_factor_backtest_reproduce_compare_report(
    project_root: Path, tmp_path: Path, capsys, monkeypatch
) -> None:
    config = tmp_path / "research.yaml"
    source_config = project_root / "config/research.yaml"
    if not source_config.is_file():
        source_config = project_root / "config/research.example.yaml"
    config.write_text(
        source_config.read_text(encoding="utf-8")
        .replace("database: ./var/research.db", f"database: {tmp_path.as_posix()}/research.db")
        .replace("database: research.db", f"database: {tmp_path.as_posix()}/research.db")
        .replace(
            "reports_root: ./var/reports",
            f"reports_root: {tmp_path.as_posix()}/reports",
        )
        .replace(
            "reports_root: reports/generated",
            f"reports_root: {tmp_path.as_posix()}/reports",
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(project_root)
    common = [
        "--config",
        str(config),
        "--symbols",
        "000001.SZ",
        "--period",
        "1d",
        "--start",
        "20240102",
        "--end",
        "20240215",
    ]
    factor_args = [common[0], common[1], "factor", "run", "--name", "momentum_20", *common[2:]]
    assert main(factor_args) == 0
    factor_output = capsys.readouterr().out
    assert '"kind": "factor"' in factor_output
    backtest_args = [
        common[0],
        common[1],
        "backtest",
        "run",
        "--strategy",
        "buy_and_hold",
        *common[2:],
    ]
    assert main(backtest_args) == 0
    backtest_output = capsys.readouterr().out
    assert '"kind": "backtest"' in backtest_output
    import json

    identifier = json.loads(backtest_output)["id"]
    assert main(["--config", str(config), "experiment", "reproduce", str(identifier)]) == 0
    assert '"same_result_hash": true' in capsys.readouterr().out
    assert (
        main(
            [
                "--config",
                str(config),
                "experiment",
                "compare",
                str(identifier),
                str(identifier),
            ]
        )
        == 0
    )
    assert '"same_result": true' in capsys.readouterr().out
    assert main(["--config", str(config), "report", "build", "--id", str(identifier)]) == 0
    assert '"html"' in capsys.readouterr().out
