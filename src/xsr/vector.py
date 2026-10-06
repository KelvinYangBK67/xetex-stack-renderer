"""Restricted glyph SVG interchange, normalized vector geometry and PGF output."""
from dataclasses import dataclass
import math
import re
import xml.etree.ElementTree as ET
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen
from .errors import XSRError

IMPORT_VERSION = 'vector-0.9'
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
TOKEN = re.compile(NUMBER + r'|[A-Za-z]')


def fail(detail):
    raise XSRError('XSR-SVG-INVALID', detail)


def numbers(text):
    tokens = re.findall(NUMBER, text)
    if re.sub(NUMBER, '', text).strip(' ,\t\r\n'):
        fail('invalid numeric list')
    values = tuple(float(t) for t in tokens)
    if any(not math.isfinite(v) or abs(v) > 1e9 for v in values):
        fail('nonfinite or excessive coordinate')
    return values


@dataclass(frozen=True)
class VectorCommand:
    operation: str
    points: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class VectorPath:
    commands: tuple[VectorCommand, ...]
    transform: Transform = Transform()
    fill: bool = True
    stroke: bool = False
    stroke_width: float = 0.


@dataclass(frozen=True)
class ExternalVectorGlyph:
    design_width: float
    design_height: float
    advance: float
    height: float
    depth: float
    bounds: tuple[float, float, float, float]
    paths: tuple[VectorPath, ...]


def path_commands(data):
    tokens = TOKEN.findall(data)
    if TOKEN.sub('', data).strip(' ,\t\r\n'):
        fail('malformed path data')
    result, i, command = [], 0, None
    current = start = (0., 0.)
    arity = {'M': 2, 'L': 2, 'H': 1, 'V': 1, 'Q': 4, 'C': 6}
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
            if command.upper() == 'Z':
                if not result:
                    fail('close without subpath')
                result.append(VectorCommand('closePath'))
                current, command = start, None
                continue
        if command is None or command.upper() not in arity:
            fail('unsupported or missing path command')
        kind, relative = command.upper(), command.islower()
        count = arity[kind]
        if i + count > len(tokens) or any(t.isalpha() for t in tokens[i:i+count]):
            fail('incomplete path command')
        values = numbers(' '.join(tokens[i:i+count]))
        i += count
        if not result and kind != 'M':
            fail('path must begin with moveto')
        x, y = current
        if kind == 'H':
            points = ((values[0] + (x if relative else 0), y),)
        elif kind == 'V':
            points = ((x, values[0] + (y if relative else 0)),)
        else:
            points = tuple((values[j] + (x if relative else 0), values[j+1] + (y if relative else 0))
                           for j in range(0, count, 2))
        if kind == 'Q':
            q, end = points
            points = ((x + 2/3*(q[0]-x), y + 2/3*(q[1]-y)),
                      (end[0] + 2/3*(q[0]-end[0]), end[1] + 2/3*(q[1]-end[1])), end)
        operation = 'moveTo' if kind == 'M' else 'curveTo' if kind in ('Q', 'C') else 'lineTo'
        result.append(VectorCommand(operation, points))
        current = points[-1]
        if kind == 'M':
            start = current
            command = 'l' if relative else 'L'
    return tuple(result)


def parse_transform(text):
    transform = Transform()
    pattern = re.compile(r'\s*(translate|rotate|scale|matrix)\s*\(([^()]*)\)\s*,?')
    position = 0
    while position < len(text):
        match = pattern.match(text, position)
        if not match:
            fail('invalid or unsupported transform')
        name, value = match.groups()
        args = numbers(value)
        if name == 'translate' and len(args) in (1, 2):
            step = Transform().translate(args[0], args[1] if len(args) == 2 else 0)
        elif name == 'scale' and len(args) in (1, 2):
            step = Transform().scale(args[0], args[-1])
        elif name == 'rotate' and len(args) in (1, 3):
            cx, cy = args[1:] if len(args) == 3 else (0, 0)
            step = Transform().translate(cx, cy).rotate(math.radians(args[0])).translate(-cx, -cy)
        elif name == 'matrix' and len(args) == 6:
            step = Transform(*args)
        else:
            fail('invalid transform arguments')
        transform = transform.transform(step)
        position = match.end()
    return transform


def path_bounds(paths):
    bounds = []
    for path in paths:
        pen = BoundsPen(None)
        target = TransformPen(pen, path.transform)
        for command in path.commands:
            getattr(target, command.operation)(*command.points)
        if pen.bounds is not None and (path.fill or path.stroke):
            a, b, c, d, _, _ = path.transform
            # Conservative default miter-join bound (SVG miterlimit = 4).
            px = 2*path.stroke_width*math.hypot(a, c) if path.stroke else 0
            py = 2*path.stroke_width*math.hypot(b, d) if path.stroke else 0
            x0, y0, x1, y1 = pen.bounds
            bounds.append((x0-px, y0-py, x1+px, y1+py))
    return (min(b[0] for b in bounds), min(b[1] for b in bounds),
            max(b[2] for b in bounds), max(b[3] for b in bounds)) if bounds else (0.,)*4


def import_svg(data):
    if len(data) > 2_000_000:
        fail('SVG exceeds 2 MB glyph limit')
    if isinstance(data, bytes):
        try:
            data = data.decode('utf-8-sig')
        except UnicodeError as error:
            fail(f'SVG must be UTF-8: {error}')
    if len(data) > 2_000_000:
        fail('SVG exceeds 2 MB glyph limit')
    # UTF-8-only and no declarations: no entity expansion or external resolver.
    if '<!' in re.sub(r'<!--.*?-->', '', data, flags=re.S) or re.search(r'<\?(?!xml\s)', data):
        fail('DTD, entities and processing instructions are forbidden')
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        fail(f'malformed XML: {error}')

    def tag(element):
        name = element.tag
        return name.split('}', 1)[1] if name.startswith('{http://www.w3.org/2000/svg}') else name

    if tag(root) != 'svg':
        fail('root must be SVG')

    def dimension(value):
        match = re.fullmatch(r'\s*(' + NUMBER + r')(?:px)?\s*', value)
        if not match:
            fail('only numeric/px dimensions are supported')
        result = numbers(match[1])[0]
        if result <= 0:
            fail('design dimensions must be positive')
        return result

    width = dimension(root.attrib['width']) if 'width' in root.attrib else None
    height = dimension(root.attrib['height']) if 'height' in root.attrib else None
    if 'viewBox' in root.attrib:
        view = numbers(root.attrib['viewBox'])
        if len(view) != 4 or view[2] <= 0 or view[3] <= 0:
            fail('viewBox requires four values with positive dimensions')
        x, y, width, height = view
    elif width and height:
        x = y = 0
    else:
        fail('supply viewBox or width and height')
    # One design-space height = one em; preserve the aspect ratio.
    normal = Transform(1/height, 0, 0, -1/height, -x/height, 1+y/height)
    paths = []
    appearance = {'fill': 'black', 'stroke': 'none', 'stroke-width': '1'}

    def visit(element, parent, inherited, depth=0):
        if depth > 64:
            fail('SVG nesting exceeds 64 levels')
        name = tag(element)
        allowed = {'transform', 'fill', 'stroke', 'stroke-width', 'id'}
        if element is root:
            allowed |= {'width', 'height', 'viewBox', 'version'}
        elif name == 'path':
            allowed |= {'d'}
        elif name != 'g':
            fail(f'unsupported SVG element: {name}')
        if set(element.attrib) - allowed:
            fail(f'unsupported SVG attributes: {sorted(set(element.attrib)-allowed)}')
        if (element.text or '').strip() or (element.tail or '').strip():
            fail('text content is unsupported')
        style = inherited | {k: v for k, v in element.attrib.items() if k in appearance}
        for key in ('fill', 'stroke'):
            if style[key] not in ('black', '#000', '#000000', 'none'):
                fail('only black or none paint is supported')
        stroke = numbers(style['stroke-width'])
        if len(stroke) != 1 or stroke[0] < 0:
            fail('stroke-width must be a nonnegative number')
        transform = parent.transform(parse_transform(element.get('transform', '')))
        if any(not math.isfinite(v) or abs(v) > 1e9 for v in transform):
            fail('excessive transform')
        if name == 'path':
            if len(element):
                fail('path cannot have children')
            commands = tuple(VectorCommand(command.operation, tuple(normal.transformPoint(point)
                            for point in command.points))
                             for command in path_commands(element.get('d', '')))
            paths.append(VectorPath(commands, transform.transform(normal.inverse()),
                                    style['fill'] != 'none', style['stroke'] != 'none', stroke[0]/height))
        for child in element:
            visit(child, transform, style, depth+1)

    visit(root, normal, appearance)
    return ExternalVectorGlyph(width, height, width/height, 1., 0., path_bounds(paths), tuple(paths))


def tofu(width=1., height=1.):
    """Filled compound hollow box, independent of any font or its .notdef."""
    inset = min(width, height)*.07
    commands = path_commands(f'M0 0 H{width} V{height} H0 Z '
                             f'M{inset} {inset} V{height-inset} H{width-inset} V{inset} Z')
    path = VectorPath(commands)
    return ExternalVectorGlyph(width, height, width, height, 0., (0., 0., width, height), (path,))


def number(value):
    if not math.isfinite(value) or abs(value) > 1e9:
        fail('invalid transformed coordinate')
    return (f'{value:.9f}'.rstrip('0').rstrip('.') or '0') if value else '0'


def paths_tex(glyph):
    """Numeric-only PGF operations: SVG strings never reach executable TeX."""
    result = []
    for path in glyph.paths:
        transform = ''.join('{' + number(v) + '}' for v in path.transform)
        operations = []
        for command in path.commands:
            if command.operation == 'closePath':
                operations.append(r'\pgfpathclose')
            else:
                name = {'moveTo': 'moveto', 'lineTo': 'lineto', 'curveTo': 'curveto'}[command.operation]
                args = ''.join('{' + r'\xsrVectorPoint' + ''.join('{' + number(v) + '}' for v in p) + '}'
                               for p in command.points)
                operations.append(r'\pgfpath' + name + args)
        paint = ','.join(name for name, enabled in [('fill', path.fill), ('stroke', path.stroke)] if enabled) or 'discard'
        result.append(r'\xsrVectorPath' + transform + '{' + number(path.stroke_width) + '}{'
                      + paint + '}{' + ''.join(operations) + '}')
    return ''.join(result)


def glyph_tex(glyph):
    return r'\xsrVectorBox' + ''.join('{' + number(v) + '}' for v in
                                      (glyph.advance, glyph.height, glyph.depth)) + '{' + paths_tex(glyph) + '}'
