"""Immutable Egyptian semantics and top-origin em geometry owned by XSR."""
from dataclasses import dataclass


@dataclass(frozen=True)
class EgyptianNode:
    kind: str
    children: tuple['EgyptianNode', ...] = ()
    codepoint: int | None = None
    rotation: int = 0
    mirror: bool = False
    damage: int = 0
    slots: tuple[str, ...] = ()
    size: tuple[float, float] = (0, 0)
    enclosure: str = ''
    ends: tuple[bool, bool] = (True, True)


@dataclass(frozen=True)
class ParsedEgyptianRun:
    text: str
    parser_version: str
    structure: EgyptianNode


@dataclass(frozen=True)
class GlyphPlacement:
    """Ink box; bearing values refer to the transformed, unscaled outline."""
    codepoint: int
    x: float
    y: float
    width: float
    height: float
    scale: float
    ink_left: float = 0.0
    ink_top: float = 0.0
    rotation: int = 0
    mirror: bool = False


@dataclass(frozen=True)
class Decoration:
    kind: str
    x: float
    y: float
    width: float
    height: float
    stroke: float = 0.018
    ends: tuple[bool, bool] = (True, True)


@dataclass(frozen=True)
class InsertionRegion:
    """Accepted, collision-tested region, retained for diagnostics/tests."""
    slot: str
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class RenderResult:
    width: float
    height: float
    depth: float
    glyphs: tuple[GlyphPlacement, ...]
    decorations: tuple[Decoration, ...] = ()
    insertions: tuple[InsertionRegion, ...] = ()
