from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dyadresearch.experiments.definitions import DefinitionKind, DefinitionStore


class DefinitionEditor:
    def __init__(
        self,
        store: DefinitionStore,
        workspace: Path,
        *,
        launcher: Callable[[Path], None] | None = None,
    ) -> None:
        self.store = store
        self.workspace = workspace.resolve()
        self.launcher = launcher or launch_vscode

    def materialize(self, kind: DefinitionKind, name: str) -> dict[str, Any]:
        definition = self.store.get(kind, name)
        path = self._path(kind, definition.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".py.tmp")
        temporary.write_text(definition.code, encoding="utf-8", newline="\n")
        temporary.replace(path)
        return {"path": str(path), "version": definition.version, "kind": kind, "name": name}

    def open(self, kind: DefinitionKind, name: str) -> dict[str, Any]:
        result = self.materialize(kind, name)
        self.launcher(Path(str(result["path"])))
        return {**result, "launched": True}

    def sync(self, kind: DefinitionKind, name: str) -> dict[str, Any]:
        path = self._path(kind, name)
        if not path.is_file():
            raise FileNotFoundError(f"VS Code workspace file does not exist: {path}")
        if path.stat().st_size > 50_000:
            raise ValueError("definition workspace file exceeds 50,000 bytes")
        definition = self.store.update(kind, name, path.read_text(encoding="utf-8"))
        return {"definition": definition.to_dict(), "path": str(path), "synced": True}

    def _path(self, kind: DefinitionKind, name: str) -> Path:
        folder = "strategies" if kind == "strategy" else "factors"
        path = (self.workspace / folder / f"{name}.py").resolve()
        if self.workspace not in path.parents:
            raise ValueError("definition workspace path escaped its root")
        return path


def launch_vscode(path: Path) -> None:
    command = shutil.which("code") or shutil.which("code.cmd")
    if command is None:
        raise RuntimeError("未找到 VS Code 命令; 请确认 code 已加入 PATH")
    executable = Path(command)
    if executable.suffix.lower() in {".cmd", ".bat"}:
        candidate = executable.parent.parent / "Code.exe"
        if candidate.is_file():
            executable = candidate
    if executable.suffix.lower() in {".cmd", ".bat"}:
        raise RuntimeError("VS Code 命令仅提供批处理入口, 无法安全启动编辑器")
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    subprocess.Popen(
        [str(executable), "--reuse-window", "--goto", str(path)],
        close_fds=True,
        creationflags=creation_flags,
    )
