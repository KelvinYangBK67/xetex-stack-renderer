'''Small XSR-owned geometry model for Egyptian rendering.'''

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedEgyptianRun:
    '''A parsed run with Hieropy's Fragment kept deliberately opaque.'''

    text: str
    parser_version: str
    fragment: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class GlyphPlacement:
    '''One glyph in em-based, top-origin XSR coordinates.'''

    codepoint: int
    x: float
    y: float
    width: float
    height: float
    scale: float


@dataclass(frozen=True)
class RenderResult:
    '''A fixed inline box and the glyph cells placed inside it.

    ``height`` is above the TeX baseline and ``depth`` is below it. For the
    first H/V renderer the baseline is the bottom of Hieropy's canvas, so
    ``depth`` is zero. Coordinates in placements start at the canvas top-left.
    '''

    width: float
    height: float
    depth: float
    glyphs: tuple[GlyphPlacement, ...]
