from pathlib import Path

import pytest

from dyadresearch.config import ResearchConfig, load_config
from dyadresearch.demo import generate_sample_data


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def public_sample_data(project_root: Path) -> None:
    if not (project_root / "config/research.yaml").is_file():
        config = load_config(project_root / "config/research.example.yaml")
        generate_sample_data(config.data.root)


@pytest.fixture(scope="session")
def real_config(project_root: Path) -> ResearchConfig:
    private = project_root / "config/research.yaml"
    config = load_config(
        private if private.is_file() else project_root / "config/research.example.yaml"
    )
    if not (config.data.root / config.data.catalog).is_file():
        generate_sample_data(config.data.root)
    return config
