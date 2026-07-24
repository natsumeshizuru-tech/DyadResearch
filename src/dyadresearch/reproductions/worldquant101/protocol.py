from __future__ import annotations

from dyadresearch.config import ResearchConfig
from dyadresearch.reproductions.paper_runner import run_paper_protocol


def run(config: ResearchConfig, protocol: str, *, output_root: str) -> dict[str, object]:
    return run_paper_protocol(
        config,
        "worldquant101",
        protocol,
        output_root=output_root,
    )
