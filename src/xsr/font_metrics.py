"""Actual OpenType outline metrics; no script or reference-font assumptions."""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from io import BytesIO
from pathlib import Path
import re

from .errors import XSRError

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont, TTLibError


def font_file_digest(path: str | Path) -> str:
    return hashlib.md5(Path(path).read_bytes(), usedforsecurity=False).hexdigest().upper()


def tex_font_path(path: str | Path) -> str:
    """Unicode paths are transported as codepoints, never interpolated as TeX."""
    value = Path(path).resolve().as_posix()
    if any(ch in value for ch in '\x00\r\n"{}%#[]'):
        raise XSRError('XSR-FONT-PATH', 'font path contains a reserved TeX/XeTeX filename character')
    return value


def encode_path(path: str | Path) -> str:
    return ','.join(f'{ord(ch):X}' for ch in str(path))


def decode_path(encoded: str) -> str:
    try:
        value = ''.join(chr(int(cp,16)) for cp in encoded.split(','))
    except (ValueError, OverflowError) as error:
        raise XSRError('XSR-REQUEST', 'malformed font path codepoints') from error
    tex_font_path(value)
    return value


def font_options(path: str | Path, *, spelling: str | None = None) -> dict:
    font = load_font(path)
    return {'font_codepoints': encode_path(spelling if spelling is not None else tex_font_path(font.path)),
            'font_digest': font.digest}


def options_font(options) -> 'FontMetrics':
    path = (decode_path(options['font_codepoints']) if options.get('font_codepoints')
            else options.get('font_path'))
    if not path:
        raise XSRError('XSR-FONT-NOT-SELECTED', 'Egyptian rendering requires an explicit font_path; use \\xsrEgyptianDefaultFont')
    return load_font(path, options.get('font_digest'))


@dataclass(frozen=True)
class GlyphMetrics:
    advance: float
    bounds: tuple[float, float, float, float]

    @property
    def width(self) -> float:
        return self.bounds[2] - self.bounds[0]

    @property
    def height(self) -> float:
        return self.bounds[3] - self.bounds[1]


class FontMetrics:
    """Snapshot a static TTF/OTF; baseline-origin, y-up em coordinates.

    Bounds use actual Bezier extrema, including composites. Outlines are
    normalized pen recordings. Variable fonts/collections need explicit
    instance/face support and are rejected to prevent a XeTeX mismatch.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        try:
            data = self.path.read_bytes()
            self._font = TTFont(BytesIO(data))
        except OSError as error:
            raise XSRError('XSR-FONT-MISSING', f'cannot load font {self.path}: {error.strerror}') from error
        except TTLibError as error:
            raise XSRError('XSR-FONT-FORMAT', f'cannot load font {self.path}: use a static TTF/OTF, not a collection or webfont') from error
        if self._font.flavor or 'fvar' in self._font:
            raise XSRError('XSR-FONT-FORMAT', 'use a static, uncompressed TTF or OTF font; variable fonts are unsupported')
        self.digest = hashlib.md5(data, usedforsecurity=False).hexdigest().upper()
        if not {'head','hhea','hmtx','cmap','name'} <= set(self._font.keys()) or not ({'glyf','CFF '} & set(self._font.keys())):
            raise XSRError('XSR-FONT-FORMAT', 'font lacks required Unicode outline/metric tables')
        self.units_per_em = self._font['head'].unitsPerEm
        self.ascender = self._font['hhea'].ascent / self.units_per_em
        self.descender = self._font['hhea'].descent / self.units_per_em
        self.line_gap = self._font['hhea'].lineGap / self.units_per_em
        self.name = self._font['name'].getDebugName(1) or self.path.stem
        self._cmap = self._font.getBestCmap() or {}
        self._glyphs = self._font.getGlyphSet()
        self._metrics: dict[int, GlyphMetrics] = {}

    def _glyph(self, codepoint: int):
        name = self._cmap.get(codepoint)
        if name is None or name == '.notdef':
            raise XSRError('XSR-GLYPH-MISSING', f'{self.path.name} has no glyph for U+{codepoint:05X}')
        return self._glyphs[name]

    def glyph(self, codepoint: int) -> GlyphMetrics:
        if codepoint not in self._metrics:
            glyph = self._glyph(codepoint)
            pen = BoundsPen(self._glyphs)
            glyph.draw(pen)
            if pen.bounds is None:
                raise XSRError('XSR-GLYPH-EMPTY', f'U+{codepoint:05X} has no outline in {self.path.name}')
            bounds = tuple(value / self.units_per_em for value in pen.bounds)
            metric = GlyphMetrics(glyph.width / self.units_per_em, bounds)
            if metric.width <= 0 or metric.height <= 0:
                raise XSRError('XSR-GLYPH-EMPTY', f'U+{codepoint:05X} has an empty ink box')
            self._metrics[codepoint] = metric
        return self._metrics[codepoint]

    def outline(self, codepoint: int) -> tuple:
        pen = DecomposingRecordingPen(self._glyphs)
        self._glyph(codepoint).draw(pen)
        normalized = DecomposingRecordingPen({})
        factor = 1 / self.units_per_em
        pen.replay(TransformPen(normalized, (factor, 0, 0, factor, 0, 0)))
        return tuple(normalized.value)


@lru_cache(maxsize=16)
def _load_font(path: str, digest: str) -> FontMetrics:
    profile = FontMetrics(path)
    if profile.digest != digest:
        raise ValueError('font changed while loading; retry with its current digest')
    return profile


def load_font(path: str | Path, digest: str | None = None) -> FontMetrics:
    resolved = str(Path(path).resolve())
    try:
        actual = font_file_digest(resolved)
    except OSError as error:
        raise XSRError('XSR-FONT-MISSING', f'cannot load font {resolved}: {error.strerror}') from error
    if digest is not None and digest != actual:
        raise XSRError('XSR-STALE', 'font digest mismatch; regenerate the request/preprocessed output')
    return _load_font(resolved, actual)
