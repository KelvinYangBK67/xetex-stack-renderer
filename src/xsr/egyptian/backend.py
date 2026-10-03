'''Egyptian backend producing XeTeX boxes from XSR geometry.'''

from __future__ import annotations

import hashlib
from typing import Mapping

from ..font_metrics import options_font, font_options, encode_path, tex_font_path
from ..ink import matrix
from .hieropy_adapter import HieropyAdapter
from .model import RenderResult


BACKEND_VERSION = 'font-aware-ehfc-0.5'


def _tex_number(value: float) -> str:
    formatted = f'{value:.6f}'.rstrip('0').rstrip('.')
    return '0' if formatted == '-0' else formatted


def serialize_tex_layout(result: RenderResult) -> str:
    '''Serialize top-origin em geometry for xsr-egyptian.sty's box builder.'''
    glyphs = ''
    for glyph in result.glyphs:
        if glyph.rotation or glyph.mirror:
            a,b,c,d,_,_ = matrix(glyph.rotation,glyph.mirror)
            transform = ','.join(_tex_number(v*glyph.scale) for v in (a,b,c,d))
            glyphs += (r'\xsrEgyptianTransformedGlyph'
                       f'{{{glyph.codepoint:X}}}{{{_tex_number(glyph.x-glyph.ink_left*glyph.scale)}}}'
                       f'{{{_tex_number(glyph.y+glyph.ink_top*glyph.scale)}}}{{{transform}}}')
        else:
            glyphs += (r'\xsrEgyptianGlyph' + f'{{{glyph.codepoint:X}}}' + ''.join(
                f'{{{_tex_number(v)}}}' for v in (glyph.x,glyph.y,glyph.width,glyph.height,
                                                 glyph.scale,glyph.ink_left,glyph.ink_top)))
    from .drawing import decoration_tex
    glyphs += ''.join(decoration_tex(dec) for dec in result.decorations)
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

    def prepare_options(self, options: Mapping[str, object]) -> dict[str, object]:
        font = options_font(options)
        return font_options(font.path)

    def render(self, text: str, options: Mapping[str, object]) -> str:
        font = options_font(options)
        tex_font_path(font.path)
        layout = self.adapter.layout(text, font)
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]
        parser = f'hieropy-{self.adapter.parser_version}'
        body = (r'\xsrEgyptianUseFont'
                f'{{{encode_path(tex_font_path(font.path))}}}{{{font.digest}}}'
                f'{{{serialize_tex_layout(layout)}}}')
        return (
            f'\\xsrBackendLayoutResult{{{self.name}}}{{{len(text)}}}'
            f'{{{digest}}}{{{self.version}}}{{{parser}}}{{{body}}}%\n'
        )
