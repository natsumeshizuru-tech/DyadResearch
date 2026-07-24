from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from dyadresearch.data.models import Bar


def query_fingerprint(*, paths: Iterable[Path], query: dict[str, Any], bars: Iterable[Bar]) -> str:
    digest = hashlib.sha256()
    normalized_paths = []
    for path in sorted(paths):
        stat = path.stat()
        normalized_paths.append(
            {"path": str(path.resolve()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        )
    digest.update(
        json.dumps(
            {"paths": normalized_paths, "query": query},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )
    for bar in bars:
        digest.update(
            json.dumps(bar.to_dict(), sort_keys=True, separators=(",", ":"), default=str).encode(
                "utf-8"
            )
        )
    return digest.hexdigest()
