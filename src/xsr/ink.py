"""Font outline transforms and conservative scanline occupancy.

Raster masks are used ONLY for layout decisions. Output remains vector glyphs.
No font names, sign-specific slots, alternate glyphs or reference-font metrics enter
this module. Cubic/quadratic curves are flattened adaptively in normalized em.
"""
import math
from functools import lru_cache
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import replayRecording
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from PIL import Image, ImageDraw, ImageFilter


def matrix(rotation=0, mirror=False):
    theta = math.radians(rotation)
    c, s = math.cos(theta), math.sin(theta)
    m = -1 if mirror else 1
    return (m * c, -s, m * s, c, 0, 0)


def outline_bounds(outline, rotation=0, mirror=False):
    pen = BoundsPen(None)
    replayRecording(outline, TransformPen(pen, matrix(rotation, mirror)))
    return pen.bounds


class FlattenPen(BasePen):
    tolerance = .0005

    def __init__(self):
        super().__init__(None)
        self.contours = []
        self.points = []

    def _moveTo(self, p):
        self.points = [p]

    def _lineTo(self, p):
        self.points.append(p)

    def _closePath(self):
        if self.points:
            self.contours.append(tuple(self.points + [self.points[0]]))
        self.points = []

    def _endPath(self):
        self._closePath()

    def _curveToOne(self, p1, p2, p3):
        def flatten(a, b, c, d, depth=0):
            # Control-polygon excess bounds curvature, with a distance test
            # that also handles a closed/degenerate chord.
            chord = math.dist(a, d)
            excess = math.dist(a, b) + math.dist(b, c) + math.dist(c, d) - chord
            if chord:
                distance = max(abs((d[0]-a[0])*(p[1]-a[1])-(d[1]-a[1])*(p[0]-a[0]))/chord for p in (b,c))
            else:
                distance = max(math.dist(a,b),math.dist(a,c))
            if (excess < self.tolerance and distance < self.tolerance) or depth >= 14:
                self.points.append(d)
                return
            mid = lambda u, v: ((u[0]+v[0])/2, (u[1]+v[1])/2)
            ab, bc, cd = mid(a,b), mid(b,c), mid(c,d)
            abc, bcd = mid(ab,bc), mid(bc,cd)
            center = mid(abc,bcd)
            flatten(a,ab,abc,center,depth+1)
            flatten(center,bcd,cd,d,depth+1)
        flatten(self._getCurrentPoint(), p1, p2, p3)


@lru_cache(maxsize=512)
def contours(outline, rotation=0, mirror=False):
    pen = FlattenPen()
    replayRecording(outline, TransformPen(pen, matrix(rotation, mirror)))
    return tuple(pen.contours)


def ink_mask(font, box, resolution=160, margin=.012):
    """Nonzero-winding fill; holes stay empty, intersecting contours stay ink.

    The mask is dilated for scan-conversion error and a real em-based margin.
    Insertion accepts an empty rectangle, conservatively reserving the complete
    inserted group box, including its decorations and nested insertions.
    """
    unit = resolution / max(box.width, box.height)
    w, h = math.ceil(box.width * unit)+1, math.ceil(box.height * unit)+1
    mask = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(mask)
    for glyph in box.glyphs:
        paths = contours(font.outline(glyph.codepoint), glyph.rotation, glyph.mirror)
        edges = []
        for path in paths:
            points = [((glyph.x + (x-glyph.ink_left)*glyph.scale)*unit,
                       (glyph.y + (glyph.ink_top-y)*glyph.scale)*unit) for x,y in path]
            edges.extend(zip(points, points[1:]))
            # Reserve boundaries too: thin strokes must not disappear between rows.
            draw.line(points, fill=255, width=1)
        for row in range(h):
            y = row + .5
            hits = []
            for (x1,y1),(x2,y2) in edges:
                if min(y1,y2) <= y < max(y1,y2):
                    hits.append((x1+(y-y1)*(x2-x1)/(y2-y1), 1 if y2>y1 else -1))
            hits.sort()
            winding, start = 0, 0
            for x, sign in hits:
                if winding == 0:
                    start = x
                winding += sign
                if winding == 0:
                    draw.line((math.floor(start),row,math.ceil(x),row),fill=255)
    # Existing inserts must not be invaded by subsequent inserts, even through
    # holes in an inserted glyph. Enclosures/decorations are also reserved.
    for region in (*box.insertions, *box.decorations):
        draw.rectangle((region.x*unit,region.y*unit,
                        (region.x+region.width)*unit,(region.y+region.height)*unit),fill=255)
    radius = max(1, math.ceil(margin*unit))
    return mask.filter(ImageFilter.MaxFilter(2*radius+1)), unit


def insertion_region(font, core, child, slot):
    mask, unit = ink_mask(font, core)
    w,h = mask.size
    data = mask.tobytes()
    integral = [[0]*(w+1) for _ in range(h+1)]
    for y in range(h):
        running = 0
        for x in range(w):
            running += bool(data[y*w+x])
            integral[y+1][x+1] = integral[y][x+1] + running
    anchors = {'ts':(0,0),'bs':(0,1),'te':(1,0),'be':(1,1),
               'm':(.5,.5),'t':(.5,0),'b':(.5,1)}
    ax,ay = anchors[slot]
    # Prefer a legible large inset, then look for the nearest semantic region.
    initial = min(1, core.height*.52/child.height, core.width*.58/child.width)
    for step in range(18):
        scale = initial * .90**step
        if child.height*scale < core.height*.10:
            break
        rw,rh = math.ceil(child.width*scale*unit),math.ceil(child.height*scale*unit)
        candidates=[]
        for y in range(1,h-rh-1):
            cy=(y+rh/2)/(h-1)
            if (ay==0 and cy>.55) or (ay==1 and cy<.45):
                continue
            for x in range(1,w-rw-1):
                cx=(x+rw/2)/(w-1)
                if (ax==0 and cx>.55) or (ax==1 and cx<.45):
                    continue
                if ax==.5 and abs(cx-.5)>.20:
                    continue
                if ay==.5 and abs(cy-.5)>.20:
                    continue
                ink = integral[y+rh][x+rw]-integral[y][x+rw]-integral[y+rh][x]+integral[y][x]
                if ink==0:
                    candidates.append(((cx-ax)**2+(cy-ay)**2,x,y))
        if candidates:
            _,x,y=min(candidates)
            return x/unit,y/unit,scale
    return None
