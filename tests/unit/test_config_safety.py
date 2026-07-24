from pathlib import Path

import pytest

from dyadresearch.config import DataConfig
from dyadresearch.errors import ConfigurationError
from dyadresearch.safety import scan_forbidden_imports


def test_data_config_refuses_writable_source(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="readonly"):
        DataConfig(root=tmp_path, readonly=False)


def test_source_has_no_forbidden_imports(project_root: Path) -> None:
    assert scan_forbidden_imports(project_root / "src/dyadresearch") == ()


def test_scanner_reports_forbidden_import(tmp_path: Path) -> None:
    source = tmp_path / "bad.py"
    source.write_text("from xtquant.xttrader import XtQuantTrader\n", encoding="utf-8")
    violations = scan_forbidden_imports(tmp_path)
    assert len(violations) == 2
    assert all(item.line == 1 for item in violations)
