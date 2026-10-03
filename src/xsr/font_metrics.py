"""Actual OpenType outline metrics; no script or reference-font assumptions."""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from io import BytesIO
from pathlib import Path
import re

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont, TTLibError


def font_file_digest(path: str | Path) -> str:
    return hashlib.md5(Path(path).read_bytes(), usedforsecurity=False).hexdigest().upper()


def tex_font_path(path: str | Path) -> str:
    """Limit the TeX bridge to unambiguous, literal ASCII file paths."""
    value = Path(path).resolve().as_posix()
    if not re.fullmatch(r'[A-Za-z0-9_ ./:-]+', value):
        raise ValueError('font path must use ASCII letters, digits, spaces, _ . / : -')
    return value


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
        except (OSError, TTLibError) as error:
            raise ValueError(f'cannot load font {self.path}: {error}') from error
        if self._font.flavor or 'fvar' in self._font:
            raise ValueError('use a static, uncompressed TTF or OTF font')
        self.digest = hashlib.md5(data, usedforsecurity=False).hexdigest().upper()
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
            raise ValueError(f'{self.path.name} has no glyph for U+{codepoint:05X}')
        return self._glyphs[name]

    def glyph(self, codepoint: int) -> GlyphMetrics:
        if codepoint not in self._metrics:
            glyph = self._glyph(codepoint)
            pen = BoundsPen(self._glyphs)
            glyph.draw(pen)
            if pen.bounds is None:
                raise ValueError(f'U+{codepoint:05X} has no outline in {self.path.name}')
            bounds = tuple(value / self.units_per_em for value in pen.bounds)
            metric = GlyphMetrics(glyph.width / self.units_per_em, bounds)
            if metric.width <= 0 or metric.height <= 0:
                raise ValueError(f'U+{codepoint:05X} has an empty ink box')
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
        raise ValueError(f'cannot load font {resolved}: {error}') from error
    if digest is not None and digest != actual:
        raise ValueError('font digest mismatch; regenerate the request/preprocessed output')
    return _load_font(resolved, actual)
