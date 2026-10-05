"""Unicode Khitan Small Script registration and backend."""
from ..registry import Registry, ScriptSpec

KHITAN_RANGES = ((0x18B00, 0x18CDA), (0x18CFF, 0x18CFF))


def register_script(registry: Registry) -> ScriptSpec:
    return registry.register(
        'khitan', KHITAN_RANGES,
        suffixes=((0x16FE4, 0x16FE4),),
        infixes=((0x20, 0x20), (0x200B, 0x200B)),
    )


from .backend import KhitanBackend  # noqa: E402
from .parser import KhitanParser  # noqa: E402
from .layout import KhitanLayout  # noqa: E402