"""Generic ink-box packing for the basic Egyptian H/V subset."""
from dataclasses import replace

from ..errors import XSRError
from ..ink import outline_bounds, insertion_region
from ..font_metrics import FontMetrics
from .model import Decoration, InsertionRegion, EgyptianNode, GlyphPlacement, ParsedEgyptianRun, RenderResult


class EgyptianLayoutError(XSRError):
    def __init__(self, detail):
        super().__init__('XSR-UNSUPPORTED', detail)


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
        def transform_region(region):
            updates = dict(x=x+region.x*scale, y=y+region.y*scale,
                           width=region.width*scale, height=region.height*scale)
            if isinstance(region, Decoration):
                updates['stroke'] = region.stroke*scale
            return replace(region, **updates)
        return RenderResult(
            box.width * scale, box.height * scale, 0.0,
            tuple(replace(g, x=x + g.x * scale, y=y + g.y * scale,
                          width=g.width * scale, height=g.height * scale,
                          scale=g.scale * scale) for g in box.glyphs),
            tuple(transform_region(d) for d in box.decorations),
            tuple(transform_region(r) for r in box.insertions),
        )

    def _pack(self, boxes: list[RenderResult], vertical: bool) -> RenderResult:
        if not boxes:
            raise EgyptianLayoutError('empty Egyptian groups cannot be laid out')
        width = (max(b.width for b in boxes) if vertical else
                 sum(b.width for b in boxes) + self.gap * (len(boxes) - 1))
        height = (sum(b.height for b in boxes) + self.gap * (len(boxes) - 1)
                  if vertical else max(b.height for b in boxes))
        cursor = 0.0
        glyphs, decorations, insertions = [], [], []
        for box in boxes:
            x = (width - box.width) / 2 if vertical else cursor
            y = cursor if vertical else (height - box.height) / 2
            placed = self._transform(box, x=x, y=y)
            glyphs.extend(placed.glyphs)
            decorations.extend(placed.decorations)
            insertions.extend(placed.insertions)
            cursor += (box.height if vertical else box.width) + self.gap
        return RenderResult(width, height, 0.0, tuple(glyphs), tuple(decorations), tuple(insertions))

    def _node(self, node: EgyptianNode) -> RenderResult:
        if node.kind == 'sign':
            metric = self.font.glyph(node.codepoint)
            bounds = (outline_bounds(self.font.outline(node.codepoint), node.rotation, node.mirror)
                      if node.rotation or node.mirror else metric.bounds)
            left, bottom, right, top = bounds
            w,h = right-left, top-bottom
            decorations = tuple(
                Decoration('shade', x*w/2, y*h/2, w/2, h/2, .008)
                for bit,x,y in ((1,0,0),(2,0,1),(4,1,0),(8,1,1)) if node.damage & bit)
            return RenderResult(w,h,0.0, (
                GlyphPlacement(node.codepoint,0,0,w,h,1.0,left,top,node.rotation,node.mirror),
            ), decorations)
        if node.kind in ('blank', 'lost'):
            w,h=node.size
            decorations = (Decoration('shade',0,0,w,h,.008),) if node.kind=='lost' else ()
            return RenderResult(w,h,0.0,(),decorations)
        if node.kind == 'overlay':
            boxes = [self._node(child) for child in node.children]
            # Bound each arm to one em before centering actual ink extents.
            boxes = [self._transform(b,min(1,1/max(b.width,b.height))) for b in boxes]
            w,h=max(b.width for b in boxes),max(b.height for b in boxes)
            boxes = [self._transform(b,x=(w-b.width)/2,y=(h-b.height)/2) for b in boxes]
            return RenderResult(w,h,0,tuple(g for b in boxes for g in b.glyphs),
                                tuple(d for b in boxes for d in b.decorations))
        if node.kind == 'insertion':
            core = self._node(node.children[0])
            for slot,child_node in zip(node.slots,node.children[1:]):
                child = self._node(child_node)
                region = insertion_region(self.font,core,child,slot)
                if region is None:
                    cps = ' '.join(f'U+{g.codepoint:05X}' for g in core.glyphs)
                    raise XSRError('XSR-INSERTION-NO-SPACE',
                        f'no legible collision-free {slot} insertion region in {cps} '
                        f'for {self.font.path.name}; a contextual alternate may be needed')
                x,y,scale=region
                placed=self._transform(child,scale,x,y)
                core=replace(core, glyphs=core.glyphs+placed.glyphs,
                             decorations=core.decorations+placed.decorations,
                             insertions=core.insertions+placed.insertions+(
                                 InsertionRegion(slot,x,y,placed.width,placed.height),))
            return core
        if node.kind == 'enclosure':
            content=self._pack([self._node(n) for n in node.children],False)
            pad=.16
            height=content.height+2*pad
            side=height/2+.04 if node.enclosure=='cartouche' else pad
            placed=self._transform(content,x=side,y=pad)
            width=content.width+2*side
            border=Decoration(node.enclosure,.02,.02,width-.04,height-.04,.022,node.ends)
            return replace(placed,width=width,height=height,decorations=(border,)+placed.decorations)
        if node.kind not in ('horizontal','vertical','run'):
            raise EgyptianLayoutError(f'unsupported XSR node {node.kind}')
        return self._pack([self._node(child) for child in node.children], node.kind=='vertical')

    def layout(self, parsed: ParsedEgyptianRun) -> RenderResult:
        boxes = [self._node(child) for child in parsed.structure.children]
        boxes = [self._transform(box, min(1.0, 1.0 / box.height)) for box in boxes]
        packed = self._pack(boxes, False)
        padded = self._transform(packed, x=self.padding, y=self.padding)
        return replace(padded, width=packed.width + 2 * self.padding,
                       height=packed.height + 2 * self.padding)


# Compatibility name; this class no longer consumes Hieropy geometry.
HieropyLayout = EgyptianLayout
