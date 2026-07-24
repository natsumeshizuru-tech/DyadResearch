from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any


def export_site(output: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "mkdocs",
            "build",
            "--strict",
            "--site-dir",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"MkDocs build failed: {detail}")
    return {
        "ok": True,
        "output": str(output.resolve()),
        "stdout": completed.stdout.strip(),
    }
