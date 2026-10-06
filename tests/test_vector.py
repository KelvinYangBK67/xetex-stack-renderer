import pytest
from xsr.errors import XSRError
from xsr.vector import import_svg, parse_transform, path_commands, tofu


def svg(path, attrs='', root='viewBox="0 0 200 200"'):
    return import_svg(f'<svg {root}><path d="{path}" {attrs}/></svg>')


@pytest.mark.parametrize('path', [
    'M20 20 L180 20 L180 180 L20 180 Z', 'M20 20 H180 V180 H20 z',
    'm20 20 h160 v160 h-160 z', 'M20 20 180 20 180 180 20 180Z',
    'M2e1 .2e2L1.8e2 20L180 180L20 180z'])
def test_rectangle(path):
    glyph = svg(path)
    assert glyph.bounds == pytest.approx((.1, .1, .9, .9))
    assert (glyph.advance, glyph.height, glyph.depth) == (1, 1, 0)


def test_quadratic_exact_conversion_and_extrema():
    glyph = svg('M0 0 Q100 200 200 0')
    command = glyph.paths[0].commands[1]
    assert command.points[0] == pytest.approx((1/3, 1/3))
    assert command.points[1] == pytest.approx((2/3, 1/3))
    assert glyph.bounds == pytest.approx((0, .5, 1, 1))
    assert svg('m0 0 q100 200 200 0').bounds == glyph.bounds


def test_cubic_and_relative():
    a = svg('M0 0 C0 200 200 200 200 0')
    b = svg('m0 0 c0 200 200 200 200 0')
    assert a.bounds == b.bounds == (0, .25, 1, 1)


@pytest.mark.parametrize('transform,expected', [
    ('translate(20,40)', (.1, .7, .2, .8)),
    ('scale(2)', (0, .8, .2, 1)),
    ('rotate(90)', (-.1, .9, 0, 1)),
    ('rotate(90,10,10)', (0, .9, .1, 1)),
    ('matrix(2,0,0,3,20,40)', (.1, .5, .3, .8)),
    ('translate(20 40) scale(2)', (.1, .6, .3, .8)),
])
def test_transforms(transform, expected):
    assert svg('M0 0H20V20H0Z', f'transform="{transform}"').bounds == pytest.approx(expected)


def test_nested_multiple_paths_viewbox_y_inversion():
    glyph = import_svg('<svg viewBox="10 20 400 100"><g transform="translate(10 20)"><g transform="scale(2)"><path d="M0 0H10V10H0Z"/></g><path d="M100 50H120V60H100Z"/></g></svg>')
    assert len(glyph.paths) == 2
    assert glyph.advance == 4
    assert glyph.bounds == pytest.approx((0, .4, 1.2, 1))


@pytest.mark.parametrize('body', ['<script/>', '<image/>', '<text>Hi</text>', '<filter/>',
    '<linearGradient/>', '<radialGradient/>', '<mask/>', '<style/>', '<animate/>',
    '<use href="https://example.com/x"/>', '<path d="M0 0" href="x"/>',
    '<path d="M0 0" fill="url(https://example.com/x)"/>',
    '<path style="fill:black" d="M0 0"/>', '<path d="M0 0" opacity=".5"/>'])
def test_reject_semantics(body):
    with pytest.raises(XSRError, match='XSR-SVG-INVALID'):
        import_svg('<svg viewBox="0 0 200 200">'+body+'</svg>')


@pytest.mark.parametrize('path', ['M', 'M0', 'M0 0 L', 'L0 0', 'Z', 'M0 0 A2 3 0 0 0 4 5',
                                  'M0 0 S1 2 3 4', 'M0 0 LNaN 3', 'M0 0 L1e999 2', 'M0 0@'])
def test_bad_path(path):
    with pytest.raises(XSRError, match='XSR-SVG-INVALID'):
        svg(path)


@pytest.mark.parametrize('transform', ['skewX(2)', 'rotate()', 'matrix(1 2)', 'translate(1)x', 'scale(NaN)'])
def test_bad_transform(transform):
    with pytest.raises(XSRError, match='XSR-SVG-INVALID'):
        parse_transform(transform)


@pytest.mark.parametrize('data', ['<svg', '<svg/>', '<!DOCTYPE svg [<!ENTITY x "a">]><svg/>',
    '<svg width="0" height="200"/>', '<svg width="-1" height="200"/>',
    '<svg viewBox="0 0 0 200"/>', '<svg viewBox="0 0 -1 200"/>',
    '<svg width="10%" height="2em"/>', '<?xml-stylesheet href="x"?><svg/>'])
def test_invalid_container(data):
    with pytest.raises(XSRError, match='XSR-SVG-INVALID'):
        import_svg(data)


def test_stroke_and_none():
    glyph = svg('M0 0L100 100', 'fill="none" stroke="black" stroke-width="2"')
    assert glyph.paths[0].stroke and not glyph.paths[0].fill
    assert glyph.paths[0].stroke_width == .01


def test_tofu_is_compound_geometry():
    glyph = tofu()
    assert glyph.bounds == (0, 0, 1, 1)
    assert len(glyph.paths[0].commands) == 10
    assert glyph.paths[0].commands[5].points == ((.07, .07),)

def test_large_design_units_are_normalized_before_tex():
    glyph = svg('M1000000 2000000H1200000V2200000H1000000Z', root='viewBox="1000000 2000000 200000 200000"')
    assert glyph.bounds == pytest.approx((0,0,1,1))
    assert glyph.paths[0].commands[0].points == ((0,1),)
