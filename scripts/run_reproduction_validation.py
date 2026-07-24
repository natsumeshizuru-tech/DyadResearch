from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _pnpm(*arguments: str) -> list[str]:
    executable = shutil.which("pnpm")
    if executable is None and os.name == "nt":
        bundled = (
            Path.home()
            / ".cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm.cmd"
        )
        executable = str(bundled) if bundled.is_file() else None
    if executable is None:
        return ["pnpm", *arguments]
    if os.name == "nt" and executable.lower().endswith((".cmd", ".bat")):
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", executable, *arguments]
    return [executable, *arguments]


COMMANDS = {
    "pytest": [".venv/Scripts/python.exe", "-m", "pytest", "-q"],
    "ruff": [".venv/Scripts/python.exe", "-m", "ruff", "check", "src", "tests", "scripts"],
    "format": [
        ".venv/Scripts/python.exe",
        "-m",
        "ruff",
        "format",
        "--check",
        "src",
        "tests",
        "scripts",
    ],
    "mypy": [".venv/Scripts/python.exe", "-m", "mypy", "-p", "dyadresearch"],
    "frontend_test": _pnpm("--dir", "frontend", "run", "test"),
    "frontend_lint": _pnpm("--dir", "frontend", "run", "lint"),
    "frontend_build": _pnpm("--dir", "frontend", "run", "build"),
    "site_build": [
        ".venv/Scripts/python.exe",
        "-m",
        "mkdocs",
        "build",
        "--strict",
        "--site-dir",
        "site",
    ],
}


def main() -> int:
    results: dict[str, Any] = {}
    for name, command in COMMANDS.items():
        completed = subprocess.run(command, check=False, capture_output=True)
        output = (
            completed.stdout.decode("utf-8", errors="replace")
            + "\n"
            + completed.stderr.decode("utf-8", errors="replace")
        ).strip()
        results[name] = {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "output_tail": output[-4000:],
        }
        print(f"{name}: {'passed' if completed.returncode == 0 else 'failed'}")
    payload = {"ok": all(item["ok"] for item in results.values()), "checks": results}
    output_path = Path("reports/reproduction/validation.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
