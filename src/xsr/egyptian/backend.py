'''Egyptian backend producing XeTeX boxes from XSR geometry.'''

from __future__ import annotations

import hashlib
from typing import Mapping

from ..synthetic import FallbackFont, policy
from ..vector import tofu, paths_tex
from ..font_metrics import options_font, font_options, encode_path, tex_font_path
from ..ink import matrix
from .parser import EgyptianParser
from .model import RenderResult
from .layout import EgyptianLayout
from .semantics import layout_options


BACKEND_VERSION = 'font-aware-ehfc-0.9'


def _tex_number(value: float) -> str:
    formatted = f'{value:.6f}'.rstrip('0').rstrip('.')
    return '0' if formatted == '-0' else formatted


def serialize_tex_layout(result: RenderResult, missing=()) -> str:
    '''Serialize top-origin em geometry for xsr-egyptian.sty's box builder.'''
    glyphs = ''
    for glyph in result.glyphs:
        if glyph.rotation or glyph.mirror or glyph.codepoint in missing:
            a,b,c,d,_,_ = matrix(glyph.rotation,glyph.mirror)
            transform = ','.join(_tex_number(v*glyph.scale) for v in (a,b,c,d))
            glyphs += ((r'\xsrEgyptianSynthetic{' + paths_tex(tofu()) + '}' if glyph.codepoint in missing
                        else r'\xsrEgyptianTransformedGlyph' + f'{{{glyph.codepoint:X}}}')
                       + f'{{{_tex_number(glyph.x-glyph.ink_left*glyph.scale)}}}'
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

    def __init__(self, parser: EgyptianParser | None = None) -> None:
        self.parser = parser or EgyptianParser()

    @staticmethod
    def preprocess_extras(sources) -> list[dict[str, object]]:
        if any('xsrEgyptianDirection' in source for source in sources):
            return [{}, {'direction': 'rtl'}]
        return [{}]

    def prepare_options(self, options: Mapping[str, object]) -> dict[str, object]:
        font = FallbackFont(options_font(options), policy(options))
        direction=layout_options(options)
        prepared=font_options(font.path)
        if policy(options) != 'box':
            prepared['missing_glyph_policy'] = policy(options)
        if direction!='ltr':
            prepared['direction']=direction
        return prepared

    def render(self, text: str, options: Mapping[str, object]) -> str:
        font = FallbackFont(options_font(options), policy(options))
        tex_font_path(font.path)
        direction=layout_options(options)
        quadrats=EgyptianLayout(font,direction).quadrats(self.parser.parse(text))
        layout_tex=r'\xsrEgyptianBreak{}'.join(serialize_tex_layout(q, font.missing) for q in quadrats)
        layout_tex=r'\xsrEgyptianFlow{'+direction+'}{'+layout_tex+'}'
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]
        parser = f'xsr-native-{self.parser.parser_version}'
        body = (r'\xsrEgyptianUseFont'
                f'{{{encode_path(tex_font_path(font.path))}}}{{{font.digest}}}'
                f'{{{layout_tex}}}')
        return (
            f'\\xsrBackendLayoutResult{{{self.name}}}{{{len(text)}}}'
            f'{{{digest}}}{{{self.version}}}{{{parser}}}{{{body}}}%\n'
        )
