"""Khitan backend XeTeX response: one intrinsic atomic box per cluster."""
from __future__ import annotations
import hashlib
import re
from typing import Mapping
from ..errors import XSRError
from ..synthetic import FallbackFont, policy
from ..vector import tofu, paths_tex
from ..font_metrics import options_font, font_options, encode_path, tex_font_path
from .parser import KhitanParser
from .layout import KhitanLayout

BACKEND_VERSION = 'native-fixed-stack-0.9'


def number(value: float) -> str:
    return f'{value:.6f}'.rstrip('0').rstrip('.') or '0'


class KhitanBackend:
    name = 'khitan'
    version = BACKEND_VERSION

    def __init__(self):
        self.parser = KhitanParser()

    @classmethod
    def preprocess_extras(cls, sources) -> list[dict[str, object]]:
        gaps = {'0.2'}
        for source in sources:
            gaps.update(re.findall(r'\\xsrKhitanClusterGap\s*\{([^{}]+)\}', source))
        return [{'cluster_gap': cls._gap({'cluster_gap': gap})}
                for gap in sorted(gaps)]

    def prepare_options(self, options: Mapping[str, object]) -> dict[str, object]:
        self._mode(options)
        font = FallbackFont(options_font(options), policy(options))
        gap = self._gap(options)
        result = font_options(font.path)
        if policy(options) != 'box':
            result['missing_glyph_policy'] = policy(options)
        if gap != 0.2:
            result['cluster_gap'] = gap
        return result

    @staticmethod
    def _mode(options: Mapping[str, object]) -> None:
        if options.get('writing_mode', 'horizontal') != 'horizontal':
            raise XSRError('XSR-WRITING-MODE-UNSUPPORTED',
                           'Khitan supports horizontal host text only')

    @staticmethod
    def _gap(options: Mapping[str, object]) -> float:
        try:
            gap = float(options.get('cluster_gap', 0.2))
        except (TypeError, ValueError) as error:
            raise XSRError('XSR-KHITAN-GAP', 'cluster_gap must be a finite nonnegative em value') from error
        import math
        if not math.isfinite(gap) or gap < 0 or gap > 2:
            raise XSRError('XSR-KHITAN-GAP', 'cluster_gap must be between 0 and 2 em')
        return gap

    def render(self, text: str, options: Mapping[str, object]) -> str:
        self._mode(options)
        font = FallbackFont(options_font(options), policy(options))
        tex_font_path(font.path)
        gap = self._gap(options)
        parsed = self.parser.parse(text)
        layout = KhitanLayout(font)
        pieces = []
        for index, cluster in enumerate(parsed.clusters):
            if index:
                pieces.append(r'\xsrKhitanBreak{' + (number(gap) if parsed.separators[index - 1] == 'space' else '0') + '}')
            box = layout.cluster(cluster)
            glyphs = ''.join(
                (r'\xsrKhitanSynthetic{' + paths_tex(tofu()) + '}' if g.codepoint in font.missing
                 else r'\xsrKhitanGlyph{' + f'{g.codepoint:X}' + '}') +
                ''.join('{' + number(v) + '}' for v in
                        (g.x, g.y, g.ink_left, g.ink_top))
                for g in box.glyphs)
            pieces.append(r'\xsrKhitanLayout{' + number(box.width) + '}{' +
                          number(box.height) + '}{' + number(box.depth) + '}{' +
                          str(len(box.glyphs)) + '}{' + glyphs + '}')
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]
        body = r'\xsrKhitanUseFont{' + encode_path(tex_font_path(font.path)) + '}{' + font.digest + '}{' + ''.join(pieces) + '}'
        return (r'\xsrBackendLayoutResult{khitan}{' + str(len(text)) + '}{' + digest +
                '}{' + self.version + '}{xsr-native-' + self.parser.parser_version + '}{' + body + '}%\n')
