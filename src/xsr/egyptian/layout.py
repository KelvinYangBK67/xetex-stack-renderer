'''Hieropy 0.1.4 geometry boundary for the basic H/V subset.

This module is the only XSR code that knows Hieropy's layout internals.
``Fragment.format`` initializes and fits group scales. ``Horizontal.format``
partitions the available x interval, while ``Vertical.format`` partitions y
and accounts for nested vertical spaces. Their recursive ``format`` calls end
at ``Literal.format``, which stores absolute ``x``, ``y``, ``w``, ``h`` and
the inherited ``scale``. XSR snapshots those values into its own model.

Hieropy 0.1.4 computes literal sizes through ``em_size_of`` and its bundled
measurement font. That dependency affects geometry only: no Hieropy raster or
font is emitted, and XeTeX remains responsible for selecting and shaping the
actual output glyphs.
'''

from __future__ import annotations

import math
from collections.abc import Iterator

from .model import GlyphPlacement, ParsedEgyptianRun, RenderResult


class EgyptianLayoutError(ValueError):
    '''Raised when a parsed construct is outside the basic H/V subset.'''


class HieropyLayout:
    '''Convert a Hieropy Fragment into XSR-owned basic H/V geometry.'''

    def __init__(self) -> None:
        from hieropy import Options
        from hieropy.unistructure import Fragment, Horizontal, Literal, Vertical

        self._options_type = Options
        self._fragment_type = Fragment
        self._horizontal_type = Horizontal
        self._literal_type = Literal
        self._vertical_type = Vertical

    def layout(self, parsed: ParsedEgyptianRun) -> RenderResult:
        fragment = parsed.fragment
        if not isinstance(fragment, self._fragment_type):
            raise EgyptianLayoutError(
                f'expected Hieropy Fragment, got {type(fragment).__name__}'
            )
        if not fragment.groups:
            raise EgyptianLayoutError('empty Egyptian runs cannot be laid out')

        self._validate_node(fragment)
        options = self._options_type(
            direction='hlr',
            linesize=1.0,
            sep=0.08,
            hmargin=0.04,
            vmargin=0.04,
            align='middle',
            separated=False,
        )
        fragment.format(options)
        content_width, content_height = fragment.size(options)

        # These are the same outer extents used by Fragment.print(), without
        # constructing any of Hieropy's PIL/PDF/SVG printable objects.
        width = content_width + options.sep + 2 * options.hmargin
        total_height = content_height + options.sep + 2 * options.vmargin
        glyphs = tuple(self._collect_literals(fragment))
        if not glyphs:
            raise EgyptianLayoutError('basic H/V layout produced no glyphs')

        self._validate_geometry(width, total_height, glyphs)
        return RenderResult(
            width=width,
            height=total_height,
            depth=0.0,
            glyphs=glyphs,
        )

    def _validate_node(self, node: object) -> None:
        if isinstance(node, self._literal_type):
            unsupported = []
            if node.vs:
                unsupported.append('rotation/variation')
            if node.mirror:
                unsupported.append('mirror')
            if node.damage:
                unsupported.append('damage')
            if unsupported:
                joined = ', '.join(unsupported)
                raise EgyptianLayoutError(
                    f'unsupported Literal feature(s): {joined}'
                )
            return

        allowed_containers = (
            self._fragment_type,
            self._horizontal_type,
            self._vertical_type,
        )
        if not isinstance(node, allowed_containers):
            raise EgyptianLayoutError(
                f'unsupported Hieropy group for basic H/V layout: '
                f'{type(node).__name__}'
            )
        for child in node.groups:
            self._validate_node(child)

    def _collect_literals(self, node: object) -> Iterator[GlyphPlacement]:
        if isinstance(node, self._literal_type):
            yield GlyphPlacement(
                codepoint=ord(node.ch),
                x=float(node.x),
                y=float(node.y),
                width=float(node.w),
                height=float(node.h),
                scale=float(node.scale),
            )
            return
        for child in node.groups:
            yield from self._collect_literals(child)

    @staticmethod
    def _validate_geometry(
        width: float,
        total_height: float,
        glyphs: tuple[GlyphPlacement, ...],
    ) -> None:
        values = [width, total_height]
        for glyph in glyphs:
            values.extend(
                [glyph.x, glyph.y, glyph.width, glyph.height, glyph.scale]
            )
        if not all(math.isfinite(value) for value in values):
            raise EgyptianLayoutError('Hieropy produced non-finite geometry')
        if width <= 0 or total_height <= 0:
            raise EgyptianLayoutError('Hieropy produced an empty layout box')
        if any(
            glyph.width <= 0 or glyph.height <= 0 or glyph.scale <= 0
            for glyph in glyphs
        ):
            raise EgyptianLayoutError('Hieropy produced an empty glyph box')
