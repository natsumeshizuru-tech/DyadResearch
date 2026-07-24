from __future__ import annotations

from pathlib import Path

from dyadresearch.experiments.definitions import DefinitionStore
from dyadresearch.experiments.editor import DefinitionEditor

FACTOR_CODE = """FACTOR = {
    "title": "Test Factor",
    "description": "A deterministic test factor.",
    "expression": "close[-1] / close[0] - 1",
    "input_fields": ["close"],
    "lookback": 2,
    "frequency": "1d",
    "higher_is_better": True,
}
"""


def test_definition_editor_materializes_opens_and_syncs(tmp_path: Path) -> None:
    store = DefinitionStore(tmp_path / "research.db")
    store.create("factor", "test_factor", FACTOR_CODE)
    launched: list[Path] = []
    editor = DefinitionEditor(store, tmp_path / "workspace", launcher=launched.append)

    opened = editor.open("factor", "test_factor")
    path = Path(str(opened["path"]))
    assert opened["launched"] is True
    assert launched == [path]
    assert path.read_text(encoding="utf-8") == FACTOR_CODE

    changed = FACTOR_CODE.replace('"lookback": 2', '"lookback": 3')
    path.write_text(changed, encoding="utf-8")
    synced = editor.sync("factor", "test_factor")

    assert synced["synced"] is True
    assert synced["definition"]["version"] == 2
    assert store.get("factor", "test_factor").config["lookback"] == 3
