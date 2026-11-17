from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..engine import Context


class Skip(Exception):
    """Module cannot run (missing key, unsupported input, or unavailable source)."""


class Module:
    name: str = ""
    title: str = ""
    description: str = ""
    inputs: tuple[str, ...] = ()
    # Required credentials: missing keys cause a skipped module.
    keys: tuple[str, ...] = ()
    # Optional credentials improve results but are not required.
    optional_keys: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    timeout: float = 60
    # Enrichment module: run on newly discovered matching entities.
    auto: bool = False
    # Deep module: run only when explicitly requested.
    deep: bool = False

    def applies(self, entity: dict) -> bool:
        return entity["type"] in self.inputs

    async def run(self, ctx: "Context") -> None:
        raise NotImplementedError

    def meta(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputs": list(self.inputs),
            "keys": list(self.keys),
            "optional_keys": list(self.optional_keys),
            "sources": list(self.sources),
            "deep": self.deep,
        }


REGISTRY: dict[str, Module] = {}


def register(cls):
    inst = cls()
    REGISTRY[inst.name] = inst
    return cls
