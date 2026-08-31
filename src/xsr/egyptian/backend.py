'''Egyptian backend producing XeTeX boxes from XSR geometry.'''

from __future__ import annotations

import hashlib
from typing import Mapping

from .hieropy_adapter import HieropyAdapter
from .model import RenderResult


BACKEND_VERSION = 'hieropy-0.1.4-basic-hv-layout-1'


def _tex_number(value: float) -> str:
    formatted = f'{value:.6f}'.rstrip('0').rstrip('.')
    return '0' if formatted == '-0' else formatted


def serialize_tex_layout(result: RenderResult) -> str:
    '''Serialize top-origin em geometry for xsr-egyptian.sty's box builder.'''
    glyphs = ''.join(
        '\\xsrEgyptianGlyph'
        f'{{{glyph.codepoint:X}}}'
        f'{{{_tex_number(glyph.x)}}}'
        f'{{{_tex_number(glyph.y)}}}'
        f'{{{_tex_number(glyph.width)}}}'
        f'{{{_tex_number(glyph.height)}}}'
        f'{{{_tex_number(glyph.scale)}}}'
        for glyph in result.glyphs
    )
    return (
        '\\xsrEgyptianLayout'
        f'{{{_tex_number(result.width)}}}'
        f'{{{_tex_number(result.height)}}}'
        f'{{{_tex_number(result.depth)}}}'
        f'{{{len(result.glyphs)}}}'
        f'{{{glyphs}}}'
    )


class EgyptianBackend:
    name = 'egyptian'
    version = BACKEND_VERSION

    def __init__(self, adapter: HieropyAdapter | None = None) -> None:
        self.adapter = adapter or HieropyAdapter()

    def render(self, text: str, options: Mapping[str, object]) -> str:
        '''Parse and lay out one complete basic H/V run, then emit TeX boxes.'''
        del options
        layout = self.adapter.layout(text)
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]
        parser = f'hieropy-{self.adapter.parser_version}'
        body = serialize_tex_layout(layout)
        return (
            f'\\xsrBackendLayoutResult{{{self.name}}}{{{len(text)}}}'
            f'{{{digest}}}{{{self.version}}}{{{parser}}}{{{body}}}\n'
        )
