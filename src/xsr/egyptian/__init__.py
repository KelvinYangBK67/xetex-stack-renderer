'''Egyptian script registration and backend exports.'''

from __future__ import annotations

from ..registry import Registry, ScriptSpec

EGYPTIAN_RANGES = (
    (0x13000, 0x1342F),
    (0x13430, 0x1345F),
    (0x13460, 0x143FF),
)


def register_script(registry: Registry) -> ScriptSpec:
    return registry.register('egyptian', EGYPTIAN_RANGES)


from .backend import (  # noqa: E402
    BACKEND_VERSION,
    EgyptianBackend,
    serialize_tex_layout,
)
from .hieropy_adapter import EgyptianParseError, HieropyAdapter  # noqa: E402
from .layout import EgyptianLayoutError, HieropyLayout  # noqa: E402
from .model import GlyphPlacement, ParsedEgyptianRun, RenderResult  # noqa: E402

__all__ = [
    'BACKEND_VERSION',
    'EGYPTIAN_RANGES',
    'EgyptianBackend',
    'EgyptianLayoutError',
    'EgyptianParseError',
    'GlyphPlacement',
    'HieropyAdapter',
    'HieropyLayout',
    'ParsedEgyptianRun',
    'RenderResult',
    'register_script',
    'serialize_tex_layout',
]
