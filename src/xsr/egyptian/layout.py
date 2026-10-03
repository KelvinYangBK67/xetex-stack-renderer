"""Generic ink-box packing for the basic Egyptian H/V subset."""
from dataclasses import replace

from ..font_metrics import FontMetrics
from .model import EgyptianNode, GlyphPlacement, ParsedEgyptianRun, RenderResult


class EgyptianLayoutError(ValueError):
    """A construct is outside the basic H/V subset."""


class EgyptianLayout:
    """Compose natural ink boxes, center children, then shrink each quadrat.

    Each top-level group fits within one em of height without enlargement.
    H/V gaps are 0.08 em before fitting; outer padding is 0.04 em. Plain
    successive signs form independent quadrats. No reference-font geometry
    or Hieropy layout methods enter this layer.
    """
    gap = 0.08
    padding = 0.04

    def __init__(self, font: FontMetrics):
        self.font = font

    @staticmethod
    def _transform(box: RenderResult, scale=1.0, x=0.0, y=0.0) -> RenderResult:
        return RenderResult(
            box.width * scale, box.height * scale, 0.0,
            tuple(replace(g, x=x + g.x * scale, y=y + g.y * scale,
                          width=g.width * scale, height=g.height * scale,
                          scale=g.scale * scale) for g in box.glyphs),
        )

    def _pack(self, boxes: list[RenderResult], vertical: bool) -> RenderResult:
        if not boxes:
            raise EgyptianLayoutError('empty Egyptian groups cannot be laid out')
        width = (max(b.width for b in boxes) if vertical else
                 sum(b.width for b in boxes) + self.gap * (len(boxes) - 1))
        height = (sum(b.height for b in boxes) + self.gap * (len(boxes) - 1)
                  if vertical else max(b.height for b in boxes))
        cursor = 0.0
        glyphs = []
        for box in boxes:
            x = (width - box.width) / 2 if vertical else cursor
            y = cursor if vertical else (height - box.height) / 2
            glyphs.extend(self._transform(box, x=x, y=y).glyphs)
            cursor += (box.height if vertical else box.width) + self.gap
        return RenderResult(width, height, 0.0, tuple(glyphs))

    def _node(self, node: EgyptianNode) -> RenderResult:
        if node.kind == 'sign':
            metric = self.font.glyph(node.codepoint)
            return RenderResult(metric.width, metric.height, 0.0, (
                GlyphPlacement(node.codepoint, 0, 0, metric.width, metric.height,
                               1.0, metric.bounds[0], metric.bounds[3]),
            ))
        return self._pack([self._node(child) for child in node.children],
                          node.kind == 'vertical')

    def layout(self, parsed: ParsedEgyptianRun) -> RenderResult:
        boxes = [self._node(child) for child in parsed.structure.children]
        boxes = [self._transform(box, min(1.0, 1.0 / box.height)) for box in boxes]
        packed = self._pack(boxes, False)
        padded = self._transform(packed, x=self.padding, y=self.padding)
        return replace(padded, width=packed.width + 2 * self.padding,
                       height=packed.height + 2 * self.padding)


# Compatibility name; this class no longer consumes Hieropy geometry.
HieropyLayout = EgyptianLayout
