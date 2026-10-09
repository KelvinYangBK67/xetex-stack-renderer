"""Backend-facing missing visible glyph policy and synthetic geometry."""
import warnings
from .errors import XSRError
from .font_metrics import GlyphMetrics
from .vector import tofu


class XSRWarning(UserWarning):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(f'[{code}] {detail}')


def policy(options):
    value = options.get('missing_glyph_policy', 'box')
    if value not in ('box', 'error'):
        raise XSRError('XSR-MISSING-POLICY', 'missing_glyph_policy must be box or error')
    return value


def warn(code, detail):
    # XSRError messages already include the typed code; warn() adds it once.
    detail = str(detail).removeprefix(f'[{code}] ')
    warnings.warn(XSRWarning(code, detail), stacklevel=3)


class FallbackFont:
    """Called only for visible signs selected by a script parser/layout.

    Both current backends use a nominal 1 em square, in the selected font's
    normalized layout units. Controls never request a glyph through this layer.
    """
    def __init__(self, font, missing_glyph_policy='box', cell=(1., 1.)):
        self.font = font
        self.policy = policy({'missing_glyph_policy': missing_glyph_policy})
        self.cell = cell
        self.missing = set()

    def __getattr__(self, name):
        return getattr(self.font, name)

    def glyph(self, cp):
        try:
            return self.font.glyph(cp)
        except XSRError as error:
            if error.code != 'XSR-GLYPH-MISSING' or self.policy == 'error':
                raise
            if cp not in self.missing:
                warn(error.code, str(error))
                self.missing.add(cp)
            width, height = self.cell
            return GlyphMetrics(width, (0., 0., width, height))

    def outline(self, cp):
        self.glyph(cp)
        if cp in self.missing:
            return tuple((c.operation, c.points) for c in tofu(*self.cell).paths[0].commands)
        return self.font.outline(cp)
