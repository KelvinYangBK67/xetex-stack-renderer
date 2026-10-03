"""Small, font-independent structure and top-origin geometry owned by XSR."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class EgyptianNode:
    kind: Literal['sign', 'horizontal', 'vertical', 'run']
    children: tuple['EgyptianNode', ...] = ()
    codepoint: int | None = None


@dataclass(frozen=True)
class ParsedEgyptianRun:
    text: str
    parser_version: str
    structure: EgyptianNode


@dataclass(frozen=True)
class GlyphPlacement:
    """Ink box in em units; bearings are unscaled baseline-origin metrics."""
    codepoint: int
    x: float
    y: float
    width: float
    height: float
    scale: float
    ink_left: float = 0.0
    ink_top: float = 0.0


@dataclass(frozen=True)
class RenderResult:
    """Fixed inline box. Baseline is the bottom; placement origin is top-left."""
    width: float
    height: float
    depth: float
    glyphs: tuple[GlyphPlacement, ...]
