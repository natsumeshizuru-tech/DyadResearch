from __future__ import annotations

from dyadresearch.factors.spec import FactorSpec


class FactorRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, FactorSpec] = {}

    def register(self, spec: FactorSpec, *, replace: bool = False) -> None:
        if spec.name in self._specs and not replace:
            raise ValueError(f"factor is already registered: {spec.name}")
        self._specs[spec.name] = spec

    def get(self, name: str) -> FactorSpec:
        try:
            return self._specs[name]
        except KeyError as exc:
            raise KeyError(f"unknown factor: {name}") from exc

    def list(self) -> tuple[FactorSpec, ...]:
        return tuple(self._specs[name] for name in sorted(self._specs))


factor_registry = FactorRegistry()
