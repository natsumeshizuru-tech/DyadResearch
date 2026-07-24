from pathlib import Path

from dyadresearch.experiments.store import ExperimentStore


def test_store_is_idempotent_by_kind_and_result_hash(tmp_path: Path) -> None:
    store = ExperimentStore(tmp_path / "research.db")
    first = store.save(
        kind="factor",
        name="momentum",
        result_hash="abc",
        data_fingerprint="data",
        config={"lookback": 20},
        result={"count": 2},
    )
    second = store.save(
        kind="factor",
        name="momentum-renamed",
        result_hash="abc",
        data_fingerprint="data",
        config={"lookback": 20},
        result={"count": 3},
    )
    assert first.id == second.id
    assert second.name == "momentum-renamed"
    assert store.get(first.id) == second
    assert store.get(999) is None
    assert store.list(kind="factor") == (second,)
