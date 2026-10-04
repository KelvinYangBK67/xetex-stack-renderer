"""Font-derived horizontal Egyptian composition and atomic quadrat layout."""
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

    def __init__(self, font: FontMetrics, direction='ltr'):
        self.font = font
        self.rtl = direction == 'rtl'

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
            tuple(transform_region(r) for r in box.insertions), box.continuous,
        )

    def _pack(self, boxes: list[RenderResult], vertical: bool) -> RenderResult:
        if not boxes:
            raise EgyptianLayoutError('empty Egyptian groups cannot be laid out')
        if self.rtl and not vertical:
            boxes = list(reversed(boxes))
        gaps = [self.gap*((not a.continuous)+(not b.continuous))/2 for a,b in zip(boxes,boxes[1:])]
        width = (max(b.width for b in boxes) if vertical else
                 sum(b.width for b in boxes) + sum(gaps))
        height = (sum(b.height for b in boxes) + sum(gaps)
                  if vertical else max(b.height for b in boxes))
        cursor = 0.0
        glyphs, decorations, insertions = [], [], []
        for index,box in enumerate(boxes):
            if box.continuous:
                w,h = (width,box.height) if vertical else (box.width,height)
                box=replace(box,width=w,height=h,decorations=(Decoration('shade',0,0,w,h,.008),))
            x = (width - box.width) / 2 if vertical else cursor
            y = cursor if vertical else (height - box.height) / 2
            placed = self._transform(box, x=x, y=y)
            glyphs.extend(placed.glyphs)
            decorations.extend(placed.decorations)
            insertions.extend(placed.insertions)
            cursor += (box.height if vertical else box.width) + (gaps[index] if index<len(gaps) else 0)
        return RenderResult(width, height, 0.0, tuple(glyphs), tuple(decorations), tuple(insertions))

    def _node(self, node: EgyptianNode) -> RenderResult:
        if node.kind == 'bracket':
            return RenderResult(.22,1,0,(),(Decoration('bracket-'+str(node.codepoint),.02,.02,.18,.96,.022,mirror=self.rtl),))
        if node.kind == 'sign':
            node = replace(node,mirror=node.mirror ^ self.rtl)
            metric = self.font.glyph(node.codepoint)
            bounds = (outline_bounds(self.font.outline(node.codepoint), node.rotation, node.mirror)
                      if node.rotation or node.mirror else metric.bounds)
            left, bottom, right, top = bounds
            w,h = right-left, top-bottom
            decorations = tuple(
                Decoration('shade', (1-x if self.rtl else x)*w/2, y*h/2, w/2, h/2, .008)
                for bit,x,y in ((1,0,0),(2,0,1),(4,1,0),(8,1,1)) if node.damage & bit)
            return RenderResult(w,h,0.0, (
                GlyphPlacement(node.codepoint,0,0,w,h,1.0,left,top,node.rotation,node.mirror),
            ), decorations)
        if node.kind in ('blank', 'lost'):
            w,h=node.size
            decorations = (Decoration('shade',0,0,w,h,.008),) if node.kind=='lost' else ()
            return RenderResult(w,h,0.0,(),decorations,continuous=node.continuous)
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
                physical_slot = {'ts':'te','te':'ts','bs':'be','be':'bs'}.get(slot,slot) if self.rtl else slot
                region = insertion_region(self.font,core,child,physical_slot)
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
            common = {'cartouche':({None,0x13379},{None,0x1337A}),
                      'rectangle':({None,0x13258},{None,0x1325B}),
                      'walled':({None,0x13286},{None,0x13287})}
            starts,ends=common[node.enclosure]
            if node.endpoint_codepoints[0] not in starts or node.endpoint_codepoints[1] not in ends:
                # Less common endpoints retain their encoded shapes, measured and
                # rendered from the selected font; connecting rails remain vectors.
                caps=[]
                for cp,damage in zip(node.endpoint_codepoints,node.endpoint_damage):
                    cap=self._node(EgyptianNode('sign',codepoint=cp,damage=damage)) if cp else RenderResult(.04,height,0,())
                    caps.append(self._transform(cap,height/cap.height))
                start,end=(caps[1],caps[0]) if self.rtl else caps
                placed=self._transform(content,x=start.width+pad,y=pad)
                end=self._transform(end,x=start.width+content.width+2*pad)
                width=end.glyphs[0].x+end.width if end.glyphs else start.width+content.width+2*pad+end.width
                rail=Decoration('walled' if node.enclosure=='walled' else 'rectangle',start.width-.011,0,content.width+2*pad+.022,height,.022,(False,False))
                return RenderResult(width,height,0,start.glyphs+placed.glyphs+end.glyphs,
                                    (rail,)+start.decorations+placed.decorations+end.decorations,placed.insertions)
            border=Decoration(node.enclosure,.02,.02,width-.04,height-.04,.022,node.ends,mirror=self.rtl)
            damage=[]
            for end,mask in enumerate(node.endpoint_damage):
                physical=1-end if self.rtl else end
                x0=0 if physical==0 else width-side
                for bit,x,y in ((1,0,0),(2,0,1),(4,1,0),(8,1,1)):
                    if mask & bit:
                        damage.append(Decoration('shade',x0+(1-x if self.rtl else x)*side/2,y*height/2,side/2,height/2,.008))
            return replace(placed,width=width,height=height,decorations=(border,)+placed.decorations+tuple(damage))
        if node.kind not in ('horizontal','vertical','run'):
            raise EgyptianLayoutError(f'unsupported XSR node {node.kind}')
        return self._pack([self._node(child) for child in node.children], node.kind=='vertical')

    def quadrats(self, parsed: ParsedEgyptianRun) -> tuple[RenderResult, ...]:
        """Atomic units in logical order; TeX performs paragraph breaking."""
        boxes = [self._node(child) for child in parsed.structure.children]
        boxes = [self._transform(box, min(1.0, 1.0 / box.height)) for box in boxes]
        height = max(b.height for b in boxes)
        result=[]
        cursor=0.0
        for i,box in enumerate(boxes):
            before= i>0 and box.continuous
            after= i+1<len(boxes) and box.continuous
            left,right=(after,before) if self.rtl else (before,after)
            lp,rp=(0 if left else self.padding),(0 if right else self.padding)
            if box.continuous:
                box=replace(box,height=height,decorations=(Decoration('shade',0,0,box.width,height,.008),))
            placed=self._transform(box,x=lp,y=self.padding+(height-box.height)/2)
            phase=-cursor-box.width-lp-rp if self.rtl else cursor
            placed=replace(placed,decorations=tuple(replace(d,phase=phase) if d.kind=='shade' else d for d in placed.decorations))
            cursor+=box.width+lp+rp
            result.append(replace(placed,width=box.width+lp+rp,height=height+2*self.padding))
        return tuple(result)

    def layout(self, parsed: ParsedEgyptianRun) -> RenderResult:
        boxes=list(self.quadrats(parsed))
        if self.rtl:
            boxes.reverse()
        cursor=0
        placed=[]
        for box in boxes:
            item=self._transform(box,x=cursor)
            # Combined diagnostics already have global positions.
            placed.append(replace(item,decorations=tuple(replace(d,phase=0) for d in item.decorations)))
            cursor+=box.width
        return RenderResult(cursor,max(b.height for b in boxes),0,
                            tuple(g for b in placed for g in b.glyphs),
                            tuple(d for b in placed for d in b.decorations),
                            tuple(r for b in placed for r in b.insertions))


# Compatibility name; this class no longer consumes Hieropy geometry.
HieropyLayout = EgyptianLayout
