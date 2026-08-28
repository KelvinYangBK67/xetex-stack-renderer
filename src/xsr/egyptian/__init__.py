"""Egyptian script registration."""

from __future__ import annotations

from ..registry import Registry, ScriptSpec

EGYPTIAN_RANGES = (
    (0x13000, 0x1342F),
    (0x13430, 0x1345F),
    (0x13460, 0x143FF),
)


def register_script(registry: Registry) -> ScriptSpec:
    return registry.register("egyptian", EGYPTIAN_RANGES)


from .backend import EgyptianBackend  # noqa: E402

__all__ = ["EGYPTIAN_RANGES", "EgyptianBackend", "register_script"]

